from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import threading

from .config import QUESTIONS_PATH


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalized(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


class QuestionStore:
    """Persistent bank of validated artifacts with lightweight usage metadata."""

    def __init__(self, path: Path = QUESTIONS_PATH):
        self.path = path
        self._lock = threading.Lock()

    def _load(self) -> dict:
        if not self.path.exists():
            return {"schema_version": 2, "questions": {}}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("questions"), dict):
            payload["schema_version"] = 2
            return payload
        legacy = payload if isinstance(payload, dict) else {}
        return {
            "schema_version": 2,
            "questions": {
                question_id: {
                    "artifact": artifact,
                    "created_at": _now(),
                    "presented_count": 0,
                    "correct_count": 0,
                    "incorrect_count": 0,
                }
                for question_id, artifact in legacy.items()
                if isinstance(artifact, dict)
            },
        }

    def _write(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def save(self, question_id: str, payload: dict) -> None:
        with self._lock:
            data = self._load()
            previous = data["questions"].get(question_id, {})
            data["questions"][question_id] = {
                "artifact": payload,
                "created_at": previous.get("created_at", _now()),
                "presented_count": int(previous.get("presented_count", 0)),
                "correct_count": int(previous.get("correct_count", 0)),
                "incorrect_count": int(previous.get("incorrect_count", 0)),
                "last_presented_at": previous.get("last_presented_at"),
                "last_answered_at": previous.get("last_answered_at"),
            }
            if len(data["questions"]) > 1000:
                ordered = sorted(
                    data["questions"].items(),
                    key=lambda item: (
                        item[1].get("last_answered_at") or "",
                        item[1].get("created_at") or "",
                    ),
                    reverse=True,
                )[:800]
                data["questions"] = dict(ordered)
            self._write(data)

    def get(self, question_id: str) -> dict | None:
        with self._lock:
            entry = self._load()["questions"].get(question_id)
            return dict(entry["artifact"]) if isinstance(entry, dict) else None

    def select_one(
        self,
        *,
        certification_code: str,
        question_type: str,
        difficulty: str,
        domain: str | None = None,
        learning_objective: str | None = None,
        preferred_objectives: list[str] | None = None,
        exclude_question_ids: set[str] | None = None,
    ) -> tuple[str, dict] | None:
        excluded = exclude_question_ids or set()
        preferred = {
            _normalized(value): index
            for index, value in enumerate(preferred_objectives or [])
        }
        with self._lock:
            data = self._load()
            candidates = []
            for question_id, entry in data["questions"].items():
                if question_id in excluded or not isinstance(entry, dict):
                    continue
                artifact = entry.get("artifact") or {}
                canonical = artifact.get("canonical") or {}
                if canonical.get("certification_code") != certification_code.upper():
                    continue
                if canonical.get("question_type") != question_type:
                    continue
                if difficulty != "random" and canonical.get("difficulty") != difficulty:
                    continue
                if domain and _normalized(canonical.get("domain")) != _normalized(domain):
                    continue
                objective = _normalized(canonical.get("learning_objective"))
                if learning_objective and objective != _normalized(learning_objective):
                    continue
                preferred_rank = preferred.get(objective, len(preferred) + 1)
                errors = int(entry.get("incorrect_count", 0))
                successes = int(entry.get("correct_count", 0))
                candidates.append(
                    (
                        preferred_rank,
                        -(errors - successes),
                        int(entry.get("presented_count", 0)),
                        entry.get("last_presented_at") or "",
                        question_id,
                        artifact,
                    )
                )
            if not candidates:
                return None
            candidates.sort(key=lambda item: item[:-1])
            *_, question_id, artifact = candidates[0]
            return str(question_id), dict(artifact)

    def mark_presented(self, question_id: str) -> None:
        with self._lock:
            data = self._load()
            entry = data["questions"].get(question_id)
            if not isinstance(entry, dict):
                return
            entry["presented_count"] = int(entry.get("presented_count", 0)) + 1
            entry["last_presented_at"] = _now()
            self._write(data)

    def record_attempt(self, question_id: str, correct: bool) -> None:
        with self._lock:
            data = self._load()
            entry = data["questions"].get(question_id)
            if not isinstance(entry, dict):
                return
            key = "correct_count" if correct else "incorrect_count"
            entry[key] = int(entry.get(key, 0)) + 1
            entry["last_answered_at"] = _now()
            self._write(data)

    def stats(self, certification_code: str | None = None) -> dict:
        with self._lock:
            entries = self._load()["questions"].values()
            if certification_code:
                entries = [
                    entry
                    for entry in entries
                    if ((entry.get("artifact") or {}).get("canonical") or {}).get(
                        "certification_code"
                    )
                    == certification_code.upper()
                ]
            entries = list(entries)
            return {
                "question_count": len(entries),
                "presented_count": sum(
                    int(item.get("presented_count", 0)) for item in entries
                ),
                "answered_count": sum(
                    int(item.get("correct_count", 0))
                    + int(item.get("incorrect_count", 0))
                    for item in entries
                ),
            }
