from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import random

from .config import USER_DATA_DIR


_FORMAT_HINTS = {
    "standard": (
        "Use a concise applied scenario followed by one direct best-answer question."
    ),
    "hotspot": (
        "Use a multi-constraint configuration or code-completion scenario, then adapt "
        "it to one four-option best-answer question for the current interface."
    ),
    "drag_drop": (
        "Use a matching, ordering, or component-to-requirement scenario, then adapt "
        "it to one four-option best-answer question for the current interface."
    ),
}


@dataclass(frozen=True)
class QuestionPattern:
    source_format: str
    belongs_to_case_study: bool


class QuestionPatternBank:
    """Load private examples as structural hints, never as technical grounding."""

    def __init__(self, root: Path = USER_DATA_DIR):
        self.root = root
        self.patterns = self._load()

    def _load(self) -> list[QuestionPattern]:
        if not self.root.exists():
            return []

        patterns: list[QuestionPattern] = []
        for path in sorted(self.root.rglob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(payload, dict) or payload.get("purpose") != "question_patterns":
                continue
            for item in payload.get("questions", []):
                if not isinstance(item, dict):
                    continue
                source_format = str(item.get("format") or "standard")
                if source_format not in _FORMAT_HINTS:
                    source_format = "standard"
                patterns.append(QuestionPattern(
                    source_format=source_format,
                    belongs_to_case_study=bool(item.get("case_study_id")),
                ))
        return patterns

    def prompt_hint(self, question_type: str) -> str:
        wants_case_study = question_type == "case_study"
        candidates = [
            pattern for pattern in self.patterns
            if pattern.belongs_to_case_study == wants_case_study
        ]
        if not candidates:
            return ""

        selected = random.choice(candidates)
        format_hint = _FORMAT_HINTS[selected.source_format]
        if wants_case_study:
            organization_hint = (
                "Organize the generated case into a current environment, a concrete "
                "problem, and explicit technical, security, or business requirements."
            )
        else:
            organization_hint = "Keep the scenario self-contained."

        return " ".join([
            "Private pattern-bank guidance (structure only):",
            organization_hint,
            format_hint,
            "Do not copy wording, products, answers, or technical claims from the pattern bank.",
            "All technical content and the correct answer must come from retrieved_context.",
        ])
