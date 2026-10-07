from __future__ import annotations

from copy import deepcopy
import re
import unittest

from pydantic import ValidationError

from backend.quiz_engine import QuizEngine
from backend.quiz_reliability import (
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
from backend.schemas import ExplanationDraft, QuestionCandidate, QuestionValidation


def _evidence(*, certification: str = "AI-200") -> list[dict]:
    return [
        {
            "score": 1.0,
            "chunk_id": "source-postgresql",
            "source": "https://learn.microsoft.com/azure/postgresql/vector-search",
            "text": (
                "Azure Database for PostgreSQL supports the pgvector extension "
                "to store embeddings with relational data and query vectors using SQL."
            ),
            "metadata": {
                "certification": certification,
                "domain": "Use Azure data services",
                "exam_domain": "Use Azure data services",
                "topic": "Vector storage",
                "learning_objective": "Vector storage",
                "skill_group": "Implement data storage solutions",
                "skill_objective": "Vector storage",
                "unit": "query-vectors",
                "blueprint_aligned": True,
                "blueprint_source_url": (
                    "https://learn.microsoft.com/credentials/certifications/"
                    "resources/study-guides/ai-200"
                ),
            },
        }
    ]


def _candidate() -> QuestionCandidate:
    return QuestionCandidate.model_validate(
        {
            "status": "ok",
            "question_type": "standard",
            "case_study": None,
            "question": (
                "You must store embeddings alongside relational application data "
                "and query them using SQL with pgvector. Which service should you use?"
            ),
            "options": [
                {"id": "opt_1", "text": "Azure Container Instances"},
                {"id": "opt_2", "text": "Azure SQL Database"},
                {"id": "opt_3", "text": "Azure Table Storage"},
                {"id": "opt_4", "text": "Azure Database for PostgreSQL"},
            ],
            "correct_option_id": "opt_4",
            "supporting_source_ids": ["source-postgresql"],
            "topic": "Vector storage",
            "domain": "Use Azure data services",
            "difficulty": "easy",
            "confidence": 0.96,
        }
    )


def _canonical():
    candidate = _candidate()
    validate_candidate(
        candidate,
        _evidence(),
        certification_code="AI-200",
        learning_objective="Vector storage",
        required_domain="Use Azure data services",
        required_difficulty="easy",
        required_question_type="standard",
    )
    return freeze_candidate(
        candidate,
        certification_code="AI-200",
        learning_objective="Vector storage",
        evidence=_evidence(),
    )


def _draft(canonical=None) -> ExplanationDraft:
    canonical = canonical or _canonical()
    return ExplanationDraft.model_validate(
        {
            "question_fingerprint": canonical.question_fingerprint,
            "correct_option_id": canonical.correct_option_id,
            "decisive_clue": "The relational transaction requirement decides the answer.",
            "learning_rule": "Keep vector data relational when SQL transactions and joins are required.",
            "takeaway": "Let the data model and transaction boundary drive the service choice.",
            "rationales": [
                {
                    "option_id": "opt_1",
                    "rationale": "This does not store relational vectors; it is designed for short-lived container compute.",
                },
                {
                    "option_id": "opt_2",
                    "rationale": "This does not establish the required extension; it is suited to other managed SQL workloads.",
                },
                {
                    "option_id": "opt_3",
                    "rationale": "This does not provide relational SQL semantics; it is intended for key-value style storage.",
                },
                {
                    "option_id": "opt_4",
                    "rationale": "It provides the required extension with relational storage and direct SQL vector querying.",
                },
            ],
        }
    )


class _Store:
    def __init__(self):
        self.saved = {}

    def save(self, question_id, payload):
        self.saved[question_id] = payload

    def get(self, question_id):
        return self.saved.get(question_id)


class _Progress:
    def record(self, domain, topic, correct):
        return {"asked": 1, "correct": int(correct), "accuracy": float(correct)}


class _Patterns:
    def prompt_hint(self, question_type):
        return ""


class _Rag:
    uses_microsoft_learn = False

    def __init__(self):
        self.items = deepcopy(_evidence())
        self.search_calls = 0

    def search(
        self,
        query,
        top_k,
        domain=None,
        certification_code="AI-103",
        learning_objective=None,
    ):
        self.search_calls += 1
        return deepcopy(_evidence())


class _ScriptedClient:
    def __init__(self):
        ambiguous = _candidate().model_copy(
            update={
                "question": (
                    "Which Azure service supports semantic search with vector similarity?"
                )
            }
        )
        self.candidates = [
            ambiguous.model_dump(mode="json"),
            _candidate().model_dump(mode="json"),
        ]
        self.question_calls = 0
        self.validation_calls = 0
        self.explanation_calls = 0

    def chat_json(self, system, user, schema, **kwargs):
        properties = schema.get("properties", {})
        fingerprint = re.search(r"\b[0-9a-f]{64}\b", user)
        if "verdict" in properties:
            self.validation_calls += 1
            return {
                "question_fingerprint": fingerprint.group(0),
                "verdict": "accept",
                "correct_option_id": "opt_4",
                "supported_option_ids": ["opt_4"],
                "option_assessments": [
                    {
                        "option_id": option["id"],
                        "verdict": (
                            "supported" if option["id"] == "opt_4" else "not_established"
                        ),
                        "supporting_source_ids": (
                            ["source-postgresql"] if option["id"] == "opt_4" else []
                        ),
                    }
                    for option in _candidate().model_dump(mode="json")["options"]
                ],
                "supporting_source_ids": ["source-postgresql"],
                "issues": [],
            }
        if "rationales" in properties:
            self.explanation_calls += 1
            draft = _draft()
            return {
                **draft.model_dump(mode="json"),
                "question_fingerprint": fingerprint.group(0),
            }
        self.question_calls += 1
        return self.candidates.pop(0)


class QuizReliabilityTests(unittest.TestCase):
    def test_rejects_two_blueprint_valid_answers(self) -> None:
        payload = _candidate().model_dump(mode="json")
        payload["question"] = "Which required AI-200 proficiency bundle should you have?"
        payload["options"] = [
            {"id": "opt_1", "text": "Messaging, containers, and service SDKs"},
            {"id": "opt_2", "text": "Office macros and desktop publishing"},
            {"id": "opt_3", "text": "Game rendering and shader authoring"},
            {"id": "opt_4", "text": "Data services, Python, and vector databases"},
        ]
        payload["correct_option_id"] = "opt_1"
        candidate = QuestionCandidate.model_validate(payload)
        review = QuestionValidation.model_validate(
            {
                "question_fingerprint": question_fingerprint(candidate),
                "verdict": "accept",
                "correct_option_id": "opt_1",
                "supported_option_ids": ["opt_1", "opt_4"],
                "option_assessments": [
                    {
                        "option_id": option_id,
                        "verdict": (
                            "supported" if option_id in {"opt_1", "opt_4"} else "not_established"
                        ),
                        "supporting_source_ids": (
                            ["source-postgresql"]
                            if option_id in {"opt_1", "opt_4"}
                            else []
                        ),
                    }
                    for option_id in ("opt_1", "opt_2", "opt_3", "opt_4")
                ],
                "supporting_source_ids": ["source-postgresql"],
                "issues": [],
            }
        )

        with self.assertRaisesRegex(QuizReliabilityError, "decision boundary"):
            validate_candidate(
                candidate,
                _evidence(),
                certification_code="AI-200",
                learning_objective="Vector storage",
                required_domain="Use Azure data services",
            )
        with self.assertRaisesRegex(QuizReliabilityError, "exactly one"):
            validate_llm_review(candidate, review)

    def test_rejects_content_outside_measured_objective(self) -> None:
        evidence = deepcopy(_evidence())
        evidence[0]["metadata"]["blueprint_aligned"] = False

        with self.assertRaisesRegex(QuizReliabilityError, "measured objective"):
            validate_candidate(
                _candidate(),
                evidence,
                certification_code="AI-200",
                learning_objective="Vector storage",
                required_domain="Use Azure data services",
            )

    def test_rejects_duplicate_concept_in_same_session(self) -> None:
        first = _candidate()
        second = first.model_copy(
            update={
                "question": (
                    "An app must keep relational records and embeddings together, "
                    "then issue pgvector similarity queries through SQL. Which service fits?"
                )
            }
        )
        recent = [
            concept_signature(
                first,
                certification_code="AI-200",
                learning_objective="Vector storage",
            )
        ]

        with self.assertRaisesRegex(QuizReliabilityError, "already tested"):
            validate_session_diversity(
                second,
                certification_code="AI-200",
                learning_objective="Vector storage",
                recent_concepts=recent,
            )

    def test_explanation_distinguishes_all_container_services(self) -> None:
        evidence = deepcopy(_evidence())
        evidence[0]["text"] = (
            "Azure Container Apps provides managed serverless microservices with KEDA "
            "scaling. Azure Kubernetes Service provides direct Kubernetes control. "
            "Azure Container Registry stores images. Azure Container Instances runs "
            "simple isolated containers with less orchestration."
        )
        metadata = evidence[0]["metadata"]
        metadata["topic"] = "Managed container compute"
        metadata["domain"] = "Develop containerized solutions"
        metadata["exam_domain"] = "Develop containerized solutions"
        metadata["learning_objective"] = "Choose managed container compute"
        metadata["skill_objective"] = "Choose managed container compute"
        candidate = QuestionCandidate.model_validate(
            {
                "status": "ok",
                "question_type": "standard",
                "case_study": None,
                "question": (
                    "A team needs managed microservices, event-driven KEDA scaling, "
                    "and no Kubernetes cluster administration. Which service should it use?"
                ),
                "options": [
                    {"id": "opt_1", "text": "Azure Container Apps"},
                    {"id": "opt_2", "text": "Azure Kubernetes Service"},
                    {"id": "opt_3", "text": "Azure Container Registry"},
                    {"id": "opt_4", "text": "Azure Container Instances"},
                ],
                "correct_option_id": "opt_1",
                "supporting_source_ids": ["source-postgresql"],
                "topic": "Managed container compute",
                "domain": "Develop containerized solutions",
                "difficulty": "medium",
                "confidence": 0.97,
            }
        )
        validate_candidate(
            candidate,
            evidence,
            certification_code="AI-200",
            learning_objective="Choose managed container compute",
            required_domain="Develop containerized solutions",
        )
        canonical = freeze_candidate(
            candidate,
            certification_code="AI-200",
            learning_objective="Choose managed container compute",
            evidence=evidence,
        )
        draft = ExplanationDraft.model_validate(
            {
                "question_fingerprint": canonical.question_fingerprint,
                "correct_option_id": "opt_1",
                "decisive_clue": "No cluster administration and event scaling decide the answer.",
                "learning_rule": "Prefer managed event-driven compute when cluster control is not required.",
                "takeaway": "Operational control is the boundary between these container options.",
                "rationales": [
                    {
                        "option_id": "opt_1",
                        "rationale": "It provides managed microservices and event-driven KEDA scaling, satisfying the no-cluster-management requirement.",
                    },
                    {
                        "option_id": "opt_2",
                        "rationale": "It does not remove cluster control; use it when direct Kubernetes administration is required.",
                    },
                    {
                        "option_id": "opt_3",
                        "rationale": "It is not a runtime; use it when container images need storage and distribution.",
                    },
                    {
                        "option_id": "opt_4",
                        "rationale": "It lacks the required orchestration; it is best for simple isolated container execution.",
                    },
                ],
            }
        )

        final = build_final_quiz(
            canonical,
            ("opt_1", "opt_2", "opt_3", "opt_4"),
            draft,
        )

        rendered = [item.explanation for item in final.option_explanations]
        self.assertTrue(any("KEDA scaling" in value for value in rendered))
        self.assertTrue(any("direct Kubernetes" in value for value in rendered))
        self.assertTrue(any("not a runtime" in value for value in rendered))
        self.assertTrue(any("simple isolated" in value for value in rendered))

    def test_rejects_stored_explanation_that_claims_another_option(self) -> None:
        canonical = _canonical()
        final = build_final_quiz(
            canonical,
            ("opt_2", "opt_4", "opt_1", "opt_3"),
            _draft(canonical),
        )
        tampered = final.model_copy(
            update={"explanation": "Azure SQL Database is correct. Stale explanation."}
        )

        with self.assertRaisesRegex(QuizReliabilityError, "different answer"):
            assert_final_consistency(tampered)

    def test_shuffled_ui_order_preserves_postgresql_correct_id(self) -> None:
        canonical = _canonical()
        order = ("opt_2", "opt_1", "opt_3", "opt_4")
        final = build_final_quiz(canonical, order, _draft(canonical))
        public = QuizEngine._public_question("question-1", final)

        self.assertEqual([option.id for option in public.options], list(order))
        self.assertEqual(canonical.correct_option_id, "opt_4")
        self.assertEqual(
            next(option.text for option in canonical.options if option.id == "opt_4"),
            "Azure Database for PostgreSQL",
        )
        store = _Store()
        store.save("question-1", final.model_dump(mode="json"))
        engine = QuizEngine(None, _Rag(), _Progress(), store, patterns=_Patterns())
        self.assertTrue(engine.answer("question-1", "opt_4")["correct"])

    def test_rejects_explanation_that_mentions_nonexistent_cosmos_option(self) -> None:
        canonical = _canonical()
        payload = _draft(canonical).model_dump(mode="json")
        payload["rationales"][0]["rationale"] = (
            "Azure Cosmos DB (Option A) is intended for NoSQL workloads."
        )

        with self.assertRaisesRegex(QuizReliabilityError, "presentation-letter"):
            build_final_quiz(
                canonical,
                ("opt_1", "opt_2", "opt_3", "opt_4"),
                ExplanationDraft.model_validate(payload),
            )

    def test_rejects_duplicate_service_aliases(self) -> None:
        payload = _candidate().model_dump(mode="json")
        payload["options"][0]["text"] = "Azure AI Search"
        payload["options"][1]["text"] = "Azure Cognitive Search"

        with self.assertRaisesRegex(QuizReliabilityError, "equivalent aliases"):
            validate_candidate(
                QuestionCandidate.model_validate(payload),
                _evidence(),
                certification_code="AI-200",
                learning_objective="Vector storage",
            )

    def test_rejects_ambiguous_generic_vector_search_question(self) -> None:
        candidate = _candidate().model_copy(
            update={
                "question": "Which service supports semantic search with vector similarity?"
            }
        )

        with self.assertRaisesRegex(QuizReliabilityError, "discriminating"):
            validate_candidate(
                candidate,
                _evidence(),
                certification_code="AI-200",
                learning_objective="Vector storage",
            )

    def test_accepts_explicit_postgresql_pgvector_question(self) -> None:
        validate_candidate(
            _candidate(),
            _evidence(),
            certification_code="AI-200",
            learning_objective="Vector storage",
            required_domain="Use Azure data services",
        )

    def test_explanation_cannot_mutate_correct_option(self) -> None:
        canonical = _canonical()
        with self.assertRaises(ValidationError):
            canonical.correct_option_id = "opt_1"

        payload = _draft(canonical).model_dump(mode="json")
        payload["correct_option_id"] = "opt_1"
        with self.assertRaisesRegex(QuizReliabilityError, "change the correct"):
            build_final_quiz(
                canonical,
                ("opt_1", "opt_2", "opt_3", "opt_4"),
                ExplanationDraft.model_validate(payload),
            )

    def test_rejects_evidence_outside_certification_module_or_topic(self) -> None:
        with self.assertRaisesRegex(QuizReliabilityError, "another certification"):
            validate_candidate(
                _candidate(),
                _evidence(certification="AI-103"),
                certification_code="AI-200",
                learning_objective="Vector storage",
            )
        wrong_module = deepcopy(_evidence())
        wrong_module[0]["metadata"]["module"] = "unrelated-module"
        with self.assertRaisesRegex(QuizReliabilityError, "another module"):
            validate_candidate(
                _candidate(),
                wrong_module,
                certification_code="AI-200",
                learning_objective="Vector storage",
                required_module="postgresql-vector-search",
            )
        wrong_topic = deepcopy(_evidence())
        wrong_topic[0]["metadata"]["learning_objective"] = "Speech synthesis"
        wrong_topic[0]["metadata"]["topic"] = "Speech synthesis"
        with self.assertRaisesRegex(QuizReliabilityError, "another topic"):
            validate_candidate(
                _candidate(),
                wrong_topic,
                certification_code="AI-200",
                learning_objective="Vector storage",
                required_topic="Vector storage",
            )

    def test_stale_explanation_cannot_attach_to_new_question(self) -> None:
        canonical = _canonical()
        payload = _draft(canonical).model_dump(mode="json")
        payload["question_fingerprint"] = "0" * 64

        with self.assertRaisesRegex(QuizReliabilityError, "another question state"):
            build_final_quiz(
                canonical,
                ("opt_1", "opt_2", "opt_3", "opt_4"),
                ExplanationDraft.model_validate(payload),
            )

    def test_only_failed_candidate_is_regenerated(self) -> None:
        client = _ScriptedClient()
        rag = _Rag()
        store = _Store()
        engine = QuizEngine(client, rag, _Progress(), store, patterns=_Patterns())

        question = engine.generate(
            certification_code="AI-200",
            mode="shuffle",
            difficulty="easy",
            question_type="standard",
        )

        self.assertEqual(question.supporting_source_ids, ["source-postgresql"])
        self.assertEqual(client.question_calls, 2)
        self.assertEqual(client.validation_calls, 1)
        self.assertEqual(client.explanation_calls, 1)
        self.assertEqual(rag.search_calls, 1)
        self.assertEqual(len(store.saved), 1)
        answer = engine.answer(question.question_id, "opt_4")
        self.assertTrue(answer["correct"])
        self.assertEqual(
            answer["source_urls"],
            ["https://learn.microsoft.com/azure/postgresql/vector-search"],
        )


if __name__ == "__main__":
    unittest.main()
