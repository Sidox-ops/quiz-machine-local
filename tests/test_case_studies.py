from __future__ import annotations

from copy import deepcopy
import re
import time
import unittest
from unittest.mock import patch

from backend.batch_jobs import BatchJobManager
from backend.quiz_engine import QuizEngine, QuizGenerationError
from backend.quiz_reliability import validate_candidate
from backend.schemas import QuestionCandidate


class _FakeClient:
    def __init__(self, payload: dict):
        self.payload = payload
        self.prompts: list[str] = []
        self.schemas: list[dict] = []

    def chat_json(self, system: str, user: str, schema: dict, **kwargs) -> dict:
        self.prompts.append(user)
        self.schemas.append(schema)
        properties = schema.get("properties", {})
        fingerprint_match = re.search(r"\b[0-9a-f]{64}\b", user)
        fingerprint = fingerprint_match.group(0) if fingerprint_match else "0" * 64
        if "verdict" in properties:
            return {
                "question_fingerprint": fingerprint,
                "verdict": "accept",
                "correct_option_id": self.payload["correct_option_id"],
                "supported_option_ids": [self.payload["correct_option_id"]],
                "option_assessments": [
                    {
                        "option_id": option["id"],
                        "verdict": (
                            "supported"
                            if option["id"] == self.payload["correct_option_id"]
                            else "not_established"
                        ),
                        "supporting_source_ids": (
                            list(self.payload["supporting_source_ids"])
                            if option["id"] == self.payload["correct_option_id"]
                            else []
                        ),
                    }
                    for option in self.payload["options"]
                ],
                "supporting_source_ids": self.payload["supporting_source_ids"],
                "issues": [],
            }
        if "rationales" in properties:
            return {
                "question_fingerprint": fingerprint,
                "correct_option_id": self.payload["correct_option_id"],
                "decisive_clue": "The stable evaluation baseline is the decisive requirement.",
                "learning_rule": "Use representative examples when releases must remain comparable.",
                "takeaway": "Stable examples make release quality comparable.",
                "rationales": [
                    {
                        "option_id": option["id"],
                        "rationale": (
                            "This provides the required evaluation baseline and supports both release requirements."
                            if option["id"] == self.payload["correct_option_id"]
                            else (
                                f"This does not satisfy requirement {index}; use it when "
                                "that separate operational goal is the actual priority."
                            )
                        ),
                    }
                    for index, option in enumerate(self.payload["options"], start=1)
                ],
            }
        return deepcopy(self.payload)


class _RepairingExplanationClient(_FakeClient):
    def __init__(self, payload: dict):
        super().__init__(payload)
        self.explanation_calls = 0

    def chat_json(self, system: str, user: str, schema: dict, **kwargs) -> dict:
        if "rationales" not in schema.get("properties", {}):
            return super().chat_json(system, user, schema, **kwargs)
        self.prompts.append(user)
        self.schemas.append(schema)
        self.explanation_calls += 1
        if self.explanation_calls > 1:
            return super().chat_json(system, user, schema, **kwargs)
        fingerprint = re.search(r"\b[0-9a-f]{64}\b", user).group(0)
        return {
            "question_fingerprint": fingerprint,
            "correct_option_id": self.payload["correct_option_id"],
            "decisive_clue": "The stable evaluation baseline is the decisive requirement.",
            "learning_rule": "Use representative examples when releases must remain comparable.",
            "takeaway": "Stable examples make release quality comparable.",
            "rationales": [
                {
                    "option_id": option["id"],
                    "rationale": (
                        "This provides the required evaluation baseline and supports both release requirements."
                        if option["id"] == self.payload["correct_option_id"]
                        else "This capability concerns a separate operational goal and remains outside the evaluated release decision."
                    ),
                }
                for option in self.payload["options"]
            ],
        }


class _InvalidExplanationClient(_FakeClient):
    def __init__(self, payload: dict):
        super().__init__(payload)
        self.explanation_calls = 0

    def chat_json(self, system: str, user: str, schema: dict, **kwargs) -> dict:
        if "rationales" not in schema.get("properties", {}):
            return super().chat_json(system, user, schema, **kwargs)
        self.prompts.append(user)
        self.schemas.append(schema)
        self.explanation_calls += 1
        fingerprint = re.search(r"\b[0-9a-f]{64}\b", user).group(0)
        return {
            "question_fingerprint": fingerprint,
            "correct_option_id": self.payload["correct_option_id"],
            "decisive_clue": "The stable evaluation baseline is the decisive requirement.",
            "learning_rule": "Use representative examples when releases must remain comparable.",
            "takeaway": "Stable examples make release quality comparable.",
            "rationales": [
                {"option_id": option["id"], "rationale": "Too brief."}
                for option in self.payload["options"]
            ],
        }


class _FakeRag:
    def __init__(self):
        self.uses_microsoft_learn = False
        self.certification_codes: list[str] = []
        self.items = [
            {
                "score": 0.95,
                "chunk_id": "chunk-evaluation",
                "source": "https://learn.microsoft.com/training/modules/evaluate-ai-solutions",
                "text": "Use a representative evaluation dataset to compare solution quality.",
                "metadata": {
                    "certification": "AI-103",
                    "topic": "Evaluation",
                    "domain": "Generative AI",
                    "exam_domain": "Generative AI",
                    "learning_objective": "Evaluation",
                    "skill_group": "Evaluate generative AI solutions",
                    "skill_objective": "Evaluation",
                    "blueprint_aligned": True,
                    "blueprint_source_url": (
                        "https://learn.microsoft.com/credentials/certifications/"
                        "resources/study-guides/ai-103"
                    ),
                },
            },
            {
                "score": 0.91,
                "chunk_id": "chunk-monitoring",
                "source": "https://learn.microsoft.com/training/modules/monitor-ai-solutions",
                "text": "Monitor quality measurements across releases and investigate regressions.",
                "metadata": {
                    "certification": "AI-103",
                    "topic": "Evaluation",
                    "domain": "Generative AI",
                    "exam_domain": "Generative AI",
                    "learning_objective": "Evaluation",
                    "skill_group": "Evaluate generative AI solutions",
                    "skill_objective": "Evaluation",
                    "blueprint_aligned": True,
                    "blueprint_source_url": (
                        "https://learn.microsoft.com/credentials/certifications/"
                        "resources/study-guides/ai-103"
                    ),
                },
            },
        ]
        self.chunks = [
            {
                "score": 0.95,
                "chunk_id": "chunk-evaluation",
                "source": "https://learn.microsoft.com/training/modules/evaluate-ai-solutions",
                "text": "Use a representative evaluation dataset to compare solution quality.",
                "metadata": deepcopy(self.items[0]["metadata"]),
            },
            {
                "score": 0.91,
                "chunk_id": "chunk-monitoring",
                "source": "https://learn.microsoft.com/training/modules/monitor-ai-solutions",
                "text": "Monitor quality measurements across releases and investigate regressions.",
                "metadata": deepcopy(self.items[1]["metadata"]),
            },
        ]

    def search(
        self,
        query: str,
        top_k: int,
        domain: str | None = None,
        certification_code: str = "AI-103",
        learning_objective: str | None = None,
    ) -> list[dict]:
        self.certification_codes.append(certification_code)
        return deepcopy(self.chunks[:top_k])

    def blueprint_objectives(
        self,
        certification_code: str,
        domain: str | None = None,
    ) -> list[str]:
        return ["Evaluation"]

    def blueprint_domains(self, certification_code: str) -> list[str]:
        return list(
            dict.fromkeys(item["metadata"]["domain"] for item in self.chunks)
        )


class _FakeQuestionStore:
    def __init__(self):
        self.saved: dict[str, dict] = {}

    def save(self, question_id: str, payload: dict) -> None:
        self.saved[question_id] = payload

    def get(self, question_id: str) -> dict | None:
        return self.saved.get(question_id)


class _FakeProgress:
    def record(self, domain: str, topic: str, correct: bool) -> dict:
        return {"asked": 1, "correct": int(correct), "accuracy": float(correct)}


class _FakePatterns:
    def prompt_hint(self, question_type: str) -> str:
        return f"STRUCTURE_ONLY_HINT:{question_type}"


class _AlwaysFailEngine:
    def generate(self, **kwargs):
        raise RuntimeError("precise candidate failure")


class _GeneratedQuestion:
    def __init__(self, index: int):
        self.question = f"Validated question {index}?"
        self.index = index

    def model_dump(self) -> dict:
        return {"question": self.question, "index": self.index}


class _EventuallySucceedsEngine:
    def __init__(self, failures: int):
        self.failures = failures
        self.calls = 0
        self.successes = 0

    def generate(self, **kwargs):
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError(f"retryable quality failure {self.calls}")
        self.successes += 1
        return _GeneratedQuestion(self.successes)


class _PreparingEngine(_EventuallySucceedsEngine):
    def __init__(self):
        super().__init__(failures=0)
        self.prepare_calls = 0

    def prepare_certification(self, certification_code, *, progress, cancelled):
        self.prepare_calls += 1
        progress(0, 2, "Preparing corpus objective 1 of 2...")
        progress(2, 2, "Compact corpus is ready.")
        return {"ready": True, "objective_count": 2, "card_count": 4}


def _case_study_payload() -> dict:
    return {
        "status": "ok",
        "question_type": "case_study",
        "case_study": {
            "title": "Quality gates for a generative AI release",
            "scenario": (
                "A team releases a generative AI application on a regular cadence. "
                "It needs a stable quality baseline and a way to identify regressions "
                "before a new version reaches production users."
            ),
            "requirements": [
                "Compare every release against representative examples.",
                "Track quality changes between application versions.",
            ],
        },
        "question": "Which approach best meets both requirements?",
        "options": [
            {"id": "opt_1", "text": "Evaluate representative data and compare release metrics"},
            {"id": "opt_2", "text": "Increase capacity and compare monthly resource usage"},
            {"id": "opt_3", "text": "Change resource groups and review deployment timestamps"},
            {"id": "opt_4", "text": "Extend prompts and compare their character counts"},
        ],
        "correct_option_id": "opt_1",
        "supporting_source_ids": ["chunk-evaluation", "chunk-monitoring"],
        "topic": "Evaluation",
        "domain": "Generative AI",
        "difficulty": "medium",
        "confidence": 0.92,
    }


class CaseStudyGenerationTests(unittest.TestCase):
    def test_selected_certification_reaches_retrieval_prompt_and_storage(self) -> None:
        domain = "Identify AI concepts and capabilities"
        payload = _case_study_payload()
        payload["domain"] = domain
        rag = _FakeRag()
        rag.uses_microsoft_learn = True
        for item in [*rag.items, *rag.chunks]:
            item["metadata"]["domain"] = domain
            item["metadata"]["exam_domain"] = domain
            item["metadata"]["certification"] = "AI-901"
            item["metadata"]["blueprint_source_url"] = (
                "https://learn.microsoft.com/credentials/certifications/"
                "resources/study-guides/ai-901"
            )
        client = _FakeClient(payload)
        questions = _FakeQuestionStore()
        engine = QuizEngine(
            client,
            rag,
            _FakeProgress(),
            questions,
            patterns=_FakePatterns(),
        )

        public = engine.generate(
            certification_code="AI-901",
            mode="domain",
            domain=domain,
            difficulty="medium",
            question_type="case_study",
        )

        self.assertEqual(public.certification_code, "AI-901")
        self.assertEqual(rag.certification_codes, ["AI-901"])
        self.assertIn("AI-901 (Microsoft Azure AI Fundamentals)", client.prompts[0])
        self.assertEqual(
            questions.saved[public.question_id]["canonical"]["certification_code"],
            "AI-901",
        )

    def test_engine_generates_and_persists_grounded_case_study(self) -> None:
        client = _FakeClient(_case_study_payload())
        questions = _FakeQuestionStore()
        engine = QuizEngine(
            client,
            _FakeRag(),
            _FakeProgress(),
            questions,
            patterns=_FakePatterns(),
        )

        public = engine.generate(
            difficulty="medium",
            question_type="case_study",
        )

        self.assertEqual(public.question_type, "case_study")
        self.assertIsNotNone(public.case_study)
        self.assertEqual(len(public.supporting_source_ids), 2)
        self.assertIn("Format: case_study", client.prompts[0])
        self.assertIn("STRUCTURE_ONLY_HINT:case_study", client.prompts[0])
        self.assertIn(public.question_id, questions.saved)

    def test_engine_repairs_a_rejected_explanation_without_discarding_question(self) -> None:
        client = _RepairingExplanationClient(_case_study_payload())
        questions = _FakeQuestionStore()
        engine = QuizEngine(
            client,
            _FakeRag(),
            _FakeProgress(),
            questions,
            patterns=_FakePatterns(),
        )

        public = engine.generate(
            difficulty="medium",
            question_type="case_study",
        )

        self.assertIn(public.question_id, questions.saved)
        self.assertEqual(client.explanation_calls, 2)
        self.assertTrue(any(
            "previous explanation was rejected" in prompt.lower()
            and "distractor explanation does not state why" in prompt.lower()
            for prompt in client.prompts
        ))

    def test_validated_question_survives_repeated_explanation_format_failures(self) -> None:
        client = _InvalidExplanationClient(_case_study_payload())
        questions = _FakeQuestionStore()
        engine = QuizEngine(
            client,
            _FakeRag(),
            _FakeProgress(),
            questions,
            patterns=_FakePatterns(),
        )

        public = engine.generate(
            difficulty="medium",
            question_type="case_study",
        )

        self.assertIn(public.question_id, questions.saved)
        self.assertEqual(client.explanation_calls, 5)
        stored = questions.saved[public.question_id]
        self.assertIn("meets the decisive scenario requirement", stored["explanation"])

    def test_ollama_schemas_avoid_unsupported_optional_case_grammar(self) -> None:
        standard = QuizEngine._generation_schema("standard", difficulty="hard")
        case_study = QuizEngine._generation_schema("case_study", difficulty="hard")

        self.assertNotIn("case_study", standard["properties"])
        self.assertNotIn("CaseStudyContext", standard["$defs"])
        self.assertEqual(standard["properties"]["question_type"]["enum"], ["standard"])
        self.assertEqual(standard["properties"]["difficulty"]["enum"], ["hard"])
        self.assertIn("case_study", case_study["required"])
        self.assertEqual(
            case_study["properties"]["question_type"]["enum"], ["case_study"]
        )
        self.assertEqual(case_study["properties"]["case_study"]["type"], "object")
        serialized_case_schema = str(case_study["properties"]["case_study"])
        for unsupported in ("anyOf", "maxLength"):
            self.assertNotIn(unsupported, serialized_case_schema)
        requirements_schema = case_study["properties"]["case_study"]["properties"][
            "requirements"
        ]
        self.assertEqual(requirements_schema["minItems"], 2)
        self.assertEqual(requirements_schema["maxItems"], 5)

    def test_case_study_requires_two_grounding_chunks(self) -> None:
        payload = _case_study_payload()
        payload["supporting_source_ids"] = ["chunk-evaluation"]
        generated = QuestionCandidate.model_validate(payload)

        with self.assertRaisesRegex(RuntimeError, "at least two"):
            validate_candidate(
                generated,
                _FakeRag().chunks,
                certification_code="AI-103",
                learning_objective="Evaluation",
                required_question_type="case_study",
            )

    def test_mixed_batch_contains_thirty_percent_case_studies(self) -> None:
        self.assertEqual(
            BatchJobManager._question_type_deck(1, "mixed"),
            ["standard"],
        )
        deck = BatchJobManager._question_type_deck(10, "mixed")

        self.assertEqual(len(deck), 10)
        self.assertEqual(deck.count("case_study"), 3)
        self.assertEqual(deck.count("standard"), 7)

    def test_forced_batch_format_is_preserved(self) -> None:
        self.assertEqual(
            BatchJobManager._question_type_deck(12, "case_study"),
            ["case_study"] * 12,
        )

    def test_batch_retries_until_every_requested_question_is_ready(self) -> None:
        engine = _EventuallySucceedsEngine(failures=8)
        manager = BatchJobManager(engine)
        with patch.object(BatchJobManager, "_retry_delay", return_value=0):
            job = manager.start(
                count=3,
                mode="shuffle",
                domain=None,
                chapter_id=None,
                difficulty="hard",
                question_type="standard",
            )

            state = job
            for _ in range(200):
                state = manager.get(job["job_id"])
                if state and state["status"] == "completed":
                    break
                time.sleep(0.005)

        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["completed"], 3)
        self.assertEqual(state["attempts"], 11)
        self.assertEqual(state["rejected"], 8)
        self.assertEqual(len(state["questions"]), 3)
        self.assertIsNone(state["error"])

    def test_batch_reports_corpus_preparation_before_question_generation(self) -> None:
        engine = _PreparingEngine()
        manager = BatchJobManager(engine)
        job = manager.start(
            certification_code="AI-200",
            count=1,
            mode="shuffle",
            domain=None,
            chapter_id=None,
            difficulty="hard",
            question_type="standard",
        )
        state = job
        for _ in range(100):
            state = manager.get(job["job_id"])
            if state and state["status"] == "completed":
                break
            time.sleep(0.005)

        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["phase"], "done")
        self.assertEqual(state["corpus_completed"], 2)
        self.assertEqual(state["corpus_total"], 2)
        self.assertEqual(state["corpus_attempts"], 1)
        self.assertEqual(engine.prepare_calls, 1)

    def test_user_can_cancel_an_indefinitely_retrying_batch(self) -> None:
        manager = BatchJobManager(_AlwaysFailEngine())
        with patch.object(BatchJobManager, "_retry_delay", return_value=0.01):
            job = manager.start(
                count=1,
                mode="shuffle",
                domain=None,
                chapter_id=None,
                difficulty="hard",
                question_type="standard",
            )
            state = job
            for _ in range(100):
                state = manager.get(job["job_id"])
                if state and state["rejected"] > 0:
                    break
                time.sleep(0.005)
            cancelled = manager.cancel(job["job_id"])

        self.assertIsNotNone(cancelled)
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertIn("cancelled", cancelled["message"].lower())


if __name__ == "__main__":
    unittest.main()
