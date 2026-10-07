from __future__ import annotations

import hashlib
import json
import re
import statistics
from typing import Iterable

from .schemas import (
    BlueprintSourceMapping,
    CanonicalQuestion,
    ExplanationDraft,
    GeneratedQuiz,
    OptionExplanation,
    QuestionCandidate,
    QuestionValidation,
)


class QuizReliabilityError(RuntimeError):
    pass


_ALIAS_GROUPS = (
    frozenset({"azure ai search", "azure cognitive search", "azure search"}),
    frozenset({"microsoft entra id", "azure active directory", "azure ad"}),
    frozenset({"azure monitor logs", "log analytics"}),
)
_STOPWORDS = {
    "azure",
    "microsoft",
    "service",
    "solution",
    "option",
    "using",
    "with",
    "from",
    "that",
    "this",
    "database",
}
_AMBIGUOUS_VECTOR_TERMS = ("semantic search", "vector similarity", "vector search")
_VECTOR_DISCRIMINATORS = (
    "relational",
    "using sql",
    "sql queries",
    "alongside",
    "pgvector",
    "postgresql",
    "search index",
    "hybrid search",
    "semantic rank",
    "nosql",
    "filterable",
)
_LETTER_REFERENCE = re.compile(
    r"\b(?:option|answer|choice)\s*(?:is\s*)?[A-D]\b|"
    r"\bcorrect\s+answer\s+is\s+[A-D]\b",
    re.IGNORECASE,
)
_STABLE_ID_REFERENCE = re.compile(r"\bopt_[1-9][0-9]*\b", re.IGNORECASE)
_UNBOUND_PRODUCT_REFERENCE = re.compile(
    r"\b(?:Azure|Microsoft)\b|\bCosmos\s+DB\b",
    re.IGNORECASE,
)
_BROAD_BLUEPRINT_QUESTION = re.compile(
    r"\b(?:which|what)\b.{0,80}\b(?:proficiency|proficiencies|skills|skill bundles|knowledge areas)\b"
    r".{0,80}\b(?:required|needed|need)\b|"
    r"\b(?:required|needed)\b.{0,80}\b(?:proficiency|proficiencies|skills|skill bundles|knowledge areas)\b",
    re.IGNORECASE,
)
_FIT_MARKERS = (
    "because",
    "fits",
    "meets",
    "provides",
    "required",
    "satisfies",
    "supports",
)
_CONTRAST_MARKERS = (
    "does not",
    "doesn't",
    "instead",
    "lacks",
    "not ",
    "rather",
    "unlike",
    "without",
)
_ALTERNATIVE_USE_MARKERS = (
    "appropriate when",
    "best for",
    "designed for",
    "instead",
    "intended for",
    "suited to",
    "use it",
    "would fit",
)


def _normalized(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _content_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9.+#-]{3,}", value.casefold())
        if token not in _STOPWORDS
    }


def _option_identities(text: str) -> set[str]:
    normalized = _normalized(text)
    identities = {normalized}
    for index, group in enumerate(_ALIAS_GROUPS):
        if any(alias in normalized for alias in group):
            identities.add(f"alias-group-{index}")
    return identities


def _candidate_payload(candidate: QuestionCandidate) -> dict:
    return {
        "question_type": candidate.question_type,
        "case_study": (
            candidate.case_study.model_dump(mode="json")
            if candidate.case_study is not None
            else None
        ),
        "question": candidate.question,
        "options": [option.model_dump(mode="json") for option in candidate.options],
        "correct_option_id": candidate.correct_option_id,
        "supporting_source_ids": candidate.supporting_source_ids,
        "topic": candidate.topic,
        "domain": candidate.domain,
        "difficulty": candidate.difficulty,
    }


def question_fingerprint(candidate: QuestionCandidate) -> str:
    serialized = json.dumps(
        _candidate_payload(candidate),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def canonical_fingerprint(question: CanonicalQuestion) -> str:
    payload = {
        "certification_code": question.certification_code,
        "learning_objective": question.learning_objective,
        "question_type": question.question_type,
        "case_study": (
            question.case_study.model_dump(mode="json")
            if question.case_study is not None
            else None
        ),
        "question": question.question,
        "options": [option.model_dump(mode="json") for option in question.options],
        "correct_option_id": question.correct_option_id,
        "supporting_source_ids": list(question.supporting_source_ids),
        "blueprint_mappings": [
            item.model_dump(mode="json") for item in question.blueprint_mappings
        ],
        "topic": question.topic,
        "domain": question.domain,
        "difficulty": question.difficulty,
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def concept_signature(
    candidate: QuestionCandidate,
    *,
    certification_code: str,
    learning_objective: str,
) -> tuple[str, str, str, frozenset[str]]:
    correct = next(
        option for option in candidate.options if option.id == candidate.correct_option_id
    )
    tokens = frozenset(
        _content_tokens(
            " ".join(
                (
                    learning_objective,
                    candidate.topic,
                    candidate.question,
                    correct.text,
                )
            )
        )
    )
    return (
        certification_code.upper(),
        _normalized(learning_objective),
        _normalized(correct.text),
        tokens,
    )


def validate_session_diversity(
    candidate: QuestionCandidate,
    *,
    certification_code: str,
    learning_objective: str,
    recent_concepts: Iterable[tuple[str, str, str, frozenset[str]]],
) -> None:
    current = concept_signature(
        candidate,
        certification_code=certification_code,
        learning_objective=learning_objective,
    )
    current_certification, current_objective, current_answer, current_tokens = current
    for prior_certification, prior_objective, prior_answer, prior_tokens in recent_concepts:
        if prior_certification != current_certification:
            continue
        union = current_tokens | prior_tokens
        similarity = len(current_tokens & prior_tokens) / max(len(union), 1)
        same_boundary = current_answer == prior_answer and (
            current_objective == prior_objective or similarity >= 0.34
        )
        near_paraphrase = similarity >= 0.72
        if same_boundary or near_paraphrase:
            raise QuizReliabilityError(
                "Question repeats a concept already tested in this session."
            )


def validate_candidate(
    candidate: QuestionCandidate,
    evidence: list[dict],
    *,
    certification_code: str,
    learning_objective: str,
    required_domain: str | None = None,
    required_module: str | None = None,
    required_topic: str | None = None,
    required_difficulty: str | None = None,
    required_question_type: str | None = None,
) -> None:
    if candidate.status != "ok":
        raise QuizReliabilityError("Model reported insufficient context.")
    option_ids = [option.id for option in candidate.options]
    if option_ids != ["opt_1", "opt_2", "opt_3", "opt_4"]:
        raise QuizReliabilityError(
            "Candidate options must use stable IDs opt_1 through opt_4 exactly once."
        )
    if candidate.correct_option_id not in option_ids:
        raise QuizReliabilityError("correct_option_id does not exist.")

    seen_identities: set[str] = set()
    for option in candidate.options:
        identities = _option_identities(option.text)
        if identities & seen_identities:
            raise QuizReliabilityError("Options contain duplicate or equivalent aliases.")
        seen_identities.update(identities)

    evidence_by_id = {str(item.get("chunk_id")): item for item in evidence}
    if not candidate.supporting_source_ids:
        raise QuizReliabilityError("Question has no supporting source evidence.")
    if len(set(candidate.supporting_source_ids)) != len(candidate.supporting_source_ids):
        raise QuizReliabilityError("Question repeats a supporting source ID.")
    if any(source_id not in evidence_by_id for source_id in candidate.supporting_source_ids):
        raise QuizReliabilityError("Question cited evidence that was not retrieved.")
    if candidate.confidence < 0.70:
        raise QuizReliabilityError("Model confidence is below the reliability threshold.")
    if required_domain and _normalized(candidate.domain) != _normalized(required_domain):
        raise QuizReliabilityError("Question drifted outside the selected exam domain.")
    if required_difficulty and candidate.difficulty != required_difficulty:
        raise QuizReliabilityError("Question did not respect the selected difficulty.")
    if required_question_type and candidate.question_type != required_question_type:
        raise QuizReliabilityError("Question did not respect the selected format.")

    cited = [evidence_by_id[source_id] for source_id in candidate.supporting_source_ids]
    for chunk in cited:
        metadata = chunk.get("metadata") or {}
        if metadata.get("blueprint_aligned") is not True:
            raise QuizReliabilityError(
                "Question evidence is not mapped to an official measured objective."
            )
        blueprint_url = str(metadata.get("blueprint_source_url") or "")
        if not (
            blueprint_url.startswith(
                "https://learn.microsoft.com/credentials/certifications/resources/study-guides/"
            )
            and blueprint_url.rstrip("/").endswith(f"/{certification_code.casefold()}")
        ):
            raise QuizReliabilityError("Question has no authoritative certification blueprint.")
        source_url = str(chunk.get("source") or metadata.get("source_url") or "")
        if not source_url.startswith("https://learn.microsoft.com/"):
            raise QuizReliabilityError("Question is not grounded in a Microsoft Learn source.")
        skill_objective = str(metadata.get("skill_objective") or "")
        if _normalized(skill_objective) != _normalized(learning_objective):
            raise QuizReliabilityError(
                "Question evidence is outside the selected measured objective."
            )
        exam_domain = str(metadata.get("exam_domain") or "")
        if required_domain and _normalized(exam_domain) != _normalized(required_domain):
            raise QuizReliabilityError(
                "Question evidence is outside the selected blueprint domain."
            )
        scoped_certification = metadata.get("certification")
        if scoped_certification and scoped_certification != certification_code:
            raise QuizReliabilityError("Retrieved evidence belongs to another certification.")
        scoped_domain = metadata.get("domain")
        if (
            required_domain
            and scoped_domain not in {None, "", "unknown"}
            and _normalized(str(scoped_domain)) != _normalized(required_domain)
        ):
            raise QuizReliabilityError("Retrieved evidence belongs to another exam domain.")
        scoped_module = metadata.get("module")
        if (
            required_module
            and scoped_module
            and _normalized(str(scoped_module)) != _normalized(required_module)
        ):
            raise QuizReliabilityError("Retrieved evidence belongs to another module.")
        if required_topic:
            scoped_topics = {
                _normalized(str(value))
                for value in (
                    metadata.get("learning_objective"),
                    metadata.get("topic"),
                )
                if value
            }
            if scoped_topics and _normalized(required_topic) not in scoped_topics:
                raise QuizReliabilityError("Retrieved evidence belongs to another topic.")

    objective = _normalized(learning_objective)
    evidence_objectives = {
        _normalized(str(value))
        for chunk in cited
        for value in (
            (chunk.get("metadata") or {}).get("learning_objective"),
            (chunk.get("metadata") or {}).get("topic"),
        )
        if value
    }
    if evidence_objectives and objective not in evidence_objectives:
        raise QuizReliabilityError("Question evidence drifted from the selected objective.")

    if candidate.question_type == "case_study":
        if candidate.case_study is None:
            raise QuizReliabilityError("Case-study question has no scenario.")
        if len(candidate.supporting_source_ids) < 2:
            raise QuizReliabilityError("Case-study question needs at least two sources.")
    elif candidate.case_study is not None:
        raise QuizReliabilityError("Standard question unexpectedly contains a case study.")

    stem = _normalized(candidate.question)
    if _BROAD_BLUEPRINT_QUESTION.search(candidate.question):
        raise QuizReliabilityError(
            "Broad blueprint-list questions do not establish one decision boundary."
        )
    if any(term in stem for term in _AMBIGUOUS_VECTOR_TERMS) and not any(
        term in stem for term in _VECTOR_DISCRIMINATORS
    ):
        raise QuizReliabilityError(
            "Generic vector-search wording lacks a discriminating requirement."
        )

    correct = next(
        option for option in candidate.options if option.id == candidate.correct_option_id
    )
    evidence_text = " ".join(str(chunk.get("text") or "") for chunk in cited)
    if not (_content_tokens(correct.text) & _content_tokens(evidence_text)):
        raise QuizReliabilityError("Correct option is not lexically grounded in cited evidence.")

    word_counts = {option.id: len(option.text.split()) for option in candidate.options}
    counts = list(word_counts.values())
    median_words = statistics.median(counts)
    correct_words = word_counts[candidate.correct_option_id]
    distractor_words = [
        count for option_id, count in word_counts.items()
        if option_id != candidate.correct_option_id
    ]
    if (
        correct_words >= 8
        and correct_words > median_words * 1.65
        and correct_words >= max(distractor_words) + 5
    ):
        raise QuizReliabilityError("Correct option is an obvious length outlier.")
    shortest = min(counts)
    longest = max(counts)
    if shortest > 0 and longest >= 12 and longest > shortest * 2.75:
        raise QuizReliabilityError("Answer choices have excessively uneven lengths.")


def validate_llm_review(
    candidate: QuestionCandidate,
    review: QuestionValidation,
) -> None:
    expected_fingerprint = question_fingerprint(candidate)
    if review.question_fingerprint != expected_fingerprint:
        raise QuizReliabilityError("Validation result belongs to another question state.")
    if review.correct_option_id != candidate.correct_option_id:
        raise QuizReliabilityError("Validator tried to change the correct option.")
    if review.verdict != "accept" or review.issues:
        details = "; ".join(review.issues) or "validator rejected the candidate"
        raise QuizReliabilityError(details)
    if review.supported_option_ids != [candidate.correct_option_id]:
        raise QuizReliabilityError("Validator did not find exactly one supported answer.")
    assessment_ids = [item.option_id for item in review.option_assessments]
    candidate_ids = [item.id for item in candidate.options]
    if len(set(assessment_ids)) != len(candidate_ids) or set(assessment_ids) != set(
        candidate_ids
    ):
        raise QuizReliabilityError("Validator did not assess every option exactly once.")
    supported_assessments = [
        item.option_id
        for item in review.option_assessments
        if item.verdict == "supported"
    ]
    if supported_assessments != [candidate.correct_option_id]:
        raise QuizReliabilityError(
            "More than one option is valid or the keyed answer is not uniquely supported."
        )
    cited_ids = set(candidate.supporting_source_ids)
    for assessment in review.option_assessments:
        if any(source_id not in cited_ids for source_id in assessment.supporting_source_ids):
            raise QuizReliabilityError("Validator used evidence outside the frozen source set.")
        if assessment.verdict == "supported" and not assessment.supporting_source_ids:
            raise QuizReliabilityError("Supported option has no source evidence.")
    if set(review.supporting_source_ids) != set(candidate.supporting_source_ids):
        raise QuizReliabilityError("Validator changed the supporting evidence set.")


def freeze_candidate(
    candidate: QuestionCandidate,
    *,
    certification_code: str,
    learning_objective: str,
    evidence: list[dict],
) -> CanonicalQuestion:
    evidence_by_id = {str(item.get("chunk_id")): item for item in evidence}
    mappings = []
    for source_id in candidate.supporting_source_ids:
        chunk = evidence_by_id[source_id]
        metadata = chunk.get("metadata") or {}
        mappings.append(
            BlueprintSourceMapping(
                exam_domain=str(metadata["exam_domain"]),
                skill_objective=str(metadata["skill_objective"]),
                learn_source_id=source_id,
                learn_url=str(chunk.get("source") or metadata["source_url"]),
                learn_unit=(str(metadata.get("unit")) if metadata.get("unit") else None),
                blueprint_url=str(metadata["blueprint_source_url"]),
            )
        )
    provisional = CanonicalQuestion(
        question_fingerprint="0" * 64,
        certification_code=certification_code,
        learning_objective=learning_objective,
        question_type=candidate.question_type,
        case_study=candidate.case_study,
        question=candidate.question,
        options=tuple(candidate.options),
        correct_option_id=candidate.correct_option_id,
        supporting_source_ids=tuple(candidate.supporting_source_ids),
        blueprint_mappings=tuple(mappings),
        topic=candidate.topic,
        domain=candidate.domain,
        difficulty=candidate.difficulty,
    )
    return CanonicalQuestion.model_validate(
        {
            **provisional.model_dump(mode="json"),
            "question_fingerprint": canonical_fingerprint(provisional),
        }
    )


def _validate_rationale(
    rationale: str,
    *,
    option_texts: Iterable[str],
    is_correct: bool,
) -> None:
    if _LETTER_REFERENCE.search(rationale):
        raise QuizReliabilityError("Explanation contains a presentation-letter reference.")
    if _STABLE_ID_REFERENCE.search(rationale):
        raise QuizReliabilityError("Explanation leaked an internal option ID.")
    if _UNBOUND_PRODUCT_REFERENCE.search(rationale):
        raise QuizReliabilityError(
            "Explanation rationale names a product instead of using the frozen option binding."
        )
    normalized_rationale = _normalized(rationale)
    if any(
        _normalized(option_text) in normalized_rationale
        for option_text in option_texts
        if len(_normalized(option_text)) >= 5
    ):
        raise QuizReliabilityError("Explanation repeated option text outside its frozen binding.")
    if "correct answer" in normalized_rationale:
        raise QuizReliabilityError("Explanation tried to independently identify an answer.")
    if len(rationale.split()) < 9:
        raise QuizReliabilityError("Explanation is too brief to teach the decision boundary.")
    if is_correct:
        if not any(marker in normalized_rationale for marker in _FIT_MARKERS):
            raise QuizReliabilityError(
                "Correct-option explanation does not connect capability to requirement."
            )
    else:
        if not any(marker in normalized_rationale for marker in _CONTRAST_MARKERS):
            raise QuizReliabilityError(
                "Distractor explanation does not state why it fails the scenario."
            )
        if not any(marker in normalized_rationale for marker in _ALTERNATIVE_USE_MARKERS):
            raise QuizReliabilityError(
                "Distractor explanation does not teach its alternative use boundary."
            )


def build_final_quiz(
    canonical: CanonicalQuestion,
    presentation_option_ids: tuple[str, ...],
    draft: ExplanationDraft,
) -> GeneratedQuiz:
    if canonical_fingerprint(canonical) != canonical.question_fingerprint:
        raise QuizReliabilityError("Canonical question changed after it was frozen.")
    canonical_ids = tuple(option.id for option in canonical.options)
    if (
        len(presentation_option_ids) != len(canonical_ids)
        or set(presentation_option_ids) != set(canonical_ids)
    ):
        raise QuizReliabilityError("Presentation order does not match the canonical options.")
    if draft.question_fingerprint != canonical.question_fingerprint:
        raise QuizReliabilityError("Explanation belongs to another question state.")
    if draft.correct_option_id != canonical.correct_option_id:
        raise QuizReliabilityError("Explanation tried to change the correct option.")
    rationales = {item.option_id: item for item in draft.rationales}
    if len(rationales) != len(draft.rationales) or set(rationales) != set(canonical_ids):
        raise QuizReliabilityError("Explanation does not bind exactly once to every option.")
    option_texts = [option.text for option in canonical.options]
    for item in rationales.values():
        _validate_rationale(
            item.rationale,
            option_texts=option_texts,
            is_correct=item.option_id == canonical.correct_option_id,
        )
    normalized_rationales = {
        _normalized(item.rationale) for item in rationales.values()
    }
    if len(normalized_rationales) != len(canonical_ids):
        raise QuizReliabilityError(
            "Explanation repeats a generic rationale instead of distinguishing options."
        )

    options_by_id = {option.id: option for option in canonical.options}
    correct_option = options_by_id[canonical.correct_option_id]
    main = (
        f"{correct_option.text} is correct. "
        f"{rationales[canonical.correct_option_id].rationale.strip()}"
    )
    explanations = tuple(
        OptionExplanation(
            option_id=option_id,
            explanation=(
                f"{options_by_id[option_id].text}: "
                f"{rationales[option_id].rationale.strip()}"
            ),
        )
        for option_id in presentation_option_ids
    )
    decisive_clue = draft.decisive_clue.strip() or (
        "Focus on the explicit operating constraint that only one capability "
        "satisfies without an unstated assumption."
    )
    learning_rule = draft.learning_rule.strip() or (
        rationales[canonical.correct_option_id].rationale.strip()
    )
    takeaway = draft.takeaway.strip() or (
        "Match each capability to the stated requirement, then eliminate choices "
        "that solve a different problem."
    )
    final = GeneratedQuiz(
        canonical=canonical,
        presentation_option_ids=presentation_option_ids,
        explanation=main,
        option_explanations=explanations,
        decisive_clue=decisive_clue,
        learning_rule=learning_rule,
        takeaway=takeaway,
    )
    assert_final_consistency(final)
    return final


def assert_final_consistency(question: GeneratedQuiz) -> None:
    canonical = question.canonical
    if canonical_fingerprint(canonical) != canonical.question_fingerprint:
        raise QuizReliabilityError("Stored canonical question fingerprint is stale.")
    canonical_option_ids = tuple(option.id for option in canonical.options)
    canonical_ids = set(canonical_option_ids)
    if len(canonical_option_ids) != 4 or len(canonical_ids) != 4:
        raise QuizReliabilityError("Stored question has duplicate or missing option IDs.")
    seen_identities: set[str] = set()
    for option in canonical.options:
        identities = _option_identities(option.text)
        if identities & seen_identities:
            raise QuizReliabilityError(
                "Stored question has duplicate or equivalent option text."
            )
        seen_identities.update(identities)
    if not canonical.supporting_source_ids:
        raise QuizReliabilityError("Stored question has no supporting source evidence.")
    if len(set(canonical.supporting_source_ids)) != len(
        canonical.supporting_source_ids
    ):
        raise QuizReliabilityError("Stored question has duplicate source IDs.")
    mapping_source_ids = [item.learn_source_id for item in canonical.blueprint_mappings]
    if (
        len(set(mapping_source_ids)) != len(canonical.supporting_source_ids)
        or set(mapping_source_ids) != set(canonical.supporting_source_ids)
    ):
        raise QuizReliabilityError(
            "Stored question lacks an exact blueprint mapping for every source."
        )
    for mapping in canonical.blueprint_mappings:
        if _normalized(mapping.exam_domain) != _normalized(canonical.domain):
            raise QuizReliabilityError("Stored blueprint domain does not match the question.")
        if _normalized(mapping.skill_objective) != _normalized(
            canonical.learning_objective
        ):
            raise QuizReliabilityError(
                "Stored blueprint objective does not match the question."
            )
    if (
        len(question.presentation_option_ids) != len(canonical_option_ids)
        or len(set(question.presentation_option_ids)) != len(canonical_option_ids)
        or set(question.presentation_option_ids) != canonical_ids
    ):
        raise QuizReliabilityError("Stored presentation options do not match the question.")
    if canonical.correct_option_id not in canonical_ids:
        raise QuizReliabilityError("Stored correct option is missing.")
    options_by_id = {option.id: option for option in canonical.options}
    expected_prefix = f"{options_by_id[canonical.correct_option_id].text} is correct. "
    if not question.explanation.startswith(expected_prefix):
        raise QuizReliabilityError("Stored explanation identifies a different answer.")
    explanation_ids = [item.option_id for item in question.option_explanations]
    if tuple(explanation_ids) != question.presentation_option_ids:
        raise QuizReliabilityError("Stored option explanations use stale presentation order.")
    for item in question.option_explanations:
        expected = f"{options_by_id[item.option_id].text}: "
        if not item.explanation.startswith(expected):
            raise QuizReliabilityError("Stored explanation references a nonexistent option.")
