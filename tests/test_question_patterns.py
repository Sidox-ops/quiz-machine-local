from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from backend.corpus import load_chunks
from backend.question_patterns import QuestionPatternBank


def _write_pattern_bank(root: Path) -> None:
    payload = {
        "purpose": "question_patterns",
        "questions": [
            {
                "format": "hotspot",
                "case_study_id": "case-1",
                "prompt": "A technical sentence that must never enter the model hint.",
            },
            {
                "format": "drag_drop",
                "case_study_id": None,
                "prompt": "Another sentence that is structure-only.",
            },
        ],
    }
    (root / "patterns.json").write_text(json.dumps(payload), encoding="utf-8")


class QuestionPatternBankTests(unittest.TestCase):
    def test_pattern_json_is_excluded_from_grounding_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_pattern_bank(root)

            self.assertEqual(load_chunks(root), [])

    def test_case_study_hint_uses_structure_without_source_wording(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_pattern_bank(root)
            bank = QuestionPatternBank(root)

            hint = bank.prompt_hint("case_study")

            self.assertIn("current environment", hint)
            self.assertIn("four-option", hint)
            self.assertNotIn("technical sentence", hint.lower())

    def test_standard_hint_can_adapt_non_mcq_source_formats(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_pattern_bank(root)
            bank = QuestionPatternBank(root)

            hint = bank.prompt_hint("standard")

            self.assertIn("matching, ordering", hint)
            self.assertIn("retrieved_context", hint)


if __name__ == "__main__":
    unittest.main()
