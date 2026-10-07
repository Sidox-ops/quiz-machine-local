from __future__ import annotations

from copy import deepcopy
import logging
import random
import threading
import uuid

from .quiz_engine import QuizEngine


logger = logging.getLogger(__name__)


class BatchJobManager:
    """Generate quiz batches in the background and expose real progress for polling."""

    def __init__(self, engine: QuizEngine):
        self.engine = engine
        self._jobs: dict[str, dict] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        # Ollama is local and the target machine is resource constrained. Serializing
        # generation prevents two UI clicks from making the local LLM fight itself for RAM/CPU.
        self._generation_lock = threading.Lock()

    @staticmethod
    def _question_type_deck(count: int, requested: str) -> list[str]:
        if requested != "mixed":
            return [requested] * count
        if count < 3:
            return ["standard"] * count

        case_study_count = max(1, int(count * 0.30 + 0.5))
        deck = ["case_study"] * case_study_count
        deck.extend(["standard"] * (count - case_study_count))
        random.shuffle(deck)
        return deck

    def start(
        self,
        *,
        certification_code: str = "AI-103",
        count: int,
        mode: str,
        domain: str | None,
        chapter_id: str | None,
        difficulty: str,
        question_type: str,
    ) -> dict:
        job_id = uuid.uuid4().hex[:12]
        job = {
            "job_id": job_id,
            "certification_code": certification_code,
            "status": "queued",
            "total": count,
            "completed": 0,
            "attempts": 0,
            "rejected": 0,
            "reused": 0,
            "phase": "queued",
            "corpus_completed": 0,
            "corpus_total": 0,
            "corpus_attempts": 0,
            "corpus_retries": 0,
            "questions": [],
            "error": None,
            "last_error": None,
            "message": "Waiting for the local generation slot...",
        }
        with self._lock:
            self._jobs[job_id] = job
            self._cancel_events[job_id] = threading.Event()

        thread = threading.Thread(
            target=self._run,
            kwargs={
                "job_id": job_id,
                "certification_code": certification_code,
                "count": count,
                "mode": mode,
                "domain": domain,
                "chapter_id": chapter_id,
                "difficulty": difficulty,
                "question_types": self._question_type_deck(count, question_type),
            },
            daemon=True,
            name=f"quiz-batch-{job_id}",
        )
        thread.start()
        return deepcopy(job)

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return deepcopy(job) if job else None

    def cancel(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            event = self._cancel_events.get(job_id)
            if job is None or event is None:
                return None
            if job["status"] not in {"completed", "failed", "cancelled"}:
                event.set()
                job.update(
                    status="cancelled",
                    message="Generation cancelled. Validated questions were kept locally.",
                )
            return deepcopy(job)

    def _update(self, job_id: str, **changes) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(changes)

    def _append_question(
        self,
        job_id: str,
        payload: dict,
        *,
        reused: bool = False,
    ) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job["questions"].append(payload)
            job["completed"] = len(job["questions"])
            job["reused"] += int(reused)

    def _record_attempt(self, job_id: str, question_number: int, count: int) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job["attempts"] += 1
            job["status"] = "generating"
            job["message"] = f"Generating question {question_number} of {count}..."

    def _record_rejection(self, job_id: str, error: str, count: int) -> int:
        with self._lock:
            job = self._jobs[job_id]
            job["rejected"] += 1
            job["last_error"] = error
            job["status"] = "retrying"
            question_number = job["completed"] + 1
            job["message"] = (
                f"Question {question_number} of {count}: candidate rejected; "
                "retrying automatically."
            )
            return job["rejected"]

    def _record_corpus_progress(
        self,
        job_id: str,
        completed: int,
        total: int,
        message: str,
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job["status"] == "cancelled":
                return
            job.update(
                status="generating",
                phase="preparing_corpus",
                corpus_completed=completed,
                corpus_total=total,
                message=message,
            )

    @staticmethod
    def _retry_delay(consecutive_failures: int) -> float:
        # The model call itself is expensive; this short capped pause prevents a
        # tight loop when Ollama or MCP is temporarily unavailable.
        return min(0.25 * (2 ** min(consecutive_failures - 1, 3)), 2.0)

    def _run(
        self,
        *,
        job_id: str,
        certification_code: str,
        count: int,
        mode: str,
        domain: str | None,
        chapter_id: str | None,
        difficulty: str,
        question_types: list[str],
    ) -> None:
        seen_questions: set[str] = set()
        consecutive_failures = 0
        cancel_event = self._cancel_events[job_id]

        try:
            with self._generation_lock:
                prepare = getattr(self.engine, "prepare_certification", None)
                if callable(prepare):
                    corpus_failures = 0
                    while not cancel_event.is_set():
                        state = self.get(job_id)
                        self._update(
                            job_id,
                            status="generating",
                            phase="preparing_corpus",
                            corpus_attempts=(state or {}).get("corpus_attempts", 0) + 1,
                            message=f"Checking the canonical {certification_code} corpus...",
                        )
                        try:
                            prepare(
                                certification_code,
                                progress=lambda completed, total, message: (
                                    self._record_corpus_progress(
                                        job_id,
                                        completed,
                                        total,
                                        message,
                                    )
                                ),
                                cancelled=cancel_event.is_set,
                            )
                            self._update(job_id, last_error=None)
                            break
                        except Exception as exc:
                            if cancel_event.is_set():
                                break
                            corpus_failures += 1
                            failure = str(exc)[:600] or type(exc).__name__
                            state = self.get(job_id)
                            self._update(
                                job_id,
                                status="retrying",
                                phase="preparing_corpus",
                                corpus_retries=(state or {}).get("corpus_retries", 0) + 1,
                                last_error=failure,
                                message=(
                                    "Corpus preparation was incomplete; retrying "
                                    "automatically."
                                ),
                            )
                            if corpus_failures <= 3 or corpus_failures % 10 == 0:
                                logger.warning(
                                    "Corpus preparation retry %s: %s",
                                    corpus_failures,
                                    failure,
                                )
                            cancel_event.wait(self._retry_delay(corpus_failures))

                if cancel_event.is_set():
                    self._update(
                        job_id,
                        status="cancelled",
                        message=(
                            "Generation cancelled. Validated questions were kept locally."
                        ),
                    )
                    return
                self._update(
                    job_id,
                    status="generating",
                    phase="generating_questions",
                    message=f"Building question set 1 of {count}...",
                )
                plan_builder = getattr(self.engine, "learning_plan", None)
                learning_objectives = (
                    plan_builder(
                        certification_code,
                        count,
                        mode=mode,
                        domain=domain,
                        question_types=question_types,
                    )
                    if callable(plan_builder)
                    else [None] * count
                )
                while True:
                    if cancel_event.is_set():
                        self._update(
                            job_id,
                            status="cancelled",
                            message="Generation cancelled. Validated questions were kept locally.",
                        )
                        return
                    state = self.get(job_id)
                    if not state or state["completed"] >= count:
                        break

                    try:
                        slot = state["completed"]
                        resolved_question_type = question_types[slot]
                        planned_objective = learning_objectives[slot]
                        reuse = getattr(self.engine, "reuse_question", None)
                        existing_ids = {
                            str(item.get("question_id"))
                            for item in state["questions"]
                            if item.get("question_id")
                        }
                        bank_question = (
                            reuse(
                                certification_code=certification_code,
                                question_type=resolved_question_type,
                                difficulty=difficulty,
                                domain=domain if mode == "domain" else None,
                                learning_objective=planned_objective,
                                exclude_question_ids=existing_ids,
                            )
                            if callable(reuse)
                            else None
                        )
                        if bank_question is not None:
                            normalized = " ".join(
                                bank_question.question.lower().split()
                            )
                            if normalized not in seen_questions:
                                seen_questions.add(normalized)
                                self._append_question(
                                    job_id,
                                    bank_question.model_dump(),
                                    reused=True,
                                )
                                completed = slot + 1
                                self._update(
                                    job_id,
                                    status="generating",
                                    last_error=None,
                                    message=(
                                        f"Selected {completed} of {count} validated "
                                        "questions from the local bank."
                                    ),
                                )
                                consecutive_failures = 0
                                continue

                        self._record_attempt(job_id, slot + 1, count)
                        question = self.engine.generate(
                            certification_code=certification_code,
                            mode=mode,
                            domain=domain,
                            chapter_id=chapter_id,
                            difficulty=difficulty,
                            question_type=resolved_question_type,
                            learning_objective=planned_objective,
                        )
                        normalized = " ".join(question.question.lower().split())
                        if normalized in seen_questions:
                            raise RuntimeError("The model generated a duplicate question.")
                        seen_questions.add(normalized)
                        self._append_question(job_id, question.model_dump())
                        consecutive_failures = 0
                        completed = state["completed"] + 1
                        self._update(
                            job_id,
                            status="generating",
                            last_error=None,
                            message=(
                                f"Validated {completed} of {count} questions."
                                if completed < count
                                else f"Validated all {count} questions."
                            ),
                        )
                    except Exception as exc:
                        # Quality rejection and temporary local-service errors are
                        # retryable. A requested batch is never truncated because a
                        # candidate failed: successful questions stay in the job.
                        consecutive_failures += 1
                        last_failure = str(exc)[:600] or type(exc).__name__
                        rejected = self._record_rejection(
                            job_id,
                            last_failure,
                            count,
                        )
                        if rejected <= 3 or rejected % 10 == 0:
                            logger.warning(
                                "Question candidate rejected (rejected %s, consecutive %s): %s",
                                rejected,
                                consecutive_failures,
                                last_failure,
                            )
                        cancel_event.wait(self._retry_delay(consecutive_failures))
                        continue

            self._update(
                job_id,
                status="completed",
                phase="done",
                message=f"All {count} questions are ready.",
                last_error=None,
            )
        except Exception as exc:
            self._update(job_id, status="failed", error=str(exc))
