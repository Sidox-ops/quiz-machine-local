from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from .config import PROGRESS_PATH


def _empty_scope() -> dict:
    return {
        "asked": 0,
        "correct": 0,
        "accuracy": 0.0,
        "by_domain": {},
        "by_topic": {},
        "by_objective": {},
        "confusions": [],
        "recent_attempts": [],
    }


def _empty_progress() -> dict:
    return {"schema_version": 3, **_empty_scope(), "by_certification": {}}


def _objective_key(certification_code: str, learning_objective: str) -> str:
    normalized = " ".join(learning_objective.casefold().split())
    return f"{certification_code.upper()}|{normalized}"


def _update_bucket(bucket: dict, correct: bool, elapsed_seconds: float | None) -> None:
    bucket["asked"] = int(bucket.get("asked", 0)) + 1
    bucket["correct"] = int(bucket.get("correct", 0)) + int(correct)
    bucket["accuracy"] = round(bucket["correct"] / bucket["asked"], 4)
    bucket["mastery"] = round((bucket["correct"] + 1) / (bucket["asked"] + 2), 4)
    prior_streak = int(bucket.get("streak", 0))
    bucket["streak"] = prior_streak + 1 if correct else 0
    bucket["last_answered_at"] = datetime.now(timezone.utc).isoformat()
    if elapsed_seconds is not None:
        total = float(bucket.get("total_seconds", 0.0)) + elapsed_seconds
        bucket["total_seconds"] = round(total, 2)
        bucket["average_seconds"] = round(total / bucket["asked"], 2)


def _merge_stats(target: dict, source: dict) -> None:
    target["asked"] = int(target.get("asked", 0)) + int(source.get("asked", 0))
    target["correct"] = int(target.get("correct", 0)) + int(source.get("correct", 0))
    target["accuracy"] = round(target["correct"] / target["asked"], 4) if target["asked"] else 0.0
    target["mastery"] = round((target["correct"] + 1) / (target["asked"] + 2), 4)
    total = float(target.get("total_seconds", 0.0)) + float(source.get("total_seconds", 0.0))
    if total:
        target["total_seconds"] = round(total, 2)
        target["average_seconds"] = round(total / target["asked"], 2)
    latest = str(source.get("last_answered_at") or "")
    if latest > str(target.get("last_answered_at") or ""):
        target["last_answered_at"] = latest
        target["streak"] = int(source.get("streak", 0))


def _normalize_scope(payload: object) -> dict:
    result = _empty_scope()
    if not isinstance(payload, dict):
        return result
    result["asked"] = max(0, int(payload.get("asked", 0)))
    result["correct"] = max(0, int(payload.get("correct", 0)))
    result["accuracy"] = round(result["correct"] / result["asked"], 4) if result["asked"] else 0.0
    for key in ("by_domain", "by_topic", "by_objective"):
        value = payload.get(key)
        result[key] = value if isinstance(value, dict) else {}
    for key in ("confusions", "recent_attempts"):
        value = payload.get(key)
        result[key] = value if isinstance(value, list) else []
    return result


class ProgressStore:
    def __init__(self, path: Path = PROGRESS_PATH):
        self.path = path

    def load(self) -> dict:
        if not self.path.exists():
            return _empty_progress()
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return _empty_progress()
        progress = _empty_progress()
        progress.update(_normalize_scope(payload))
        raw_certifications = payload.get("by_certification")
        if isinstance(raw_certifications, dict):
            progress["by_certification"] = {
                str(code).upper(): _normalize_scope(scope)
                for code, scope in raw_certifications.items()
                if isinstance(scope, dict)
            }
        else:
            progress["by_certification"] = self._migrate_certifications(progress)
        self._rebuild_aggregate(progress)
        return progress

    def report(self, certification_code: str | None = None) -> dict:
        progress = self.load()
        code = certification_code.upper() if certification_code else None
        scope = progress["by_certification"].get(code, _empty_scope()) if code else progress
        recent = scope.get("recent_attempts", [])
        recent_window = recent[-20:]
        recent_correct = sum(bool(item.get("correct")) for item in recent_window)
        timed = [
            float(item["elapsed_seconds"])
            for item in recent
            if item.get("elapsed_seconds") is not None
        ]
        return {
            "schema_version": 3,
            "certification_code": code,
            "asked": int(scope.get("asked", 0)),
            "correct": int(scope.get("correct", 0)),
            "incorrect": max(0, int(scope.get("asked", 0)) - int(scope.get("correct", 0))),
            "accuracy": float(scope.get("accuracy", 0.0)),
            "recent_accuracy": round(recent_correct / len(recent_window), 4) if recent_window else 0.0,
            "average_seconds": round(sum(timed) / len(timed), 2) if timed else None,
            "by_domain": scope.get("by_domain", {}),
            "by_objective": scope.get("by_objective", {}),
            "confusions": scope.get("confusions", [])[:12],
            "recent_attempts": recent[-30:],
        }

    def record(
        self,
        domain: str,
        topic: str,
        correct: bool,
        *,
        certification_code: str = "AI-103",
        learning_objective: str | None = None,
        question_id: str | None = None,
        selected_option_id: str | None = None,
        correct_option_id: str | None = None,
        selected_option_text: str | None = None,
        correct_option_text: str | None = None,
        elapsed_seconds: float | None = None,
    ) -> dict:
        progress = self.load()
        code = certification_code.upper()
        scope = progress["by_certification"].setdefault(code, _empty_scope())
        scope["asked"] = int(scope.get("asked", 0)) + 1
        scope["correct"] = int(scope.get("correct", 0)) + int(correct)
        scope["accuracy"] = round(scope["correct"] / scope["asked"], 4)

        for bucket_name, key in (("by_domain", domain), ("by_topic", topic)):
            bucket = scope[bucket_name].setdefault(key or "unknown", {})
            _update_bucket(bucket, correct, elapsed_seconds)

        objective = learning_objective or topic or "unknown"
        key = _objective_key(code, objective)
        objective_bucket = scope["by_objective"].setdefault(
            key,
            {
                "certification_code": code,
                "learning_objective": objective,
                "domain": domain,
                "topic": topic,
            },
        )
        _update_bucket(objective_bucket, correct, elapsed_seconds)

        if not correct and selected_option_text and correct_option_text:
            confusion = next(
                (
                    item
                    for item in scope["confusions"]
                    if item.get("learning_objective") == objective
                    and item.get("selected_option_text") == selected_option_text
                    and item.get("correct_option_text") == correct_option_text
                ),
                None,
            )
            if confusion is None:
                confusion = {
                    "certification_code": code,
                    "learning_objective": objective,
                    "selected_option_text": selected_option_text,
                    "correct_option_text": correct_option_text,
                    "count": 0,
                }
                scope["confusions"].append(confusion)
            confusion["count"] += 1
            confusion["last_seen_at"] = datetime.now(timezone.utc).isoformat()
            scope["confusions"] = sorted(
                scope["confusions"],
                key=lambda item: (item.get("count", 0), item.get("last_seen_at", "")),
                reverse=True,
            )[:100]

        scope["recent_attempts"].append(
            {
                "question_id": question_id,
                "certification_code": code,
                "learning_objective": objective,
                "domain": domain,
                "correct": correct,
                "selected_option_id": selected_option_id,
                "correct_option_id": correct_option_id,
                "elapsed_seconds": elapsed_seconds,
                "answered_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        scope["recent_attempts"] = scope["recent_attempts"][-100:]
        self._rebuild_aggregate(progress)
        self._save(progress)
        return self.report(code)

    def reset(self, scope: str, certification_code: str | None = None) -> dict:
        if scope not in {"recent_activity", "adaptive_profile", "certification", "all"}:
            raise ValueError("Unknown progress reset scope.")
        code = certification_code.upper() if certification_code else None
        progress = self.load()
        if scope == "all":
            progress = _empty_progress()
        elif scope == "certification":
            if not code:
                raise ValueError("A certification code is required for this reset.")
            progress["by_certification"].pop(code, None)
        else:
            targets = (
                [progress["by_certification"].setdefault(code, _empty_scope())]
                if code
                else list(progress["by_certification"].values())
            )
            for target in targets:
                if scope == "recent_activity":
                    target["recent_attempts"] = []
                else:
                    for key in ("by_domain", "by_topic", "by_objective"):
                        target[key] = {}
                    target["confusions"] = []
        self._rebuild_aggregate(progress)
        self._save(progress)
        return self.report(code)

    def objective_priorities(self, certification_code: str, objectives: list[str]) -> list[dict]:
        scope = self.load()["by_certification"].get(certification_code.upper(), _empty_scope())
        result = []
        for position, objective in enumerate(objectives):
            bucket = scope["by_objective"].get(_objective_key(certification_code, objective), {})
            asked = int(bucket.get("asked", 0))
            mastery = float(bucket.get("mastery", 0.5 if asked else 0.0))
            streak = int(bucket.get("streak", 0))
            unseen_bonus = 0.35 if asked == 0 else 0.0
            error_bonus = 0.75 * (1.0 - float(bucket.get("accuracy", 0.0))) if asked else 0.0
            priority = max(0.05, 1.0 - mastery + unseen_bonus + error_bonus - min(streak, 3) * 0.06)
            result.append(
                {
                    "learning_objective": objective,
                    "asked": asked,
                    "mastery": round(mastery, 4),
                    "priority": round(priority, 4),
                    "position": position,
                }
            )
        return sorted(result, key=lambda item: (-item["priority"], item["position"]))

    def weakest_domain(self, certification_code: str | None = None) -> str | None:
        eligible = [
            (stats.get("mastery", stats.get("accuracy", 0.0)), name)
            for name, stats in self.report(certification_code)["by_domain"].items()
            if stats.get("asked", 0) >= 2
        ]
        return min(eligible)[1] if eligible else None

    def weakest_objective(self, certification_code: str) -> str | None:
        scope = self.load()["by_certification"].get(certification_code.upper(), _empty_scope())
        candidates = list(scope["by_objective"].values())
        if not candidates:
            return None
        weakest = min(
            candidates,
            key=lambda item: (
                item.get("mastery", item.get("accuracy", 0.0)),
                -item.get("asked", 0),
            ),
        )
        return str(weakest.get("learning_objective") or "") or None

    def _migrate_certifications(self, progress: dict) -> dict:
        certifications: dict[str, dict] = {}
        for key, stats in progress.get("by_objective", {}).items():
            if not isinstance(stats, dict):
                continue
            code = str(stats.get("certification_code") or str(key).partition("|")[0]).upper()
            if not code:
                continue
            scope = certifications.setdefault(code, _empty_scope())
            scope["by_objective"][str(key)] = dict(stats)
            _merge_stats(scope, stats)
            domain = str(stats.get("domain") or "unknown")
            _merge_stats(scope["by_domain"].setdefault(domain, {}), stats)
        for item in progress.get("confusions", []):
            code = str(item.get("certification_code") or "AI-103").upper()
            certifications.setdefault(code, _empty_scope())["confusions"].append(item)
        for item in progress.get("recent_attempts", []):
            code = str(item.get("certification_code") or "AI-103").upper()
            certifications.setdefault(code, _empty_scope())["recent_attempts"].append(item)
        assigned_asked = sum(scope["asked"] for scope in certifications.values())
        assigned_correct = sum(scope["correct"] for scope in certifications.values())
        missing_asked = max(0, int(progress.get("asked", 0)) - assigned_asked)
        missing_correct = max(0, int(progress.get("correct", 0)) - assigned_correct)
        if missing_asked:
            legacy = certifications.setdefault("LEGACY", _empty_scope())
            legacy["asked"] = missing_asked
            legacy["correct"] = min(missing_correct, missing_asked)
            legacy["accuracy"] = round(legacy["correct"] / legacy["asked"], 4)
        return certifications

    @staticmethod
    def _rebuild_aggregate(progress: dict) -> None:
        aggregate = _empty_scope()
        for scope in progress.get("by_certification", {}).values():
            _merge_stats(aggregate, scope)
            for collection in ("by_domain", "by_topic", "by_objective"):
                for key, stats in scope.get(collection, {}).items():
                    target = aggregate[collection].setdefault(key, {})
                    if collection == "by_objective":
                        for metadata in ("certification_code", "learning_objective", "domain", "topic"):
                            if metadata in stats:
                                target[metadata] = stats[metadata]
                    _merge_stats(target, stats)
            aggregate["confusions"].extend(scope.get("confusions", []))
            aggregate["recent_attempts"].extend(scope.get("recent_attempts", []))
        aggregate["confusions"] = sorted(
            aggregate["confusions"],
            key=lambda item: (item.get("count", 0), item.get("last_seen_at", "")),
            reverse=True,
        )[:100]
        aggregate["recent_attempts"] = sorted(
            aggregate["recent_attempts"], key=lambda item: item.get("answered_at", "")
        )[-100:]
        for key, value in aggregate.items():
            progress[key] = value
        progress["schema_version"] = 3

    def _save(self, progress: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(progress, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
