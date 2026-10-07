from __future__ import annotations

from collections import deque
import json
import random
import uuid

from pydantic import ValidationError

from .certifications import certification
from .ollama_client import OllamaClient, OllamaError
from .progress import ProgressStore
from .question_patterns import QuestionPatternBank
from .question_store import QuestionStore
from .quiz_reliability import (
    QuizReliabilityError,
    assert_final_consistency,
    build_final_quiz,
    concept_signature,
    freeze_candidate,
    question_fingerprint,
    validate_candidate,
    validate_llm_review,
    validate_session_diversity,
)
from .rag import RagIndex
from .schemas import (
    CanonicalQuestion,
    ExplanationDraft,
    GeneratedQuiz,
    PublicQuestion,
    QuestionCandidate,
    QuestionValidation,
)


class QuizGenerationError(RuntimeError):
    pass


_QUESTION_SYSTEM = """
You generate exactly one Microsoft certification practice question from a tiny
official evidence set already mapped to the current certification blueprint.
The measured exam objective is a hard scope gate. Use only explicit evidence;
do not use model memory to fill gaps. Prefer a constrained operational scenario
over documentation recall. Return insufficient_context when one uniquely
defensible answer is not supported. Produce question data only: never generate
an explanation. Use stable IDs opt_1, opt_2, opt_3, opt_4. Letters are forbidden.
""".strip()

_VALIDATION_SYSTEM = """
You are an evidence auditor, not a question writer. Check one candidate against
the exact official evidence supplied. Assess every option independently before
the verdict. Reject when two or more options are valid, validity depends on an
unstated assumption, or one answer is merely more likely. Also reject unsupported
claims, equivalent aliases, duplicate answers, weak distractors, scope drift, or
a missing discriminator. Copy the fingerprint, correct option ID, and source
IDs; you have no authority to change them. Return only the validation schema.
""".strip()

_EXPLANATION_SYSTEM = """
The answer in this frozen question was already validated. Do not solve it again
and do not choose or change an answer. Return one evidence-grounded rationale
for each provided stable option ID. Rationales must teach the decision boundary:
why the correct capability meets the explicit requirement, why each distractor
fails it, and what a distractor is designed for when the evidence establishes
that use. Avoid generic or repeated rationales. Describe capability fit only:
do not name an option, product, company, option letter, or internal ID. The
server will attach each rationale to the immutable option text. Copy the exact
question fingerprint and correct option ID. Source authority remains frozen by
the server and is not part of your output. Also return three short teaching
fields: the decisive clue in the stem, a reusable decision rule, and one
memorable takeaway. They must add learning value rather than repeat the answer.
""".strip()


class QuizEngine:
    def __init__(
        self,
        client: OllamaClient,
        rag: RagIndex,
        progress: ProgressStore,
        questions: QuestionStore,
        patterns: QuestionPatternBank | None = None,
    ):
        self.client = client
        self.rag = rag
        self.progress = progress
        self.questions = questions
        self.patterns = patterns or QuestionPatternBank()
        self._recent_chunk_ids: deque[str] = deque(maxlen=16)
        self._recent_objectives: deque[str] = deque(maxlen=24)
        self._recent_concepts: deque[
            tuple[str, str, str, frozenset[str]]
        ] = deque(maxlen=24)
        self._answer_slot_deck: list[int] = []

    def prepare_certification(
        self,
        certification_code: str,
        *,
        progress=None,
        cancelled=None,
    ) -> dict:
        if not getattr(self.rag, "uses_microsoft_learn", False):
            return {"ready": True, "objective_count": 0, "card_count": 0}
        prepare = getattr(self.rag, "prepare_generation_corpus", None)
        if not callable(prepare):
            return {"ready": True, "objective_count": 0, "card_count": 0}
        return prepare(
            certification_code,
            progress=progress,
            cancelled=cancelled,
        )

    def learning_plan(
        self,
        certification_code: str,
        count: int,
        *,
        mode: str = "shuffle",
        domain: str | None = None,
        question_types: list[str] | None = None,
    ) -> list[str | None]:
        """Plan a complete batch before revision, with no mid-session LLM call."""
        if not getattr(self.rag, "uses_microsoft_learn", False):
            return [None] * count
        objectives = self.rag.blueprint_objectives(
            certification_code,
            domain if mode == "domain" else None,
        )
        if not objectives:
            return [None] * count
        prioritize = getattr(self.progress, "objective_priorities", None)
        if callable(prioritize):
            priorities = prioritize(certification_code, objectives)
        else:
            priorities = [
                {
                    "learning_objective": objective,
                    "asked": 0,
                    "mastery": 0.0,
                }
                for objective in objectives
            ]
        ordered = [str(item["learning_objective"]) for item in priorities]
        weak = [
            str(item["learning_objective"])
            for item in priorities
            if int(item.get("asked", 0)) > 0 and float(item.get("mastery", 0)) < 0.75
        ][:2]
        reinforcement_slots = min(count // 3, len(ordered)) if count >= 4 else 0
        anchors = list(dict.fromkeys([*weak, *ordered]))[:reinforcement_slots]
        breadth_target = count - reinforcement_slots
        plan: list[str] = list(anchors)
        for objective in ordered:
            if len(plan) >= breadth_target:
                break
            if objective not in plan:
                plan.append(objective)
        while len(plan) < breadth_target:
            plan.append(ordered[len(plan) % len(ordered)])
        for index in range(reinforcement_slots):
            plan.append(anchors[index % len(anchors)])
        while len(plan) < count:
            plan.append(ordered[len(plan) % len(ordered)])
        case_objectives_method = getattr(self.rag, "case_study_objectives", None)
        if question_types and callable(case_objectives_method):
            case_objectives = case_objectives_method(
                certification_code,
                domain if mode == "domain" else None,
            )
            case_ranked = [value for value in ordered if value in case_objectives]
            if case_ranked:
                case_index = 0
                for index, value in enumerate(question_types[:count]):
                    if value != "case_study" or plan[index] in case_objectives:
                        continue
                    plan[index] = case_ranked[case_index % len(case_ranked)]
                    case_index += 1
        return plan[:count]

    def reuse_question(
        self,
        *,
        certification_code: str,
        question_type: str,
        difficulty: str,
        domain: str | None,
        learning_objective: str | None,
        exclude_question_ids: set[str],
    ) -> PublicQuestion | None:
        select = getattr(self.questions, "select_one", None)
        if not callable(select):
            return None
        preferred = []
        if learning_objective:
            preferred.append(learning_objective)
        selected = select(
            certification_code=certification_code,
            question_type=question_type,
            difficulty=difficulty,
            domain=domain,
            learning_objective=learning_objective,
            preferred_objectives=preferred,
            exclude_question_ids=exclude_question_ids,
        )
        if not selected:
            return None
        question_id, payload = selected
        try:
            final = GeneratedQuiz.model_validate(payload)
            assert_final_consistency(final)
        except (ValidationError, QuizReliabilityError):
            return None
        mark_presented = getattr(self.questions, "mark_presented", None)
        if callable(mark_presented):
            mark_presented(question_id)
        return self._public_question(question_id, final)

    def _next_answer_slot(self) -> int:
        if not self._answer_slot_deck:
            self._answer_slot_deck = [0, 1, 2, 3]
            random.shuffle(self._answer_slot_deck)
        return self._answer_slot_deck.pop()

    @staticmethod
    def _resolve_difficulty(requested: str) -> str:
        if requested == "random":
            return random.choice(["easy", "medium", "hard"])
        return requested

    @staticmethod
    def _resolve_question_type(requested: str) -> str:
        if requested == "mixed":
            return random.choices(
                ["standard", "case_study"], weights=[7, 3], k=1
            )[0]
        return requested

    @staticmethod
    def _question_type_instruction(question_type: str) -> str:
        if question_type == "case_study":
            return (
                "Create a compact case study with a title, an 80-3000 character "
                "scenario, and 2-5 explicit requirements. It must synthesize and "
                "cite at least two supplied evidence chunks."
            )
        return "Create a standalone question and omit case_study."

    @staticmethod
    def _generation_schema(question_type: str, difficulty: str | None = None) -> dict:
        schema = QuestionCandidate.model_json_schema()
        definitions = schema.get("$defs", {})
        case_study_schema = definitions.pop("CaseStudyContext")
        properties = schema["properties"]
        properties["question_type"]["enum"] = [question_type]
        if difficulty:
            properties["difficulty"]["enum"] = [difficulty]

        if question_type == "case_study":
            unsupported = {"maxLength"}

            def strip_grammar_constraints(value):
                if isinstance(value, dict):
                    return {
                        key: strip_grammar_constraints(item)
                        for key, item in value.items()
                        if key not in unsupported
                    }
                if isinstance(value, list):
                    return [strip_grammar_constraints(item) for item in value]
                return value

            properties["case_study"] = strip_grammar_constraints(case_study_schema)
            if "case_study" not in schema["required"]:
                schema["required"].append("case_study")
        else:
            properties.pop("case_study", None)
        return schema

    @staticmethod
    def _objective_key(certification_code: str, objective: str) -> str:
        return f"{certification_code.upper()}|{' '.join(objective.casefold().split())}"

    def _random_seed_item(self, certification_code: str) -> dict:
        candidates = [
            item
            for item in self.rag.items
            if (item.get("metadata") or {}).get("topic")
            and (item.get("metadata") or {}).get("domain")
            not in {None, "unknown", "Cross-domain / orientation"}
        ]
        if not candidates:
            candidates = list(self.rag.items)
        fresh = [
            item
            for item in candidates
            if item.get("chunk_id") not in self._recent_chunk_ids
            and self._objective_key(
                certification_code,
                self._objective(item, certification_code),
            )
            not in self._recent_objectives
        ]
        return random.choice(fresh or candidates)

    @staticmethod
    def _dedupe_chunks(chunks: list[dict]) -> list[dict]:
        seen = set()
        result = []
        for chunk in chunks:
            chunk_id = chunk.get("chunk_id")
            if not chunk_id or chunk_id in seen:
                continue
            seen.add(chunk_id)
            result.append(chunk)
        return result

    @staticmethod
    def _objective(chunk: dict, fallback: str) -> str:
        metadata = chunk.get("metadata") or {}
        return str(
            metadata.get("learning_objective")
            or metadata.get("topic")
            or fallback
        )

    def _select_context(
        self,
        certification_code: str,
        mode: str,
        domain: str | None,
        chapter_id: str | None,
        requested_objective: str | None = None,
        top_k: int = 3,
    ) -> tuple[str, str | None, str, list[dict]]:
        selected_certification = certification(certification_code)
        top_k = max(1, min(top_k, 3))
        if getattr(self.rag, "uses_microsoft_learn", False):
            blueprint_domains = self.rag.blueprint_domains(
                selected_certification.code
            )
            if not blueprint_domains:
                raise QuizGenerationError(
                    "The official study guide has no measured exam domains."
                )
            if mode == "chapter":
                raise QuizGenerationError(
                    "Chapter mode is available only with an indexed local corpus."
                )
            if requested_objective:
                selected_domain = next(
                    (
                        candidate_domain
                        for candidate_domain in blueprint_domains
                        if any(
                            self._objective_key(selected_certification.code, value)
                            == self._objective_key(
                                selected_certification.code,
                                requested_objective,
                            )
                            for value in self.rag.blueprint_objectives(
                                selected_certification.code,
                                candidate_domain,
                            )
                        )
                    ),
                    None,
                )
                if selected_domain is None:
                    raise QuizGenerationError(
                        "The planned learning objective is absent from the blueprint."
                    )
            elif mode == "domain":
                selected_domain = next(
                    (
                        value
                        for value in blueprint_domains
                        if " ".join(value.casefold().split())
                        == " ".join((domain or "").casefold().split())
                    ),
                    None,
                )
                if selected_domain is None:
                    raise QuizGenerationError(
                        f"Select a valid {selected_certification.code} domain."
                    )
            else:
                selected_domain = random.choice(blueprint_domains)
            objectives = self.rag.blueprint_objectives(
                selected_certification.code,
                selected_domain,
            )
            if not objectives:
                raise QuizGenerationError(
                    "The official blueprint has no measured objective in this domain."
                )
            if requested_objective:
                objective = next(
                    value
                    for value in objectives
                    if self._objective_key(selected_certification.code, value)
                    == self._objective_key(
                        selected_certification.code,
                        requested_objective,
                    )
                )
            else:
                fresh_objectives = [
                    value
                    for value in objectives
                    if self._objective_key(selected_certification.code, value)
                    not in self._recent_objectives
                ]
                prioritize = getattr(self.progress, "objective_priorities", None)
                if callable(prioritize):
                    ranked = prioritize(
                        selected_certification.code,
                        fresh_objectives or objectives,
                    )
                    pool = [
                        item["learning_objective"]
                        for item in ranked[: min(4, len(ranked))]
                    ]
                    objective = random.choice(pool)
                else:
                    objective = random.choice(fresh_objectives or objectives)
            discovery_query = (
                f"{objective} documented behavior requirements constraints use case"
            )
            packet = getattr(self.rag, "select_evidence_packet", None)
            if callable(packet):
                retrieved = packet(
                    discovery_query,
                    top_k=top_k,
                    domain=selected_domain,
                    certification_code=selected_certification.code,
                    learning_objective=objective,
                    exclude_chunk_ids=set(self._recent_chunk_ids),
                )
            else:
                retrieved = self.rag.search(
                    discovery_query,
                    top_k=top_k,
                    domain=selected_domain,
                    certification_code=selected_certification.code,
                    learning_objective=objective,
                )
            if not retrieved:
                raise QuizGenerationError("No blueprint-scoped Learn evidence was found.")
            return discovery_query, selected_domain, objective, retrieved

        if mode == "domain":
            if not domain:
                raise QuizGenerationError("Domain mode requires a domain.")
            candidates = [
                item
                for item in self.rag.items
                if (item.get("metadata") or {}).get("domain") == domain
                and item.get("chunk_id") not in self._recent_chunk_ids
                and self._objective_key(
                    certification_code,
                    self._objective(item, domain),
                )
                not in self._recent_objectives
            ]
            if not candidates:
                candidates = [
                    item
                    for item in self.rag.items
                    if (item.get("metadata") or {}).get("domain") == domain
                ]
            if not candidates:
                raise QuizGenerationError(f"No indexed chunks found for domain: {domain}")
            seed = random.choice(candidates)
            objective = self._objective(seed, domain)
            retrieved = self.rag.search(
                f"{objective} documented behavior requirements constraints use case",
                top_k=top_k,
                domain=domain,
                certification_code=certification_code,
                learning_objective=objective,
            )
            self._recent_chunk_ids.append(str(seed.get("chunk_id")))
            return objective, domain, objective, self._dedupe_chunks([seed, *retrieved])[:top_k]

        if mode == "chapter":
            if not chapter_id:
                raise QuizGenerationError("Chapter mode requires a chapter_id.")
            seed = self.rag.get(chapter_id)
            if not seed:
                raise QuizGenerationError(f"Unknown chapter_id: {chapter_id}")
            metadata = seed.get("metadata") or {}
            objective = self._objective(seed, str(metadata.get("topic") or chapter_id))
            selected_domain = metadata.get("domain")
            related = self.rag.search(
                f"{objective} documented behavior requirements constraints use case",
                top_k=max(top_k - 1, 1),
                domain=selected_domain,
                certification_code=certification_code,
                learning_objective=objective,
            )
            return objective, selected_domain, objective, self._dedupe_chunks([seed, *related])[:top_k]

        seed = self._random_seed_item(certification_code)
        metadata = seed.get("metadata") or {}
        objective = self._objective(seed, certification_code)
        selected_domain = metadata.get("domain")
        related = self.rag.search(
            f"{objective} documented behavior requirements constraints use case",
            top_k=top_k,
            domain=selected_domain,
            certification_code=certification_code,
            learning_objective=objective,
        )
        self._recent_chunk_ids.append(str(seed.get("chunk_id")))
        return objective, selected_domain, objective, self._dedupe_chunks([seed, *related])[:top_k]

    @staticmethod
    def _format_context(chunks: list[dict]) -> str:
        blocks = []
        for chunk in chunks[:3]:
            metadata = chunk.get("metadata") or {}
            blocks.append(
                "\n".join(
                    [
                        f"source_id: {chunk['chunk_id']}",
                        f"source_url: {chunk['source']}",
                        f"certification: {metadata.get('certification', 'local')}",
                        f"exam_domain: {metadata.get('exam_domain') or metadata.get('domain', 'unknown')}",
                        f"skill_group: {metadata.get('skill_group', 'unknown')}",
                        f"measured_objective: {metadata.get('skill_objective') or metadata.get('learning_objective') or 'unknown'}",
                        f"learn_unit: {metadata.get('unit') or metadata.get('module') or 'page'}",
                        f"evidence_role: {metadata.get('evidence_role', 'retrieved')}",
                        f"questionability_score: {metadata.get('questionability_score', 'unscored')}",
                        f"blueprint_url: {metadata.get('blueprint_source_url', 'missing')}",
                        "evidence:",
                        str(chunk["text"]),
                    ]
                )
            )
        return "\n\n---\n\n".join(blocks)

    def _presentation_order(self, canonical: CanonicalQuestion) -> tuple[str, ...]:
        correct_id = canonical.correct_option_id
        distractors = [option.id for option in canonical.options if option.id != correct_id]
        random.shuffle(distractors)
        target_index = self._next_answer_slot()
        order = list(distractors)
        order.insert(target_index, correct_id)
        return tuple(order)

    def _generate_candidate_prompt(
        self,
        *,
        certification_code: str,
        certification_title: str,
        mode: str,
        domain: str | None,
        objective: str,
        difficulty: str,
        question_type: str,
        evidence: list[dict],
        previous_failure: str | None,
    ) -> str:
        retry = (
            f"\nThe previous candidate was rejected: {previous_failure}\n"
            if previous_failure
            else ""
        )
        case_study_shape = (
            '"case_study": {"title": "...", "scenario": "...", '
            '"requirements": ["...", "..."]},\n  '
            if question_type == "case_study"
            else ""
        )
        return f"""
Create one {certification_code} ({certification_title}) question.
Selection mode: {mode}
Exam domain: {domain or 'selected objective'}
Single learning objective: {objective}
Difficulty: {difficulty}
Format: {question_type}
{self._question_type_instruction(question_type)}
{self.patterns.prompt_hint(question_type)}

Requirements:
- Return question/options/correct_option_id/supporting_source_ids only; no explanation.
- Use exactly opt_1, opt_2, opt_3, opt_4 in that order.
- Test only the stated measured objective; related Azure knowledge is out of scope.
- Prefer an applied scenario with explicit requirements or tradeoffs over recall.
- Useful discriminators include management control, event-driven scaling, data
  model, serverless operations, security, monitoring, and troubleshooting.
- Exactly one answer must follow from explicit evidence and the stem's constraints.
- Each other option must fail an explicit requirement, not merely be less likely.
- Distractors must be plausible, same-domain, non-equivalent, and clearly wrong.
- Do not use renamed aliases of one product as competing options.
- Do not ask which broad proficiencies or skill bundles the blueprint requires.
- Cite only source_id values below. Return insufficient_context rather than guess.
{retry}
Output exactly one JSON object with this shape, without Markdown or prose:
{{
  "status": "ok",
  "question_type": "{question_type}",
  {case_study_shape}"question": "...",
  "options": [
    {{"id": "opt_1", "text": "..."}},
    {{"id": "opt_2", "text": "..."}},
    {{"id": "opt_3", "text": "..."}},
    {{"id": "opt_4", "text": "..."}}
  ],
  "correct_option_id": "opt_1",
  "supporting_source_ids": ["an exact source_id below"],
  "topic": "...",
  "domain": "{domain or '...'}",
  "difficulty": "{difficulty}",
  "confidence": 0.9
}}
<official_evidence>
{self._format_context(evidence)}
</official_evidence>
""".strip()

    def _validate_with_model(
        self,
        candidate: QuestionCandidate,
        evidence: list[dict],
    ) -> QuestionValidation:
        fingerprint = question_fingerprint(candidate)
        prompt = f"""
Question fingerprint (copy exactly): {fingerprint}
Candidate:
{json.dumps(candidate.model_dump(mode='json'), ensure_ascii=False, indent=2)}

Assess opt_1 through opt_4 independently against the evidence. A verdict is
"supported" only when the option objectively satisfies every stated requirement;
use "contradicted", "not_established", or "equivalent" otherwise. Then check:
exactly one supported answer; correct ID exists; every claim is supported;
distractors fail the stated constraints; no ambiguity, unstated assumption,
duplicate/equivalent answer, obsolete alias pair, or missing discriminator.

Output exactly one JSON object, without Markdown or prose:
{{"question_fingerprint":"{fingerprint}","verdict":"accept or reject",
"correct_option_id":"{candidate.correct_option_id}",
"supported_option_ids":["exactly one ID when accepted"],
"option_assessments":[
{{"option_id":"opt_1","verdict":"supported|contradicted|not_established|equivalent","supporting_source_ids":[]}},
{{"option_id":"opt_2","verdict":"supported|contradicted|not_established|equivalent","supporting_source_ids":[]}},
{{"option_id":"opt_3","verdict":"supported|contradicted|not_established|equivalent","supporting_source_ids":[]}},
{{"option_id":"opt_4","verdict":"supported|contradicted|not_established|equivalent","supporting_source_ids":[]}}],
"supporting_source_ids":{json.dumps(candidate.supporting_source_ids)},
"issues":[]}}

<official_evidence>
{self._format_context(evidence)}
</official_evidence>
""".strip()
        raw = self.client.chat_json(
            _VALIDATION_SYSTEM,
            prompt,
            QuestionValidation.model_json_schema(),
            think=True,
            temperature=0,
        )
        return QuestionValidation.model_validate(raw)

    def _explain(
        self,
        canonical: CanonicalQuestion,
        evidence: list[dict],
        previous_failure: str | None = None,
        repair_attempt: int = 0,
    ) -> ExplanationDraft:
        repair = (
            "\nThe previous explanation was rejected by the deterministic checker:\n"
            f"{previous_failure}\n"
            "Repair that exact defect. Rewrite all four rationales; for every "
            "distractor explicitly say which scenario requirement it does not "
            "meet and when that capability would instead be appropriate.\n"
            if previous_failure
            else ""
        )
        prompt = f"""
Frozen question (copy fingerprint and correct_option_id exactly):
{json.dumps(canonical.model_dump(mode='json'), ensure_ascii=False, indent=2)}

For each option ID, provide a concise capability-fit rationale. For the correct
option, connect its capability to the decisive scenario requirement. For every
distractor, state the failed requirement and, when evidence permits, what kind
of requirement would make it appropriate. Make all four rationales distinct.
Do not repeat option text and do not name any Azure/Microsoft product. Use only
the frozen evidence, but do not return or rewrite source IDs.
{repair}

Output exactly one JSON object, without Markdown or prose:
{{"question_fingerprint":"{canonical.question_fingerprint}",
"correct_option_id":"{canonical.correct_option_id}",
"decisive_clue":"the exact clue or constraint that decides the answer",
"learning_rule":"a concise reusable rule for similar situations",
"takeaway":"one short memory hook",
"rationales":[
{{"option_id":"opt_1","rationale":"..."}},
{{"option_id":"opt_2","rationale":"..."}},
{{"option_id":"opt_3","rationale":"..."}},
{{"option_id":"opt_4","rationale":"..."}}
]}}

<official_evidence>
{self._format_context(evidence)}
</official_evidence>
""".strip()
        raw = self.client.chat_json(
            _EXPLANATION_SYSTEM,
            prompt,
            ExplanationDraft.model_json_schema(),
            think=False,
            temperature=0 if repair_attempt == 0 else 0.2,
        )
        return ExplanationDraft.model_validate(raw)

    @staticmethod
    def _fallback_explanation(canonical: CanonicalQuestion) -> ExplanationDraft:
        """Preserve a validated question when the model only misses prose rules."""
        distractor_templates = (
            "This does not meet the stated operating requirement; it would "
            "fit when a different operational constraint is primary.",
            "This lacks the required capability; use it when that separate "
            "workload goal is the actual priority instead.",
            "This does not satisfy the stated decision boundary; it is appropriate "
            "when the scenario requires its narrower capability instead.",
        )
        distractor_index = 0
        rationales = []
        for option in canonical.options:
            if option.id == canonical.correct_option_id:
                rationale = (
                    "This meets the decisive scenario requirement because the cited "
                    "evidence supports the required capability and operating constraint."
                )
            else:
                rationale = distractor_templates[distractor_index]
                distractor_index += 1
            rationales.append({"option_id": option.id, "rationale": rationale})
        return ExplanationDraft.model_validate({
            "question_fingerprint": canonical.question_fingerprint,
            "correct_option_id": canonical.correct_option_id,
            "rationales": rationales,
            "decisive_clue": (
                "The decisive clue is the explicit operating constraint in the "
                "scenario, not general product familiarity."
            ),
            "learning_rule": (
                "Choose the capability that satisfies every stated requirement; "
                "reject choices that solve a neighboring problem."
            ),
            "takeaway": "Requirement first, capability second, elimination last.",
        })

    def generate(
        self,
        certification_code: str = "AI-103",
        mode: str = "shuffle",
        domain: str | None = None,
        chapter_id: str | None = None,
        difficulty: str = "random",
        question_type: str = "mixed",
        learning_objective: str | None = None,
    ) -> PublicQuestion:
        selected_certification = certification(certification_code)
        self.prepare_certification(selected_certification.code)
        resolved_difficulty = self._resolve_difficulty(difficulty)
        resolved_question_type = self._resolve_question_type(question_type)
        _, selected_domain, objective, evidence = self._select_context(
            selected_certification.code,
            mode,
            domain,
            chapter_id,
            requested_objective=learning_objective,
            top_k=3,
        )
        intended_module = str(
            (evidence[0].get("metadata") or {}).get("module") or ""
        ) or None
        minimum_evidence = 2 if resolved_question_type == "case_study" else 1
        if len(evidence) < minimum_evidence:
            raise QuizGenerationError("Insufficient scoped evidence for this question.")

        schema = self._generation_schema(
            resolved_question_type,
            difficulty=resolved_difficulty,
        )
        candidate: QuestionCandidate | None = None
        last_error: Exception | None = None
        previous_failure: str | None = None
        for _ in range(3):
            prompt = self._generate_candidate_prompt(
                certification_code=selected_certification.code,
                certification_title=selected_certification.title,
                mode=mode,
                domain=selected_domain,
                objective=objective,
                difficulty=resolved_difficulty,
                question_type=resolved_question_type,
                evidence=evidence,
                previous_failure=previous_failure,
            )
            try:
                raw = self.client.chat_json(
                    _QUESTION_SYSTEM,
                    prompt,
                    schema,
                    think=False,
                    temperature=0,
                )
                proposed = QuestionCandidate.model_validate(raw)
                validate_candidate(
                    proposed,
                    evidence,
                    certification_code=selected_certification.code,
                    learning_objective=objective,
                    required_domain=selected_domain,
                    required_module=intended_module,
                    required_topic=(
                        objective if resolved_question_type == "standard" else None
                    ),
                    required_difficulty=resolved_difficulty,
                    required_question_type=resolved_question_type,
                )
                review = self._validate_with_model(proposed, evidence)
                validate_llm_review(proposed, review)
                validate_session_diversity(
                    proposed,
                    certification_code=selected_certification.code,
                    learning_objective=objective,
                    recent_concepts=self._recent_concepts,
                )
                candidate = proposed
                break
            except (ValidationError, QuizReliabilityError, OllamaError) as exc:
                last_error = exc
                previous_failure = str(exc)[:400]

        if candidate is None:
            raise QuizGenerationError(
                f"Could not generate a validated question: {last_error}"
            )

        canonical = freeze_candidate(
            candidate,
            certification_code=selected_certification.code,
            learning_objective=objective,
            evidence=evidence,
        )
        supporting_evidence = [
            chunk
            for chunk in evidence
            if chunk["chunk_id"] in canonical.supporting_source_ids
        ]
        presentation_order = self._presentation_order(canonical)

        final: GeneratedQuiz | None = None
        explanation_failure: str | None = None
        for repair_attempt in range(5):
            try:
                draft = self._explain(
                    canonical,
                    supporting_evidence,
                    previous_failure=explanation_failure,
                    repair_attempt=repair_attempt,
                )
                final = build_final_quiz(canonical, presentation_order, draft)
                break
            except (ValidationError, QuizReliabilityError, OllamaError) as exc:
                last_error = exc
                explanation_failure = str(exc)[:400]
        if final is None:
            # Explanation prose is presentation data. A fully validated and frozen
            # question must not be discarded because a small local model repeatedly
            # missed one wording marker in that final prose-only step.
            final = build_final_quiz(
                canonical,
                presentation_order,
                self._fallback_explanation(canonical),
            )

        source_urls = list(
            dict.fromkeys(
                str(chunk["source"])
                for chunk in evidence
                if chunk["chunk_id"] in canonical.supporting_source_ids
                and str(chunk.get("source", "")).startswith("https://")
            )
        )
        final = GeneratedQuiz.model_validate(
            {**final.model_dump(mode="json"), "source_urls": source_urls}
        )
        assert_final_consistency(final)
        question_id = uuid.uuid4().hex[:12]
        self.questions.save(question_id, final.model_dump(mode="json"))
        mark_presented = getattr(self.questions, "mark_presented", None)
        if callable(mark_presented):
            mark_presented(question_id)
        self._recent_objectives.append(
            self._objective_key(selected_certification.code, objective)
        )
        self._recent_concepts.append(
            concept_signature(
                candidate,
                certification_code=selected_certification.code,
                learning_objective=objective,
            )
        )
        for source_id in canonical.supporting_source_ids:
            self._recent_chunk_ids.append(source_id)
        return self._public_question(question_id, final)

    @staticmethod
    def _public_question(question_id: str, final: GeneratedQuiz) -> PublicQuestion:
        canonical = final.canonical
        options_by_id = {option.id: option for option in canonical.options}
        return PublicQuestion(
            question_id=question_id,
            certification_code=canonical.certification_code,
            question_type=canonical.question_type,
            case_study=canonical.case_study,
            question=canonical.question,
            options=[options_by_id[option_id] for option_id in final.presentation_option_ids],
            learning_objective=canonical.learning_objective,
            blueprint_mappings=list(canonical.blueprint_mappings),
            topic=canonical.topic,
            domain=canonical.domain,
            difficulty=canonical.difficulty,
            supporting_source_ids=list(canonical.supporting_source_ids),
        )

    def answer(
        self,
        question_id: str,
        selected_option_id: str,
        elapsed_seconds: float | None = None,
    ) -> dict:
        stored = self.questions.get(question_id)
        if not stored:
            raise KeyError("Unknown question_id")
        try:
            question = GeneratedQuiz.model_validate(stored)
            assert_final_consistency(question)
        except (ValidationError, QuizReliabilityError) as exc:
            # Legacy or tampered questions are never shown with potentially stale
            # explanations. The learner must generate a new validated question.
            raise KeyError("Question is not a valid frozen artifact") from exc
        canonical = question.canonical
        if selected_option_id not in {option.id for option in canonical.options}:
            raise KeyError("Unknown option ID")
        correct = selected_option_id == canonical.correct_option_id
        options_by_id = {option.id: option for option in canonical.options}
        record_arguments = {
            "certification_code": canonical.certification_code,
            "learning_objective": canonical.learning_objective,
            "question_id": question_id,
            "selected_option_id": selected_option_id,
            "correct_option_id": canonical.correct_option_id,
            "selected_option_text": options_by_id[selected_option_id].text,
            "correct_option_text": options_by_id[canonical.correct_option_id].text,
            "elapsed_seconds": elapsed_seconds,
        }
        if callable(getattr(self.progress, "objective_priorities", None)):
            progress = self.progress.record(
                canonical.domain,
                canonical.topic,
                correct,
                **record_arguments,
            )
        else:
            progress = self.progress.record(canonical.domain, canonical.topic, correct)
        record_attempt = getattr(self.questions, "record_attempt", None)
        if callable(record_attempt):
            record_attempt(question_id, correct)
        explanations = {
            item.option_id: item.explanation for item in question.option_explanations
        }
        weakest = getattr(self.progress, "weakest_objective", None)
        next_focus = weakest(canonical.certification_code) if callable(weakest) else None
        return {
            "correct": correct,
            "selected_option_id": selected_option_id,
            "correct_option_id": canonical.correct_option_id,
            "explanation": question.explanation,
            "option_explanations": [
                item.model_dump(mode="json") for item in question.option_explanations
            ],
            "topic": canonical.topic,
            "domain": canonical.domain,
            "supporting_source_ids": list(canonical.supporting_source_ids),
            "source_urls": list(question.source_urls),
            "decisive_clue": question.decisive_clue,
            "learning_rule": question.learning_rule,
            "selected_option_feedback": explanations.get(selected_option_id, ""),
            "correct_option_feedback": explanations.get(
                canonical.correct_option_id,
                "",
            ),
            "takeaway": question.takeaway,
            "next_focus": next_focus,
            "progress": progress,
        }
