from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from requests import RequestException

from .config import (
    INDEX_PATH,
    KNOWLEDGE_PROVIDER,
    MICROSOFT_LEARN_CORPUS_PATH,
    MICROSOFT_LEARN_CORPUS_REFRESH_HOURS,
    MICROSOFT_LEARN_MCP_ENDPOINT,
    TOP_K,
)
from .certifications import certification, public_certifications
from .corpus import excluded_corpus_sources, load_chunks
from .microsoft_learn_mcp import MicrosoftLearnMcpClient
from .microsoft_learn_corpus import (
    MAX_CHUNK_CHARS,
    MAX_EVIDENCE_PACKET_CHARS,
    MicrosoftLearnCorpusStore,
    questionability_score,
)
from .ollama_client import OllamaClient, OllamaError


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _bounded_packet(items: list[dict]) -> list[dict]:
    bounded = []
    remaining = MAX_EVIDENCE_PACKET_CHARS
    for item in items:
        if remaining <= 0:
            break
        text = str(item.get("text") or "")
        limit = min(MAX_CHUNK_CHARS, remaining)
        if len(text) > limit:
            content_limit = max(1, limit - 1)
            boundary = text.rfind(" ", 0, content_limit + 1)
            if boundary < int(content_limit * 0.70):
                boundary = content_limit
            text = text[:boundary].rstrip() + ("…" if limit > 1 else "")
        if not text:
            continue
        bounded.append({**item, "text": text})
        remaining -= len(text)
    return bounded


class RagIndex:
    def __init__(
        self,
        client: OllamaClient,
        path: Path = INDEX_PATH,
        data_dir: Path | None = None,
        knowledge_provider: str = KNOWLEDGE_PROVIDER,
        microsoft_corpus_path: Path = MICROSOFT_LEARN_CORPUS_PATH,
    ):
        self.client = client
        self.path = path
        self.data_dir = data_dir
        self.microsoft_learn = (
            MicrosoftLearnMcpClient(MICROSOFT_LEARN_MCP_ENDPOINT)
            if knowledge_provider == "microsoft_learn_mcp"
            else None
        )
        self.microsoft_corpus = MicrosoftLearnCorpusStore(
            microsoft_corpus_path,
            refresh_hours=MICROSOFT_LEARN_CORPUS_REFRESH_HOURS,
        )
        self._knowledge_ready = False
        self._generation_status_cache: dict[str, dict] = {}
        self.items: list[dict] = []
        if path.exists():
            self.load()

    def load(self) -> None:
        self.items = json.loads(self.path.read_text(encoding="utf-8"))["items"]

    def build(self) -> int:
        chunks = load_chunks(self.data_dir)
        if not chunks:
            raise RuntimeError("No .json, .md or .txt files found in data/.")
        duplicate_ids = sorted(
            chunk_id
            for chunk_id, count in Counter(
                chunk["chunk_id"] for chunk in chunks
            ).items()
            if count > 1
        )
        if duplicate_ids:
            examples = ", ".join(duplicate_ids[:5])
            raise RuntimeError(
                "Corpus chunk IDs must be globally unique. "
                f"Duplicates: {examples}"
            )

        texts = [chunk["text"] for chunk in chunks]
        embeddings: list[list[float]] = []
        batch_size = 16
        for start in range(0, len(texts), batch_size):
            batch = texts[start:start + batch_size]
            embeddings.extend(self.client.embed(batch))
            print(f"Embedded {min(start + batch_size, len(texts))}/{len(texts)} chunks")

        if len(embeddings) != len(chunks):
            raise RuntimeError(
                "Embedding coverage is incomplete: "
                f"received {len(embeddings)} vectors for {len(chunks)} chunks."
            )

        new_items = []
        for chunk, embedding in zip(chunks, embeddings):
            new_items.append({**chunk, "embedding": embedding})

        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary_path.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "corpus_digest": _corpus_digest(chunks),
                    "items": new_items,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        temporary_path.replace(self.path)
        self.items = new_items
        return len(new_items)

    def search(
        self,
        query: str,
        top_k: int = TOP_K,
        domain: str | None = None,
        certification_code: str = "AI-103",
        learning_objective: str | None = None,
    ) -> list[dict]:
        if self.microsoft_learn is not None:
            selected = certification(certification_code)
            if not domain or not learning_objective:
                raise RuntimeError(
                    "Microsoft Learn retrieval requires one measured objective and domain."
                )
            return self.select_evidence_packet(
                query,
                certification_code=selected.code,
                domain=domain,
                learning_objective=learning_objective,
                top_k=top_k,
            )
        return self._search_local(
            query,
            top_k=top_k,
            domain=domain,
            certification_code=certification_code,
        )

    def _search_local(
        self,
        query: str,
        top_k: int,
        domain: str | None,
        certification_code: str,
        explicit_scope_only: bool = False,
    ) -> list[dict]:
        if not self.items:
            if self.path.exists():
                self.load()
            else:
                return []
        candidates = self._scoped_local_items(
            certification_code,
            domain,
            explicit_scope_only=explicit_scope_only,
        )
        if not candidates:
            return []
        query_vector = self.client.embed(query)[0]
        scored = [
            (cosine_similarity(query_vector, item["embedding"]), item)
            for item in candidates
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [self._public_item(item, score) for score, item in scored[:top_k]]

    def select_evidence_packet(
        self,
        query: str,
        *,
        certification_code: str,
        domain: str,
        learning_objective: str,
        top_k: int = TOP_K,
        exclude_chunk_ids: set[str] | None = None,
    ) -> list[dict]:
        """Build a small request-only packet from the broad canonical corpus."""
        selected = certification(certification_code)
        official = self.microsoft_corpus.select_evidence_packet(
            query,
            certification_code=selected.code,
            domain=domain,
            learning_objective=learning_objective,
            top_k=top_k,
            exclude_chunk_ids=exclude_chunk_ids,
        )
        local = []
        for item in self._local_objective_evidence(
            selected,
            {
                "domain": domain,
                "objective": learning_objective,
                "skill": learning_objective,
            },
        ):
            if str(item.get("chunk_id")) in (exclude_chunk_ids or set()):
                continue
            metadata = dict(item.get("metadata") or {})
            metadata.update(
                questionability_score=questionability_score(item),
                evidence_role="imported_anchor",
                canonical_chunk=True,
                request_scoped_window=True,
            )
            local.append({**item, "metadata": metadata})
        local.sort(
            key=lambda item: (
                (item.get("metadata") or {}).get("questionability_score", 0),
                str(item.get("chunk_id")),
            ),
            reverse=True,
        )
        merged = _bounded_packet(
            self._merge_hybrid(local[:1], official, max(1, min(top_k, 3)))
        )
        if not merged:
            raise RuntimeError(
                "The requested measured objective has no usable canonical evidence."
            )
        return merged

    def _scoped_local_items(
        self,
        certification_code: str,
        domain: str | None = None,
        explicit_scope_only: bool = False,
    ) -> list[dict]:
        if not self.items and self.path.exists():
            self.load()
        normalized_domain = _normalized(domain) if domain else None
        result = []
        for item in self.items:
            metadata = item.get("metadata") or {}
            item_certification = metadata.get("certification_code")
            if item_certification:
                if str(item_certification).upper() != certification_code.upper():
                    continue
            elif explicit_scope_only:
                continue
            elif certification_code.upper() != "AI-103":
                continue
            item_domain = metadata.get("domain")
            if (
                normalized_domain
                and item_domain
                and item_domain != "unknown"
                and _normalized(str(item_domain)) != normalized_domain
            ):
                continue
            result.append(item)
        return result

    @staticmethod
    def _merge_hybrid(
        local_results: list[dict],
        microsoft_results: list[dict],
        top_k: int,
    ) -> list[dict]:
        # Reserve one evidence slot for an imported corpus when it is in scope;
        # Microsoft Learn fills the remaining slots with official documentation.
        ordered = []
        if local_results:
            ordered.append(local_results[0])
        ordered.extend(microsoft_results)
        ordered.extend(local_results[1:])
        result = []
        seen = set()
        for item in ordered:
            key = item.get("chunk_id") or (item.get("source"), item.get("text"))
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
            if len(result) >= top_k:
                break
        return result

    def blueprint_objectives(
        self,
        certification_code: str,
        domain: str | None = None,
    ) -> list[str]:
        if self.microsoft_learn is None:
            return []
        selected = certification(certification_code)
        cached = self.microsoft_corpus.blueprint_objectives(selected.code, domain)
        if cached:
            return cached
        try:
            self._ensure_blueprint(selected)
            values = self.microsoft_corpus.blueprint_objectives(selected.code, domain)
        except (RequestException, RuntimeError, ValueError):
            values = []
        if values:
            return values
        return sorted({
            str((item.get("metadata") or {}).get("learning_objective")
                or (item.get("metadata") or {}).get("topic"))
            for item in self._scoped_local_items(
                selected.code,
                domain,
                explicit_scope_only=True,
            )
            if (item.get("metadata") or {}).get("learning_objective")
            or (item.get("metadata") or {}).get("topic")
        })

    def blueprint_domains(self, certification_code: str) -> list[str]:
        if self.microsoft_learn is None:
            return []
        selected = certification(certification_code)
        cached = self.microsoft_corpus.blueprint_domains(selected.code)
        if cached:
            return cached
        try:
            self._ensure_blueprint(selected)
            values = self.microsoft_corpus.blueprint_domains(selected.code)
        except (RequestException, RuntimeError, ValueError):
            values = []
        return values or list(selected.domains)

    def case_study_objectives(
        self,
        certification_code: str,
        domain: str | None = None,
    ) -> list[str]:
        normalized_domain = _normalized(domain) if domain else None
        status = self._generation_status_cache.get(certification_code)
        if status is None:
            status = self.microsoft_corpus.generation_status(certification_code)
        return [
            str(item["objective"])
            for item in status.get("objectives", [])
            if item.get("case_study_ready")
            and (
                normalized_domain is None
                or _normalized(str(item.get("domain") or "")) == normalized_domain
            )
        ]

    def _ensure_blueprint(self, selected) -> None:
        if not self.microsoft_corpus.blueprint_needs_refresh(selected.code):
            return
        markdown = self.microsoft_learn.fetch(selected.study_guide_url)
        if not markdown:
            rows = self.microsoft_learn.search(
                f"{selected.code} official study guide skills measured",
                limit=6,
            )
            exact = next(
                (
                    row
                    for row in rows
                    if str(row.get("url") or "").rstrip("/")
                    == selected.study_guide_url.rstrip("/")
                ),
                None,
            )
            if exact:
                markdown = str(
                    exact.get("fetched_content")
                    or exact.get("content")
                    or exact.get("text")
                    or ""
                ).strip() or self.microsoft_learn.fetch(selected.study_guide_url)
        if not markdown:
            raise RuntimeError(
                f"The official {selected.code} study guide could not be retrieved."
            )
        self.microsoft_corpus.update_blueprint(
            certification_code=selected.code,
            certification_title=selected.title,
            study_guide_url=selected.study_guide_url,
            markdown=markdown,
        )

    def prepare_generation_corpus(
        self,
        certification_code: str,
        *,
        progress=None,
        cancelled=None,
    ) -> dict:
        """Ensure the canonical corpus covers every measured objective."""
        selected = certification(certification_code)
        if self.microsoft_learn is None:
            return {"ready": True, "objective_count": 0, "chunk_count": 0}

        current = self._generation_status_cache.get(selected.code)
        if current is None:
            current = self.microsoft_corpus.generation_status(selected.code)
        if current["ready"]:
            self._generation_status_cache[selected.code] = current
            if progress:
                progress(
                    current["objective_count"],
                    current["objective_count"],
                    f"Canonical {selected.code} corpus is ready.",
                )
            return current
        if progress:
            progress(0, 0, f"Loading the official {selected.code} blueprint...")
        self._ensure_blueprint(selected)
        entries = self.microsoft_corpus.blueprint_entries(selected.code)
        if not entries:
            raise RuntimeError(
                f"The official {selected.code} blueprint contains no measured objectives."
            )

        total = len(entries)
        for index, entry in enumerate(entries):
            if cancelled and cancelled():
                raise RuntimeError("Corpus preparation cancelled.")
            if progress:
                progress(
                    index,
                    total,
                    f"Indexing evidence for objective {index + 1} of {total}...",
                )
            self._prepare_official_objective(selected, entry)

        status = self.microsoft_corpus.generation_status(selected.code)
        if not status["ready"]:
            missing = [
                item["objective"]
                for item in status["objectives"]
                if not item["ready"]
            ]
            raise RuntimeError(
                "The canonical corpus still lacks usable evidence for: "
                + "; ".join(missing[:4])
            )
        if progress:
            progress(total, total, f"Canonical {selected.code} corpus is ready.")
        self._generation_status_cache[selected.code] = status
        return status

    def _prepare_official_objective(self, selected, entry: dict) -> list[dict]:
        domain = entry["domain"]
        objective = entry["objective"]
        cached = self.microsoft_corpus.scoped_chunks(
            selected.code,
            domain,
            objective,
        )
        quality = self.microsoft_corpus.questionability_index(
            selected.code,
            domain,
            objective,
        )
        if len(cached) >= 2 and any(item["eligible"] for item in quality):
            return cached
        refresh = self.microsoft_corpus.needs_refresh(
            selected.code,
            domain,
            objective,
        )

        queries = (
            f"{selected.code} {objective}",
            f"{selected.title} {domain} {objective} requirements limitations",
            f"Microsoft Learn {entry.get('skill') or domain} {objective} when to use",
        )
        replace_scope = refresh
        for query in queries:
            rows = self.microsoft_learn.search(query, limit=6)
            enriched = []
            for index, row in enumerate(rows):
                item = dict(row)
                if index < 4:
                    try:
                        fetched = self.microsoft_learn.fetch(
                            str(row.get("url") or "")
                        )
                    except (RequestException, RuntimeError, ValueError):
                        fetched = None
                    if fetched:
                        item["fetched_content"] = fetched
                enriched.append(item)
            self.microsoft_corpus.ingest(
                certification_code=selected.code,
                certification_title=selected.title,
                domain=domain,
                learning_objective=objective,
                rows=enriched,
                replace_scope=replace_scope,
            )
            replace_scope = False
            cached = self.microsoft_corpus.scoped_chunks(
                selected.code,
                domain,
                objective,
            )
            quality = self.microsoft_corpus.questionability_index(
                selected.code,
                domain,
                objective,
            )
            if len(cached) >= 2 and any(item["eligible"] for item in quality):
                break
        return cached

    def _local_objective_evidence(self, selected, entry: dict) -> list[dict]:
        result = []
        for item in self._scoped_local_items(
            selected.code,
            entry["domain"],
            explicit_scope_only=True,
        ):
            metadata = item.get("metadata") or {}
            if _normalized(str(metadata.get("learning_objective") or "")) != _normalized(
                entry["objective"]
            ):
                continue
            source_url = str(metadata.get("source_url") or "")
            if not source_url.startswith("https://learn.microsoft.com/"):
                continue
            result.append({
                **self._public_item(item, 1.0),
                "source": source_url,
                "metadata": {
                    **metadata,
                    "certification": selected.code,
                    "domain": entry["domain"],
                    "exam_domain": entry["domain"],
                    "skill_group": entry.get("skill") or entry["objective"],
                    "skill_objective": entry["objective"],
                    "learning_objective": entry["objective"],
                    "blueprint_aligned": True,
                    "blueprint_source_url": selected.study_guide_url,
                    "source_url": source_url,
                },
            })
        return result

    @staticmethod
    def _dedupe_evidence(items: list[dict]) -> list[dict]:
        result = []
        seen = set()
        for item in items:
            key = (
                str(item.get("source") or ""),
                _normalized(str(item.get("text") or "")),
            )
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    def invalidate_generation_corpus(self, certification_code: str) -> None:
        # Evidence packets are request-scoped views over canonical chunks, so
        # there is no derived corpus to invalidate after an import.
        self._generation_status_cache.pop(certification_code, None)

    def get(self, chunk_id: str) -> dict | None:
        if not self.items:
            if self.path.exists():
                self.load()
            else:
                raise RuntimeError("Index not found. Run `python build_index.py` first.")
        for item in self.items:
            if item.get("chunk_id") == chunk_id:
                return self._public_item(item, 1.0)
        return None

    def catalog(self, certification_code: str = "AI-103") -> dict:
        selected = certification(certification_code)
        if self.microsoft_learn is not None:
            existing_status = self.microsoft_corpus.generation_status(selected.code)
            if not existing_status["ready"]:
                try:
                    self._ensure_blueprint(selected)
                except (RequestException, RuntimeError, ValueError):
                    if not self.microsoft_corpus.blueprint_entries(
                        selected.code
                    ) and not self._scoped_local_items(
                        selected.code,
                        explicit_scope_only=True,
                    ):
                        raise
            expected_local = [
                item for item in load_chunks(self.data_dir)
                if self._item_matches_certification(
                    item,
                    selected.code,
                    explicit_scope_only=True,
                )
            ]
            indexed_local = self._scoped_local_items(
                selected.code,
                explicit_scope_only=True,
            )
            local_coverage = _coverage(expected_local, indexed_local)
            local_complete = not expected_local or local_coverage["complete"]
            local_sources = local_coverage.pop("sources")
            corpus_status = self.microsoft_corpus.generation_status(selected.code)
            objectives = self.microsoft_corpus.blueprint_entries(selected.code)
            canonical_source = {
                "id": f"official:{selected.code}",
                "title": f"{selected.code} canonical Microsoft Learn corpus",
                "status": "indexed" if corpus_status["ready"] else "missing",
                "expected_chunks": max(
                    len(objectives) * 2,
                    corpus_status["chunk_count"],
                ),
                "indexed_chunks": corpus_status["chunk_count"],
                "chapter_count": 0,
                "domains": self.microsoft_corpus.blueprint_domains(selected.code),
            }
            sources = [canonical_source, *local_sources]
            indexed_chunks = sum(source["indexed_chunks"] for source in sources)
            expected_chunks = sum(source["expected_chunks"] for source in sources)
            indexed_sources = sum(source["status"] == "indexed" for source in sources)
            domains = self.microsoft_corpus.blueprint_domains(selected.code)
            return {
                "certifications": public_certifications(),
                "selected_certification": selected.public_dict(),
                "knowledge_provider": "hybrid" if local_sources else "microsoft_learn_mcp",
                "domains": domains or list(selected.domains),
                "chapters": [],
                "sources": sources,
                "coverage": {
                    "complete": corpus_status["ready"] and local_complete,
                    "expected_sources": len(sources),
                    "indexed_sources": indexed_sources,
                    "expected_chunks": expected_chunks,
                    "indexed_chunks": indexed_chunks,
                },
            }
        if selected.code != "AI-103":
            raise RuntimeError(
                "The offline fallback corpus currently supports AI-103 only."
            )
        if not self.items:
            if self.path.exists():
                self.load()
            else:
                raise RuntimeError("Index not found. Run `python build_index.py` first.")

        domains = sorted({
            (item.get("metadata") or {}).get("domain")
            for item in self.items
            if (item.get("metadata") or {}).get("domain")
            and (item.get("metadata") or {}).get("domain") != "unknown"
        })

        chapters = []
        seen = set()
        source_positions: defaultdict[str, int] = defaultdict(int)
        for item in self.items:
            meta = item.get("metadata") or {}
            # Structured chapters remain navigable even when they are not tied to
            # a video timeline. Markdown windows and generic chunks stay out.
            if (
                meta.get("navigation_kind") != "chapter"
                and "timestamp_start" not in meta
            ):
                continue
            cid = item.get("chunk_id")
            if not cid or cid in seen:
                continue
            seen.add(cid)
            source_id = item.get("source", "Unknown source")
            position = meta.get("chapter_index")
            if not isinstance(position, int):
                position = source_positions[source_id]
            source_positions[source_id] += 1
            chapters.append({
                "id": cid,
                "topic": meta.get("topic", "Unknown topic"),
                "domain": meta.get("domain", "Unknown domain"),
                "start": meta.get("timestamp_start"),
                "end": meta.get("timestamp_end"),
                "priority": meta.get("priority"),
                "source_id": source_id,
                "source_title": meta.get("source_title") or source_id,
                "position": position,
            })

        chapters.sort(key=lambda chapter: (
            chapter["source_title"].casefold(),
            chapter["position"],
        ))
        coverage = _coverage(
            load_chunks(self.data_dir),
            self.items,
            excluded_corpus_sources(self.data_dir),
        )
        return {
            "certifications": public_certifications(),
            "selected_certification": selected.public_dict(),
            "knowledge_provider": "local",
            "domains": domains,
            "chapters": chapters,
            "sources": coverage.pop("sources"),
            "coverage": coverage,
        }

    @property
    def uses_microsoft_learn(self) -> bool:
        return self.microsoft_learn is not None

    @property
    def knowledge_provider(self) -> str:
        if self.uses_microsoft_learn and self.has_scoped_local_corpus:
            return "hybrid"
        return "microsoft_learn_mcp" if self.uses_microsoft_learn else "local"

    @property
    def indexed_chunk_count(self) -> int:
        if not self.uses_microsoft_learn:
            return len(self.items)
        scoped_local_count = sum(
            bool((item.get("metadata") or {}).get("certification_code"))
            for item in self.items
        )
        return scoped_local_count + self.microsoft_corpus.count()

    @property
    def has_local_corpus(self) -> bool:
        if self.items:
            return True
        try:
            return bool(load_chunks(self.data_dir))
        except (OSError, ValueError, json.JSONDecodeError):
            return False

    @property
    def has_scoped_local_corpus(self) -> bool:
        if self.has_indexed_scoped_local_corpus:
            return True
        try:
            chunks = load_chunks(self.data_dir)
        except (OSError, ValueError, json.JSONDecodeError):
            return False
        return any(
            bool((item.get("metadata") or {}).get("certification_code"))
            for item in chunks
        )

    @property
    def has_indexed_scoped_local_corpus(self) -> bool:
        return any(
            bool((item.get("metadata") or {}).get("certification_code"))
            for item in self.items
        )

    @property
    def requires_local_embeddings(self) -> bool:
        return not self.uses_microsoft_learn or self.has_scoped_local_corpus

    def test_knowledge_provider(self) -> None:
        if self.microsoft_learn is not None:
            self.microsoft_learn.test_connection()
            self._knowledge_ready = True

    @property
    def knowledge_ready(self) -> bool:
        if self.uses_microsoft_learn:
            return (
                self._knowledge_ready
                or self.microsoft_corpus.count() > 0
                or self.has_indexed_scoped_local_corpus
            )
        return bool(self.items)

    @staticmethod
    def _item_matches_certification(
        item: dict,
        certification_code: str,
        explicit_scope_only: bool = False,
    ) -> bool:
        item_certification = (item.get("metadata") or {}).get("certification_code")
        if item_certification:
            return str(item_certification).upper() == certification_code.upper()
        if explicit_scope_only:
            return False
        return certification_code.upper() == "AI-103"

    @staticmethod
    def _public_item(item: dict, score: float) -> dict:
        return {
            "score": round(score, 5),
            "chunk_id": item["chunk_id"],
            "source": item["source"],
            "text": item["text"],
            "metadata": item.get("metadata", {}),
        }


def _corpus_digest(chunks: list[dict]) -> str:
    canonical = [
        {
            "chunk_id": item.get("chunk_id"),
            "source": item.get("source"),
            "text": item.get("text"),
            "metadata": item.get("metadata") or {},
        }
        for item in chunks
    ]
    canonical.sort(key=lambda item: (str(item["source"]), str(item["chunk_id"])))
    serialized = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _coverage(
    expected: list[dict],
    indexed: list[dict],
    excluded: list[dict] | None = None,
) -> dict:
    expected_by_source: defaultdict[str, list[dict]] = defaultdict(list)
    indexed_by_source: defaultdict[str, list[dict]] = defaultdict(list)
    for item in expected:
        expected_by_source[item["source"]].append(item)
    for item in indexed:
        indexed_by_source[item["source"]].append(item)

    sources = []
    for source_id in sorted(
        set(expected_by_source) | set(indexed_by_source),
        key=str.casefold,
    ):
        expected_items = expected_by_source[source_id]
        indexed_items = indexed_by_source[source_id]
        if not expected_items:
            status = "stale"
        elif not indexed_items:
            status = "missing"
        elif _corpus_digest(expected_items) == _corpus_digest(indexed_items):
            status = "indexed"
        else:
            status = "stale"

        representative = (expected_items or indexed_items)[0]
        metadata = representative.get("metadata") or {}
        chapters = [
            item
            for item in expected_items
            if (item.get("metadata") or {}).get("navigation_kind") == "chapter"
            or "timestamp_start" in (item.get("metadata") or {})
        ]
        domains = sorted({
            (item.get("metadata") or {}).get("domain")
            for item in expected_items
            if (item.get("metadata") or {}).get("domain")
            not in {None, "unknown"}
        })
        sources.append({
            "id": source_id,
            "title": metadata.get("source_title") or source_id,
            "status": status,
            "expected_chunks": len(expected_items),
            "indexed_chunks": len(indexed_items),
            "chapter_count": len(chapters),
            "domains": domains,
        })

    for source in excluded or []:
        sources.append({
            "id": source["id"],
            "title": source["title"],
            "status": "excluded",
            "expected_chunks": 0,
            "indexed_chunks": 0,
            "chapter_count": 0,
            "domains": [],
            "reason": source["reason"],
        })
    sources.sort(key=lambda source: source["title"].casefold())

    current_sources = sum(source["status"] == "indexed" for source in sources)
    expected_sources = len(expected_by_source)
    return {
        "complete": bool(expected) and all(
            source["status"] in {"indexed", "excluded"} for source in sources
        ),
        "expected_sources": expected_sources,
        "indexed_sources": current_sources,
        "expected_chunks": len(expected),
        "indexed_chunks": len(indexed),
        "sources": sources,
    }
