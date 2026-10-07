from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from backend.microsoft_learn_corpus import (
    MAX_CHUNK_CHARS,
    MAX_EVIDENCE_PACKET_CHARS,
    MicrosoftLearnCorpusStore,
    questionability_score,
)
from backend.rag import RagIndex


_STUDY_GUIDE_URL = (
    "https://learn.microsoft.com/credentials/certifications/resources/study-guides/ai-200"
)
_OBJECTIVE = "Use pgvector with relational data"
_DOMAIN = "Develop AI solutions by using Azure data management services"
_BLUEPRINT = f"""
## Skills measured

### Audience profile

- Developers who build cloud solutions

### Skills at a glance

- General familiarity with Azure

### {_DOMAIN} (20-25%)

#### Implement relational and non-relational storage

- {_OBJECTIVE}
- Select relational or non-relational data services for a workload

## Study resources
"""


def _seed_blueprint(store: MicrosoftLearnCorpusStore) -> None:
    store.update_blueprint(
        certification_code="AI-200",
        certification_title="Developing AI Cloud Solutions on Azure",
        study_guide_url=_STUDY_GUIDE_URL,
        markdown=_BLUEPRINT,
    )


class _LearnMcp:
    def __init__(self) -> None:
        self.fetch_calls: list[str] = []
        self.search_calls: list[str] = []

    def fetch(self, url: str) -> str:
        self.fetch_calls.append(url)
        if url == _STUDY_GUIDE_URL:
            return _BLUEPRINT
        if url.endswith("/considerations"):
            return (
                "# Storage decisions\n\nUse pgvector only when vector data belongs "
                "with relational records. Choose relational storage when schemas, "
                "joins, and transactions are required. Choose non-relational "
                "storage when flexible records and workload-specific scale are "
                "the decisive constraints for the application."
            )
        return (
            "# Query vectors\n\nUse pgvector with relational data and SQL when "
            "the workload must combine vector similarity with transactional rows. "
            "Choose a dedicated search index instead when independent search "
            "features and document-oriented enrichment are the primary requirement."
        )

    def search(self, query: str, limit: int = 6) -> list[dict]:
        self.search_calls.append(query)
        return [
            {
                "title": "Use pgvector with relational data",
                "url": (
                    "https://learn.microsoft.com/training/modules/"
                    "postgresql-vector-search/query-vectors"
                ),
                "content": (
                    "Use pgvector with relational data and SQL when vector values "
                    "must remain beside transactional records and constraints."
                ),
            },
            {
                "title": "Choose pgvector, relational, or non-relational storage",
                "url": "https://learn.microsoft.com/azure/storage/considerations",
                "content": (
                    "Choose relational storage when schemas, joins, and transactions "
                    "are required. Choose non-relational storage when flexible records "
                    "and workload-specific scale are the decisive constraints."
                ),
            },
        ]


class MicrosoftLearnCorpusTests(unittest.TestCase):
    def test_questionability_favors_decision_ready_evidence(self) -> None:
        metadata = {
            "skill_objective": _OBJECTIVE,
            "topic": "Storage decisions",
            "module": "postgresql-vector-search",
            "unit": "choose-storage",
        }
        useful = {
            "text": (
                "Use pgvector with relational data when transactions and SQL joins "
                "are required. Choose a dedicated search index instead when search "
                "enrichment and an independent document index are the priority."
            ),
            "metadata": metadata,
        }
        noisy = {"text": "Overview next previous", "metadata": metadata}

        self.assertGreater(questionability_score(useful), questionability_score(noisy))

    def test_rag_prepares_canonical_corpus_and_builds_temporary_packet(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rag = RagIndex(
                client=None,
                path=root / "index.json",
                knowledge_provider="microsoft_learn_mcp",
                microsoft_corpus_path=root / "learn.json",
            )
            learn = _LearnMcp()
            rag.microsoft_learn = learn

            status = rag.prepare_generation_corpus("AI-200")
            calls_after_preparation = len(learn.search_calls)
            fetches_after_preparation = len(learn.fetch_calls)
            repeated_status = rag.prepare_generation_corpus("AI-200")
            rows = rag.search(
                "pgvector relational SQL",
                certification_code="AI-200",
                domain=_DOMAIN,
                learning_objective=_OBJECTIVE,
                top_k=3,
            )

        self.assertTrue(status["ready"])
        self.assertTrue(repeated_status["ready"])
        self.assertEqual(learn.fetch_calls[0], _STUDY_GUIDE_URL)
        self.assertGreater(calls_after_preparation, 0)
        self.assertEqual(len(learn.search_calls), calls_after_preparation)
        self.assertEqual(len(learn.fetch_calls), fetches_after_preparation)
        self.assertTrue(rows)
        self.assertEqual(rows[0]["metadata"]["skill_objective"], _OBJECTIVE)
        self.assertTrue(rows[0]["metadata"]["canonical_chunk"])
        self.assertTrue(rows[0]["metadata"]["request_scoped_window"])
        self.assertIn(rows[0]["metadata"]["evidence_role"], {"anchor", "related"})
        self.assertLessEqual(len(rows[0]["text"]), MAX_CHUNK_CHARS)

    def test_blueprint_uses_only_weighted_measured_domains(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = MicrosoftLearnCorpusStore(Path(directory) / "learn.json")
            _seed_blueprint(store)

            entries = store.blueprint_entries("AI-200")

        self.assertEqual(len(entries), 2)
        self.assertEqual({item["domain"] for item in entries}, {_DOMAIN})

    def test_rejects_learn_content_outside_measured_objectives(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = MicrosoftLearnCorpusStore(Path(directory) / "learn.json")
            _seed_blueprint(store)

            count = store.ingest(
                certification_code="AI-200",
                certification_title="Developing AI Cloud Solutions on Azure",
                domain=_DOMAIN,
                learning_objective="Configure quantum computing workspaces",
                rows=[
                    {
                        "title": "Azure quantum workspaces",
                        "url": "https://learn.microsoft.com/azure/quantum/workspaces",
                        "content": "Configure and manage a quantum workspace.",
                    }
                ],
            )

        self.assertEqual(count, 0)

    def test_persists_semantic_chunks_with_full_scope_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "learn-corpus.json"
            store = MicrosoftLearnCorpusStore(path)
            _seed_blueprint(store)

            count = store.ingest(
                certification_code="AI-200",
                certification_title="Developing AI Cloud Solutions on Azure",
                domain=_DOMAIN,
                learning_objective=_OBJECTIVE,
                rows=[
                    {
                        "title": "Store and search vectors",
                        "url": (
                            "https://learn.microsoft.com/training/modules/"
                            "postgresql-vector-search/query-vectors"
                        ),
                        "fetched_content": (
                            "# Store embeddings\n\nUse pgvector for relational vector data.\n\n"
                            "# Query embeddings\n\nUse SQL operators for similarity search."
                        ),
                    }
                ],
            )

            payload = json.loads(path.read_text(encoding="utf-8"))
            results = store.search(
                "pgvector relational SQL",
                certification_code="AI-200",
                domain=_DOMAIN,
                top_k=3,
            )

        self.assertEqual(count, 2)
        self.assertEqual(len(payload["chunks"]), 2)
        self.assertTrue(results)
        metadata = results[0]["metadata"]
        self.assertEqual(metadata["certification"], "AI-200")
        self.assertEqual(metadata["module"], "postgresql-vector-search")
        self.assertEqual(metadata["unit"], "query-vectors")
        self.assertEqual(metadata["learning_objective"], _OBJECTIVE)
        self.assertTrue(metadata["blueprint_aligned"])
        self.assertEqual(metadata["blueprint_source_url"], _STUDY_GUIDE_URL)
        self.assertTrue(metadata["source_id"].startswith("learn:"))

    def test_fresh_scope_is_reused_without_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = MicrosoftLearnCorpusStore(Path(directory) / "learn.json")
            _seed_blueprint(store)
            store.ingest(
                certification_code="AI-200",
                certification_title="AI-200",
                domain=_DOMAIN,
                learning_objective=_OBJECTIVE,
                rows=[
                    {
                        "title": "Vectors",
                        "url": "https://learn.microsoft.com/azure/postgresql/vectors",
                        "content": "PostgreSQL supports relational vector search with pgvector.",
                    }
                ],
            )

            self.assertFalse(
                store.needs_refresh("AI-200", _DOMAIN, _OBJECTIVE)
            )
            self.assertTrue(store.needs_refresh("AI-103", "Other domain"))

    def test_stale_scope_requires_refresh_but_cached_chunks_remain_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "learn.json"
            store = MicrosoftLearnCorpusStore(path, refresh_hours=1)
            _seed_blueprint(store)
            store.ingest(
                certification_code="AI-200",
                certification_title="AI-200",
                domain=_DOMAIN,
                learning_objective=_OBJECTIVE,
                rows=[
                    {
                        "title": "Vectors",
                        "url": "https://learn.microsoft.com/azure/postgresql/vectors",
                        "content": "PostgreSQL supports relational vector search with pgvector.",
                    }
                ],
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["scopes"][f"AI-200|{_DOMAIN}|{_OBJECTIVE}"] = (
                datetime.now(timezone.utc) - timedelta(hours=2)
            ).isoformat()
            path.write_text(json.dumps(payload), encoding="utf-8")

            self.assertTrue(
                store.needs_refresh("AI-200", _DOMAIN, _OBJECTIVE)
            )
            self.assertTrue(
                store.search(
                    "PostgreSQL pgvector",
                    certification_code="AI-200",
                    domain=_DOMAIN,
                    top_k=3,
                    learning_objective=_OBJECTIVE,
                )
            )

    def test_merge_keeps_prior_scope_chunks_and_bounds_long_source_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "learn.json"
            store = MicrosoftLearnCorpusStore(path)
            _seed_blueprint(store)
            common = {
                "certification_code": "AI-200",
                "certification_title": "AI-200",
                "domain": _DOMAIN,
                "learning_objective": _OBJECTIVE,
            }
            store.ingest(
                **common,
                rows=[{
                    "title": "First topic",
                    "url": "https://learn.microsoft.com/azure/first",
                    "content": "pgvector relational database evidence",
                }],
            )
            store.ingest(
                **common,
                replace_scope=False,
                rows=[{
                    "title": "Second topic",
                    "url": "https://learn.microsoft.com/azure/second",
                    "content": "pgvector relational vector data " * 1000,
                }],
            )
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertGreater(len(payload["chunks"]), 2)
        self.assertTrue(
            all(len(chunk["text"]) <= MAX_CHUNK_CHARS for chunk in payload["chunks"])
        )
        self.assertEqual(
            {chunk["source"] for chunk in payload["chunks"]},
            {
                "https://learn.microsoft.com/azure/first",
                "https://learn.microsoft.com/azure/second",
            },
        )

    def test_evidence_packet_is_bounded_and_keeps_canonical_chunk_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = MicrosoftLearnCorpusStore(Path(directory) / "learn.json")
            _seed_blueprint(store)
            rows = [
                {
                    "title": f"Storage choice {index}",
                    "url": f"https://learn.microsoft.com/azure/storage/choice-{index}",
                    "content": (
                        "Use pgvector with relational data when transactions, joins, "
                        "and SQL constraints are required. Choose another service "
                        "instead when an independent document search index is required. "
                    )
                    * 20,
                }
                for index in range(3)
            ]
            store.ingest(
                certification_code="AI-200",
                certification_title="AI-200",
                domain=_DOMAIN,
                learning_objective=_OBJECTIVE,
                rows=rows,
            )

            packet = store.select_evidence_packet(
                "pgvector relational requirements constraints",
                certification_code="AI-200",
                domain=_DOMAIN,
                learning_objective=_OBJECTIVE,
                top_k=3,
            )

        self.assertGreaterEqual(len(packet), 2)
        self.assertLessEqual(len(packet), 3)
        self.assertLessEqual(
            sum(len(item["text"]) for item in packet),
            MAX_EVIDENCE_PACKET_CHARS,
        )
        self.assertEqual(packet[0]["metadata"]["evidence_role"], "anchor")
        self.assertTrue(all(item["metadata"]["canonical_chunk"] for item in packet))


if __name__ == "__main__":
    unittest.main()
