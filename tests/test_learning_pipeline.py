from __future__ import annotations

from pathlib import Path
import tempfile
import time
import unittest

from backend.batch_jobs import BatchJobManager
from backend.progress import ProgressStore
from backend.question_store import QuestionStore
from backend.quiz_engine import QuizEngine


def _artifact(
    certification: str,
    objective: str,
    *,
    question_type: str = "standard",
    difficulty: str = "hard",
) -> dict:
    return {
        "canonical": {
            "certification_code": certification,
            "learning_objective": objective,
            "question_type": question_type,
            "difficulty": difficulty,
            "domain": "Build AI solutions",
        }
    }


class _BankQuestion:
    def __init__(self, index: int) -> None:
        self.question_id = f"bank-{index}"
        self.question = f"Validated bank question {index}?"

    def model_dump(self) -> dict:
        return {
            "question_id": self.question_id,
            "question": self.question,
        }


class _BankOnlyEngine:
    def __init__(self) -> None:
        self.reused = 0
        self.generated = 0

    def prepare_certification(self, certification_code, *, progress, cancelled):
        progress(1, 1, "Canonical corpus is ready.")
        return {"ready": True}

    def learning_plan(self, certification_code, count, **kwargs):
        return ["Use grounded retrieval"] * count

    def reuse_question(self, **kwargs):
        self.reused += 1
        return _BankQuestion(self.reused)

    def generate(self, **kwargs):
        self.generated += 1
        raise AssertionError("A complete validated bank must avoid LLM generation")


class _PlanRag:
    uses_microsoft_learn = True

    def blueprint_objectives(self, certification_code, domain=None):
        return [f"Objective {index}" for index in range(1, 10)]


class _PlanProgress:
    def objective_priorities(self, certification_code, objectives):
        return [
            {
                "learning_objective": objective,
                "asked": 3 if index == 0 else 0,
                "mastery": 0.2 if index == 0 else 0.0,
                "priority": 2.0 if index == 0 else 1.0,
                "position": index,
            }
            for index, objective in enumerate(objectives)
        ]


class LearningPipelineTests(unittest.TestCase):
    def test_learning_plan_reserves_reinforcement_without_extra_generation(self) -> None:
        engine = QuizEngine(None, _PlanRag(), _PlanProgress(), None)

        plan = engine.learning_plan("AI-200", 9)

        self.assertEqual(len(plan), 9)
        self.assertGreaterEqual(plan.count("Objective 1"), 2)
        self.assertGreaterEqual(len(set(plan)), 6)

    def test_question_store_migrates_legacy_artifacts_and_filters_bank(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "questions.json"
            store = QuestionStore(path)
            store.save("q1", _artifact("AI-200", "Use grounded retrieval"))
            store.save("q2", _artifact("AI-200", "Build agents"))
            store.save(
                "q3",
                _artifact(
                    "AI-200",
                    "Use grounded retrieval",
                    question_type="case_study",
                ),
            )

            selected = store.select_one(
                certification_code="AI-200",
                question_type="standard",
                difficulty="hard",
                learning_objective="Use grounded retrieval",
            )
            self.assertIsNotNone(selected)
            self.assertEqual(selected[0], "q1")
            store.mark_presented("q1")
            store.record_attempt("q1", False)
            stats = store.stats("AI-200")

        self.assertEqual(stats["question_count"], 3)
        self.assertEqual(stats["presented_count"], 1)
        self.assertEqual(stats["answered_count"], 1)

    def test_progress_tracks_mastery_confusions_and_learning_priority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ProgressStore(Path(directory) / "progress.json")
            store.record(
                "Build AI solutions",
                "Retrieval",
                False,
                certification_code="AI-200",
                learning_objective="Use grounded retrieval",
                selected_option_text="Use model memory",
                correct_option_text="Retrieve approved evidence",
                elapsed_seconds=42,
            )
            priorities = store.objective_priorities(
                "AI-200",
                ["Use grounded retrieval", "Build agents"],
            )
            payload = store.load()

        self.assertEqual(priorities[0]["learning_objective"], "Use grounded retrieval")
        objective = payload["by_objective"][
            "AI-200|use grounded retrieval"
        ]
        self.assertEqual(objective["asked"], 1)
        self.assertLess(objective["mastery"], 0.5)
        self.assertEqual(payload["confusions"][0]["count"], 1)
        self.assertEqual(objective["average_seconds"], 42)

    def test_progress_reports_and_resets_are_scoped_by_certification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ProgressStore(Path(directory) / "progress.json")
            store.record(
                "Build AI solutions",
                "Retrieval",
                False,
                certification_code="AI-200",
                learning_objective="Use grounded retrieval",
                selected_option_text="Use model memory",
                correct_option_text="Retrieve approved evidence",
                elapsed_seconds=40,
            )
            store.record(
                "Describe AI workloads",
                "Vision",
                True,
                certification_code="AI-900",
                learning_objective="Identify vision workloads",
                elapsed_seconds=20,
            )

            ai_200 = store.report("AI-200")
            ai_900 = store.report("AI-900")
            store.reset("recent_activity", "AI-200")
            recent_reset = store.report("AI-200")
            store.reset("certification", "AI-200")
            removed = store.report("AI-200")
            preserved = store.report("AI-900")

        self.assertEqual(ai_200["asked"], 1)
        self.assertEqual(ai_200["accuracy"], 0)
        self.assertEqual(ai_200["average_seconds"], 40)
        self.assertEqual(ai_900["asked"], 1)
        self.assertEqual(ai_900["accuracy"], 1)
        self.assertEqual(recent_reset["asked"], 1)
        self.assertEqual(recent_reset["recent_attempts"], [])
        self.assertEqual(removed["asked"], 0)
        self.assertEqual(preserved["asked"], 1)

    def test_batch_uses_validated_bank_without_mid_session_generation(self) -> None:
        engine = _BankOnlyEngine()
        manager = BatchJobManager(engine)
        job = manager.start(
            certification_code="AI-200",
            count=5,
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
        self.assertEqual(state["completed"], 5)
        self.assertEqual(state["reused"], 5)
        self.assertEqual(state["attempts"], 0)
        self.assertEqual(engine.generated, 0)


if __name__ == "__main__":
    unittest.main()
