import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend import api
from backend.schemas import MarkdownCorpusBatchImportRequest


def _markdown(document_id: str, title: str = "Evaluation notes") -> str:
    return f"""---
schema: quiz-machine-corpus/v1
document_id: {document_id}
certification_code: AI-103
domain: Plan and manage an Azure AI solution
title: {title}
language: en
---

# {title}

## Quality criteria

Use representative test data and stable metrics to compare candidate models.
"""


class _ModelClient:
    def assert_required_models(self, require_embedding: bool = True) -> None:
        if not require_embedding:
            raise AssertionError("Markdown import must require the embedding model.")


class _Rag:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.build_calls = 0
        self.invalidated: list[str] = []

    def build(self) -> int:
        self.build_calls += 1
        if self.error:
            raise self.error
        return 2

    def invalidate_generation_corpus(self, certification_code: str) -> None:
        self.invalidated.append(certification_code)


class CorpusApiTests(unittest.TestCase):
    def test_batch_import_writes_all_files_and_builds_once(self) -> None:
        request = MarkdownCorpusBatchImportRequest.model_validate({
            "rights_confirmed": True,
            "files": [
                {"filename": "one.md", "content": _markdown("notes-one")},
                {"filename": "two.md", "content": _markdown("notes-two", "Other notes")},
            ],
        })
        rag = _Rag()
        with tempfile.TemporaryDirectory() as directory, patch.object(
            api, "USER_DATA_DIR", Path(directory)
        ), patch.object(api, "client", _ModelClient()), patch.object(api, "rag", rag):
            response = api.import_markdown_batch(request)

            self.assertTrue((Path(directory) / "notes-one.md").exists())
            self.assertTrue((Path(directory) / "notes-two.md").exists())

        self.assertEqual(response.file_count, 2)
        self.assertEqual(response.chunk_count, 2)
        self.assertEqual(rag.build_calls, 1)
        self.assertEqual(rag.invalidated, ["AI-103"])

    def test_batch_import_rolls_back_every_file_when_indexing_fails(self) -> None:
        request = MarkdownCorpusBatchImportRequest.model_validate({
            "rights_confirmed": True,
            "files": [
                {"filename": "one.md", "content": _markdown("notes-one")},
                {"filename": "two.md", "content": _markdown("notes-two", "Other notes")},
            ],
        })
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = root / "notes-one.md"
            existing.write_text("previous content", encoding="utf-8")
            with patch.object(api, "USER_DATA_DIR", root), patch.object(
                api, "client", _ModelClient()
            ), patch.object(api, "rag", _Rag(RuntimeError("embedding failed"))):
                with self.assertRaises(HTTPException) as raised:
                    api.import_markdown_batch(request)

            self.assertEqual(raised.exception.status_code, 422)
            self.assertEqual(existing.read_text(encoding="utf-8"), "previous content")
            self.assertFalse((root / "notes-two.md").exists())

    def test_batch_import_rejects_duplicate_document_ids_before_writing(self) -> None:
        request = MarkdownCorpusBatchImportRequest.model_validate({
            "rights_confirmed": True,
            "files": [
                {"filename": "one.md", "content": _markdown("same-notes")},
                {"filename": "two.md", "content": _markdown("same-notes")},
            ],
        })
        with tempfile.TemporaryDirectory() as directory, patch.object(
            api, "USER_DATA_DIR", Path(directory)
        ):
            with self.assertRaises(HTTPException) as raised:
                api.import_markdown_batch(request)

            self.assertEqual(raised.exception.status_code, 422)
            self.assertIn("duplicate_document_id", str(raised.exception.detail))
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
