import json
import tempfile
import unittest
from pathlib import Path

from backend.corpus import (
    MarkdownCorpusValidationError,
    load_chunks,
    validate_corpus_payload,
    validate_markdown_corpus,
)
from backend.rag import RagIndex


class _EmbeddingClient:
    def embed(self, texts: list[str] | str) -> list[list[float]]:
        values = [texts] if isinstance(texts, str) else texts
        return [[1.0, float(index + 1)] for index, _ in enumerate(values)]


class _IncompleteEmbeddingClient:
    def embed(self, texts: list[str] | str) -> list[list[float]]:
        return []


class CorpusTests(unittest.TestCase):
    markdown = """---
schema: quiz-machine-corpus/v1
document_id: ai103-evaluation-notes
certification_code: AI-103
domain: Plan and manage an Azure AI solution
title: Evaluation notes
language: en
source_url: https://learn.microsoft.com/azure/ai-foundry/
learning_objective: Evaluate and select models for an AI solution
---

# Evaluation notes

## Quality criteria

Use representative test data and stable metrics to compare candidate models.

## Operational criteria

Measure latency, throughput, safety and cost before selecting a model.
"""

    def test_validates_and_loads_strict_markdown_corpus(self) -> None:
        summary = validate_markdown_corpus(self.markdown, "evaluation.md")
        self.assertEqual(summary["certification_code"], "AI-103")
        self.assertEqual(summary["chunk_count"], 2)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evaluation.md"
            path.write_text(self.markdown, encoding="utf-8")
            chunks = load_chunks(Path(directory))

        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["metadata"]["certification_code"], "AI-103")
        self.assertEqual(
            chunks[0]["metadata"]["domain"],
            "Plan and manage an Azure AI solution",
        )
        self.assertEqual(chunks[0]["metadata"]["source_type"], "imported_markdown")

    def test_markdown_validation_returns_actionable_issues(self) -> None:
        invalid = self.markdown.replace(
            "domain: Plan and manage an Azure AI solution",
            "domain: A domain that does not exist",
        ).replace("# Evaluation notes", "# A different title")

        with self.assertRaises(MarkdownCorpusValidationError) as raised:
            validate_markdown_corpus(invalid, "evaluation.md")

        codes = {issue.code for issue in raised.exception.issues}
        self.assertIn("invalid_domain", codes)
        self.assertIn("title_mismatch", codes)
        self.assertTrue(all(issue.message for issue in raised.exception.issues))

    def test_markdown_requires_frontmatter_and_md_extension(self) -> None:
        with self.assertRaises(MarkdownCorpusValidationError) as raised:
            validate_markdown_corpus("# Notes\n\n## Topic\n\nContent", "notes.txt")
        self.assertEqual(raised.exception.issues[0].code, "missing_frontmatter")

    def test_validates_and_loads_documented_format(self) -> None:
        payload = {
            "title": "My corpus",
            "language": "en",
            "chunks": [
                {
                    "id": "fact-1",
                    "content": "A self-contained fact.",
                    "topic": "Evaluation",
                    "domain": "AI solutions",
                }
            ],
        }
        self.assertEqual(validate_corpus_payload(payload)["chunk_count"], 1)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corpus.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            chunks = load_chunks(Path(directory))

        self.assertEqual(chunks[0]["chunk_id"], "fact-1")
        self.assertEqual(chunks[0]["metadata"]["domain"], "AI solutions")

    def test_rejects_duplicate_ids(self) -> None:
        payload = {
            "chunks": [
                {"id": "same", "content": "First"},
                {"id": "same", "content": "Second"},
            ]
        }
        with self.assertRaisesRegex(ValueError, "repeats the id"):
            validate_corpus_payload(payload)

    def test_rejects_empty_content(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            validate_corpus_payload({"chunks": [{"content": "  "}]})

    def test_validates_structured_chapters_without_timestamps(self) -> None:
        payload = {
            "metadata": {"title": "Structured notes", "language": "English"},
            "chapters": [
                {
                    "id": "chapter-1",
                    "start": None,
                    "topic": "Foundry model selection",
                    "exam_domain": "Generative AI",
                    "study_focus": ["Compare model quality, safety, cost, and latency."],
                }
            ],
        }

        summary = validate_corpus_payload(payload)

        self.assertEqual(summary["title"], "Structured notes")
        self.assertEqual(summary["language"], "English")
        self.assertEqual(summary["chunk_count"], 1)

    def test_catalog_exposes_every_structured_corpus_and_coverage(self) -> None:
        payloads = {
            "video.json": {
                "metadata": {"title": "Timed video"},
                "chapters": [
                    {
                        "id": "video-1",
                        "start": "00:10",
                        "topic": "Timed chapter",
                        "exam_domain": "Generative AI",
                        "study_focus": ["Use a timed source."],
                    }
                ],
            },
            "notes.json": {
                "metadata": {"title": "Untimed notes"},
                "chapters": [
                    {
                        "id": "notes-1",
                        "start": None,
                        "topic": "Untimed chapter",
                        "exam_domain": "Planning",
                        "study_focus": ["Use a structured source without timestamps."],
                    }
                ],
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "corpora"
            data_dir.mkdir()
            for filename, payload in payloads.items():
                (data_dir / filename).write_text(json.dumps(payload), encoding="utf-8")
            (data_dir / "patterns.json").write_text(
                json.dumps({
                    "title": "Question patterns",
                    "purpose": "question_patterns",
                    "patterns": [],
                }),
                encoding="utf-8",
            )
            index = RagIndex(
                _EmbeddingClient(),
                path=root / "index.json",
                data_dir=data_dir,
                knowledge_provider="local",
            )
            self.assertEqual(index.build(), 2)

            catalog = index.catalog()

        self.assertTrue(catalog["coverage"]["complete"])
        self.assertEqual(catalog["coverage"]["expected_sources"], 2)
        self.assertEqual(catalog["coverage"]["indexed_sources"], 2)
        self.assertEqual(len(catalog["chapters"]), 2)
        self.assertEqual(
            [source["status"] for source in catalog["sources"]].count("excluded"),
            1,
        )
        self.assertEqual(
            {chapter["source_title"] for chapter in catalog["chapters"]},
            {"Timed video", "Untimed notes"},
        )

    def test_index_build_rejects_ids_duplicated_across_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "corpora"
            data_dir.mkdir()
            for filename in ("first.json", "second.json"):
                (data_dir / filename).write_text(
                    json.dumps({
                        "chunks": [
                            {"id": "duplicate", "content": filename},
                        ]
                    }),
                    encoding="utf-8",
                )
            index = RagIndex(
                _EmbeddingClient(),
                path=root / "index.json",
                data_dir=data_dir,
                knowledge_provider="local",
            )

            with self.assertRaisesRegex(RuntimeError, "globally unique"):
                index.build()

    def test_index_build_rejects_incomplete_embedding_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "corpora"
            data_dir.mkdir()
            (data_dir / "corpus.json").write_text(
                json.dumps({"chunks": [{"id": "one", "content": "Fact"}]}),
                encoding="utf-8",
            )
            index = RagIndex(
                _IncompleteEmbeddingClient(),
                path=root / "index.json",
                data_dir=data_dir,
                knowledge_provider="local",
            )

            with self.assertRaisesRegex(RuntimeError, "coverage is incomplete"):
                index.build()

    def test_hybrid_merge_reserves_a_slot_for_local_corpus(self) -> None:
        local = [{"chunk_id": "local", "source": "local/notes.md", "text": "Local"}]
        official = [
            {"chunk_id": "learn-1", "source": "learn", "text": "Official 1"},
            {"chunk_id": "learn-2", "source": "learn", "text": "Official 2"},
            {"chunk_id": "learn-3", "source": "learn", "text": "Official 3"},
        ]

        merged = RagIndex._merge_hybrid(local, official, top_k=3)

        self.assertEqual([item["chunk_id"] for item in merged], [
            "local",
            "learn-1",
            "learn-2",
        ])

    def test_hybrid_scope_excludes_legacy_unscoped_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index = RagIndex(
                _EmbeddingClient(),
                path=root / "index.json",
                data_dir=root / "corpora",
                knowledge_provider="microsoft_learn_mcp",
                microsoft_corpus_path=root / "learn.json",
            )
            index.items = [
                {
                    "chunk_id": "legacy",
                    "source": "legacy.json",
                    "text": "Legacy",
                    "metadata": {"domain": "Plan and manage an Azure AI solution"},
                    "embedding": [1.0, 1.0],
                },
                {
                    "chunk_id": "scoped",
                    "source": "notes.md",
                    "text": "Scoped",
                    "metadata": {
                        "certification_code": "AI-103",
                        "domain": "Plan and manage an Azure AI solution",
                    },
                    "embedding": [1.0, 1.0],
                },
            ]

            scoped = index._scoped_local_items(
                "AI-103",
                "Plan and manage an Azure AI solution",
                explicit_scope_only=True,
            )

        self.assertEqual([item["chunk_id"] for item in scoped], ["scoped"])


if __name__ == "__main__":
    unittest.main()
