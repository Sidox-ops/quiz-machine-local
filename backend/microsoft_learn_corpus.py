from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import random
import re
from pathlib import Path
from urllib.parse import urlparse


MAX_CHUNK_CHARS = 2200
MAX_EVIDENCE_PACKET_CHARS = 5200
MIN_QUESTIONABLE_SCORE = 0.34
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9.+#-]{2,}", re.IGNORECASE)
_BLUEPRINT_NOISE = {
    "azure",
    "develop",
    "implement",
    "manage",
    "microsoft",
    "plan",
    "solution",
    "solutions",
    "the",
    "use",
    "using",
}
_DECISION_MARKERS = {
    "choose",
    "consider",
    "constraint",
    "instead",
    "limit",
    "only",
    "recommend",
    "require",
    "support",
    "when",
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _tokens(value: str) -> Counter[str]:
    return Counter(token.casefold() for token in _TOKEN_RE.findall(value))


def _normalized(value: str) -> str:
    return " ".join(_TOKEN_RE.findall(value.casefold()))


def _plain_markdown(value: str) -> str:
    value = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", value)
    value = value.replace("**", "").replace("__", "").replace("`", "")
    return re.sub(r"\s+", " ", value).strip()


def _domain_heading(value: str) -> str:
    return re.sub(r"\s*\([^)]*%[^)]*\)\s*$", "", _plain_markdown(value)).strip()


def parse_study_guide(markdown: str) -> list[dict[str, str]]:
    """Extract measured domain/skill/objective rows from a Learn study guide."""
    in_skills = False
    current_domain: str | None = None
    current_skill: str | None = None
    objectives: list[dict[str, str]] = []

    for raw_line in markdown.replace("\r\n", "\n").splitlines():
        heading = re.match(r"^(#{2,4})\s+(.+?)\s*$", raw_line)
        if heading:
            level = len(heading.group(1))
            title = _plain_markdown(heading.group(2))
            normalized_title = _normalized(title)
            if level == 2 and "skills measured" in normalized_title:
                in_skills = True
                current_domain = None
                current_skill = None
                continue
            if level == 2 and in_skills:
                break
            if not in_skills:
                continue
            if level == 3:
                current_domain = (
                    _domain_heading(title)
                    if re.search(r"\([^)]*%[^)]*\)\s*$", title)
                    else None
                )
                current_skill = None
            elif level == 4 and current_domain:
                current_skill = _plain_markdown(title)
            continue

        if not in_skills or not current_domain:
            continue
        bullet = re.match(r"^\s*[-*]\s+(.+?)\s*$", raw_line)
        if not bullet:
            continue
        objective = _plain_markdown(bullet.group(1))
        if not objective:
            continue
        objectives.append(
            {
                "domain": current_domain,
                "skill": current_skill or objective,
                "objective": objective,
            }
        )

    deduped: dict[tuple[str, str], dict[str, str]] = {}
    for item in objectives:
        key = (_normalized(item["domain"]), _normalized(item["objective"]))
        deduped[key] = item
    return list(deduped.values())


def _blueprint_relevance(objective: str, row: dict) -> float:
    objective_tokens = {
        token
        for token in _tokens(objective)
        if token not in _BLUEPRINT_NOISE
    }
    searchable = " ".join(
        str(row.get(key) or "")
        for key in ("title", "url", "fetched_content", "content", "snippet", "text")
    )
    searchable_tokens = set(_tokens(searchable))
    if not objective_tokens:
        return 0.0
    overlap = len(objective_tokens & searchable_tokens)
    required_overlap = 1 if len(objective_tokens) <= 2 else 2
    if overlap < required_overlap:
        return 0.0
    return overlap / len(objective_tokens)


def questionability_score(chunk: dict) -> float:
    """Estimate whether a raw chunk can support one discriminating question."""
    text = _plain_markdown(str(chunk.get("text") or ""))
    metadata = chunk.get("metadata") or {}
    if not text:
        return 0.0
    tokens = _tokens(text)
    token_count = sum(tokens.values())
    objective_tokens = set(
        _tokens(str(metadata.get("skill_objective") or ""))
    ) - _BLUEPRINT_NOISE
    overlap = len(objective_tokens & set(tokens)) / max(len(objective_tokens), 1)
    length_score = min(token_count / 90, 1.0)
    if token_count > 430:
        length_score *= max(0.45, 1 - ((token_count - 430) / 900))
    decision_score = min(
        sum(tokens.get(marker, 0) for marker in _DECISION_MARKERS) / 4,
        1.0,
    )
    structure_score = sum(
        bool(metadata.get(key)) for key in ("module", "unit", "topic")
    ) / 3
    unique_ratio = len(tokens) / max(token_count, 1)
    repetition_penalty = max(0.0, 0.35 - unique_ratio)
    score = (
        0.34 * length_score
        + 0.31 * overlap
        + 0.22 * decision_score
        + 0.13 * structure_score
        - repetition_penalty
    )
    return round(max(0.0, min(score, 1.0)), 5)


def _bounded_evidence_text(value: str, remaining: int) -> str:
    """Create a request-scoped window without creating another stored corpus."""
    limit = max(0, min(MAX_CHUNK_CHARS, remaining))
    if limit == 0:
        return ""
    if len(value) <= limit:
        return value
    content_limit = max(1, limit - 1)
    boundary = value.rfind(" ", 0, content_limit + 1)
    if boundary < int(limit * 0.70):
        boundary = content_limit
    return value[:boundary].rstrip() + ("…" if limit > 1 else "")


def _source_id(url: str) -> str:
    return "learn:" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]


def _chunk_id(scope: str, url: str, heading: str, content: str) -> str:
    value = f"{scope}\n{url}\n{heading}\n{content}".encode("utf-8")
    return "mcp:" + hashlib.sha256(value).hexdigest()[:24]


def _url_metadata(url: str) -> dict[str, str | None]:
    parts = [part for part in urlparse(url).path.split("/") if part]
    metadata: dict[str, str | None] = {
        "learning_path": None,
        "module": None,
        "unit": None,
    }
    try:
        training_index = parts.index("training")
    except ValueError:
        return metadata
    tail = parts[training_index + 1 :]
    if len(tail) >= 2 and tail[0] == "paths":
        metadata["learning_path"] = tail[1]
    elif len(tail) >= 2 and tail[0] == "modules":
        metadata["module"] = tail[1]
        if len(tail) >= 3:
            metadata["unit"] = tail[2]
    return metadata


def _bounded_fragments(value: str) -> list[str]:
    """Keep even punctuation-free source blocks inside the context budget."""
    fragments: list[str] = []
    remaining = value.strip()
    while len(remaining) > MAX_CHUNK_CHARS:
        boundary = remaining.rfind(" ", 0, MAX_CHUNK_CHARS + 1)
        if boundary <= 0:
            boundary = MAX_CHUNK_CHARS
        fragments.append(remaining[:boundary].strip())
        remaining = remaining[boundary:].strip()
    if remaining:
        fragments.append(remaining)
    return fragments


def _semantic_sections(markdown: str, fallback_topic: str) -> list[tuple[str, str]]:
    """Split fetched Learn markdown at headings and paragraph boundaries."""
    normalized = re.sub(r"\r\n?", "\n", markdown).strip()
    if not normalized:
        return []
    raw_sections = re.split(r"(?=^#{1,4}\s+)", normalized, flags=re.MULTILINE)
    sections: list[tuple[str, str]] = []
    for raw in raw_sections:
        raw = raw.strip()
        if not raw:
            continue
        first_line = raw.splitlines()[0]
        match = re.match(r"^#{1,4}\s+(.+)$", first_line)
        heading = match.group(1).strip() if match else fallback_topic
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", raw) if part.strip()]
        current: list[str] = []
        current_size = 0
        for paragraph in paragraphs:
            if current and current_size + len(paragraph) + 2 > MAX_CHUNK_CHARS:
                sections.append((heading, "\n\n".join(current)))
                current = []
                current_size = 0
            if len(paragraph) > MAX_CHUNK_CHARS:
                sentences = re.split(r"(?<=[.!?])\s+", paragraph)
                for sentence in sentences:
                    for fragment in _bounded_fragments(sentence):
                        if current and current_size + len(fragment) + 1 > MAX_CHUNK_CHARS:
                            sections.append((heading, " ".join(current)))
                            current = []
                            current_size = 0
                        current.append(fragment)
                        current_size += len(fragment) + 1
            else:
                current.append(paragraph)
                current_size += len(paragraph) + 2
        if current:
            sections.append((heading, "\n\n".join(current)))
    return sections


class MicrosoftLearnCorpusStore:
    """Persistent, scoped corpus built from official MCP search/fetch results."""

    def __init__(self, path: Path, refresh_hours: int = 24) -> None:
        self.path = path
        self.refresh_after = timedelta(hours=max(refresh_hours, 1))

    def _load(self) -> dict:
        if not self.path.exists():
            return {"schema_version": 2, "blueprints": {}, "scopes": {}, "chunks": []}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"schema_version": 2, "blueprints": {}, "scopes": {}, "chunks": []}
        if not isinstance(payload, dict):
            return {"schema_version": 2, "blueprints": {}, "scopes": {}, "chunks": []}
        payload["schema_version"] = 2
        payload.setdefault("blueprints", {})
        payload.setdefault("scopes", {})
        payload.setdefault("chunks", [])
        return payload

    @staticmethod
    def _scope(
        certification_code: str,
        domain: str | None,
        learning_objective: str | None = None,
    ) -> str:
        return f"{certification_code}|{domain or '*'}|{learning_objective or '*'}"

    def needs_refresh(
        self,
        certification_code: str,
        domain: str | None,
        learning_objective: str | None = None,
    ) -> bool:
        payload = self._load()
        value = payload["scopes"].get(
            self._scope(certification_code, domain, learning_objective)
        )
        if not isinstance(value, str):
            return True
        try:
            refreshed = datetime.fromisoformat(value)
        except ValueError:
            return True
        if refreshed.tzinfo is None:
            refreshed = refreshed.replace(tzinfo=timezone.utc)
        return _now_utc() - refreshed.astimezone(timezone.utc) >= self.refresh_after

    def blueprint_needs_refresh(self, certification_code: str) -> bool:
        blueprint = self._load()["blueprints"].get(certification_code)
        value = blueprint.get("refreshed_at") if isinstance(blueprint, dict) else None
        if not isinstance(value, str):
            return True
        try:
            refreshed = datetime.fromisoformat(value)
        except ValueError:
            return True
        if refreshed.tzinfo is None:
            refreshed = refreshed.replace(tzinfo=timezone.utc)
        return _now_utc() - refreshed.astimezone(timezone.utc) >= self.refresh_after

    def update_blueprint(
        self,
        *,
        certification_code: str,
        certification_title: str,
        study_guide_url: str,
        markdown: str,
    ) -> int:
        if not study_guide_url.startswith(
            "https://learn.microsoft.com/credentials/certifications/resources/study-guides/"
        ):
            raise ValueError("Certification blueprint must be an official Learn study guide.")
        objectives = parse_study_guide(markdown)
        if not objectives:
            raise ValueError("The official study guide contained no measured objectives.")
        payload = self._load()
        payload["blueprints"][certification_code] = {
            "certification_title": certification_title,
            "study_guide_url": study_guide_url,
            "refreshed_at": _now_utc().isoformat(),
            "objectives": objectives,
        }
        self._write(payload)
        return len(objectives)

    def blueprint_entries(
        self,
        certification_code: str,
        domain: str | None = None,
    ) -> list[dict[str, str]]:
        blueprint = self._load()["blueprints"].get(certification_code)
        if not isinstance(blueprint, dict):
            return []
        entries = blueprint.get("objectives")
        if not isinstance(entries, list):
            return []
        return [
            dict(item)
            for item in entries
            if isinstance(item, dict)
            and item.get("domain")
            and item.get("objective")
            and (not domain or _normalized(str(item["domain"])) == _normalized(domain))
        ]

    def blueprint_objectives(
        self,
        certification_code: str,
        domain: str | None = None,
    ) -> list[str]:
        return [
            item["objective"]
            for item in self.blueprint_entries(certification_code, domain)
        ]

    def blueprint_domains(self, certification_code: str) -> list[str]:
        return list(
            dict.fromkeys(
                item["domain"] for item in self.blueprint_entries(certification_code)
            )
        )

    def match_blueprint_objective(
        self,
        certification_code: str,
        domain: str | None,
        value: str,
    ) -> dict[str, str] | None:
        normalized_value = _normalized(value)
        entries = self.blueprint_entries(certification_code, domain)
        exact = next(
            (
                item
                for item in entries
                if _normalized(item["objective"]) == normalized_value
            ),
            None,
        )
        if exact:
            return exact
        value_tokens = set(_tokens(value)) - _BLUEPRINT_NOISE
        ranked = []
        for item in entries:
            objective_tokens = set(_tokens(item["objective"])) - _BLUEPRINT_NOISE
            overlap = len(value_tokens & objective_tokens)
            if overlap:
                ranked.append((overlap / max(len(objective_tokens), 1), item))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        return ranked[0][1] if ranked and ranked[0][0] >= 0.34 else None

    def ingest(
        self,
        *,
        certification_code: str,
        certification_title: str,
        domain: str | None,
        learning_objective: str,
        rows: list[dict],
        replace_scope: bool = True,
    ) -> int:
        blueprint = self._load()["blueprints"].get(certification_code)
        matched = self.match_blueprint_objective(
            certification_code,
            domain,
            learning_objective,
        )
        if not isinstance(blueprint, dict) or matched is None:
            return 0
        blueprint_url = str(blueprint.get("study_guide_url") or "")
        scope = self._scope(certification_code, matched["domain"], matched["objective"])
        new_chunks: list[dict] = []
        for row in rows:
            url = str(row.get("url") or "").strip()
            content = str(
                row.get("fetched_content")
                or row.get("content")
                or row.get("snippet")
                or row.get("text")
                or ""
            ).strip()
            relevance = _blueprint_relevance(matched["objective"], row)
            if (
                not url.startswith("https://learn.microsoft.com/")
                or url == blueprint_url
                or not content
                or relevance <= 0
            ):
                continue
            topic = str(row.get("title") or domain or certification_title).strip()
            url_fields = _url_metadata(url)
            sid = _source_id(url)
            for heading, section in _semantic_sections(content, topic):
                metadata = {
                    "corpus_scope": scope,
                    "certification": certification_code,
                    "certification_title": certification_title,
                    "learning_path": row.get("learning_path") or url_fields["learning_path"],
                    "module": row.get("module") or url_fields["module"],
                    "unit": row.get("unit") or url_fields["unit"],
                    "topic": heading or topic,
                    "learning_objective": matched["objective"],
                    "domain": matched["domain"],
                    "exam_domain": matched["domain"],
                    "skill_group": matched["skill"],
                    "skill_objective": matched["objective"],
                    "blueprint_aligned": True,
                    "blueprint_source_url": blueprint_url,
                    "blueprint_match_score": round(relevance, 5),
                    "source_url": url,
                    "source_id": sid,
                    "knowledge_provider": "microsoft_learn_mcp",
                }
                chunk = {
                    "chunk_id": _chunk_id(scope, url, heading, section),
                    "source": url,
                    "text": section,
                    "metadata": metadata,
                }
                metadata["questionability_score"] = questionability_score(chunk)
                new_chunks.append(chunk)

        if not new_chunks:
            return 0

        payload = self._load()
        retained = (
            [
                chunk
                for chunk in payload["chunks"]
                if (chunk.get("metadata") or {}).get("corpus_scope") != scope
            ]
            if replace_scope
            else list(payload["chunks"])
        )
        deduped = {chunk["chunk_id"]: chunk for chunk in retained}
        new_ids = {chunk["chunk_id"] for chunk in new_chunks}
        deduped.update({chunk["chunk_id"]: chunk for chunk in new_chunks})
        payload["chunks"] = list(deduped.values())
        payload["scopes"][scope] = _now_utc().isoformat()
        self._write(payload)
        return len(new_ids)

    def _write(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def search(
        self,
        query: str,
        *,
        certification_code: str,
        domain: str | None,
        top_k: int,
        learning_objective: str | None = None,
    ) -> list[dict]:
        query_tokens = _tokens(query)
        scored: list[tuple[float, dict]] = []
        for chunk in self._load()["chunks"]:
            metadata = chunk.get("metadata") or {}
            if metadata.get("certification") != certification_code:
                continue
            if domain and metadata.get("domain") != domain:
                continue
            if metadata.get("blueprint_aligned") is not True:
                continue
            if (
                learning_objective
                and _normalized(str(metadata.get("skill_objective") or ""))
                != _normalized(learning_objective)
            ):
                continue
            searchable = " ".join(
                str(value or "")
                for value in (
                    metadata.get("learning_objective"),
                    metadata.get("topic"),
                    metadata.get("module"),
                    metadata.get("unit"),
                    chunk.get("text"),
                )
            )
            candidate_tokens = _tokens(searchable)
            overlap = sum(
                min(count, candidate_tokens.get(token, 0))
                for token, count in query_tokens.items()
            )
            score = overlap / max(sum(query_tokens.values()), 1)
            scored.append((score, chunk))
        scored.sort(key=lambda item: (item[0], item[1]["chunk_id"]), reverse=True)
        return [
            {**chunk, "score": round(score, 5)}
            for score, chunk in scored[: max(1, min(top_k, 3))]
            if score > 0 or len(scored) <= top_k
        ]

    def questionability_index(
        self,
        certification_code: str,
        domain: str | None = None,
        learning_objective: str | None = None,
    ) -> list[dict]:
        """Return the derived quality index for canonical chunks in one scope."""
        normalized_domain = _normalized(domain or "")
        normalized_objective = _normalized(learning_objective or "")
        indexed = []
        for chunk in self._load()["chunks"]:
            metadata = chunk.get("metadata") or {}
            if metadata.get("certification") != certification_code:
                continue
            if normalized_domain and _normalized(str(metadata.get("domain") or "")) != normalized_domain:
                continue
            if normalized_objective and _normalized(
                str(metadata.get("skill_objective") or "")
            ) != normalized_objective:
                continue
            score = questionability_score(chunk)
            indexed.append(
                {
                    "chunk_id": chunk.get("chunk_id"),
                    "score": score,
                    "eligible": score >= MIN_QUESTIONABLE_SCORE,
                    "source": chunk.get("source"),
                    "domain": metadata.get("domain"),
                    "learning_objective": metadata.get("skill_objective"),
                    "module": metadata.get("module"),
                    "unit": metadata.get("unit"),
                }
            )
        return sorted(indexed, key=lambda item: (-item["score"], str(item["chunk_id"])))

    def select_evidence_packet(
        self,
        query: str,
        *,
        certification_code: str,
        domain: str,
        learning_objective: str,
        top_k: int = 3,
        exclude_chunk_ids: set[str] | None = None,
    ) -> list[dict]:
        """Select an anchor plus related/contrasting raw chunks for one question."""
        candidates = self.scoped_chunks(
            certification_code,
            domain,
            learning_objective,
        )
        if not candidates:
            return []
        query_tokens = _tokens(query)
        excluded = exclude_chunk_ids or set()
        ranked: list[tuple[float, dict]] = []
        for chunk in candidates:
            searchable = " ".join(
                str(value or "")
                for value in (
                    (chunk.get("metadata") or {}).get("topic"),
                    (chunk.get("metadata") or {}).get("module"),
                    (chunk.get("metadata") or {}).get("unit"),
                    chunk.get("text"),
                )
            )
            candidate_tokens = _tokens(searchable)
            overlap = sum(
                min(count, candidate_tokens.get(token, 0))
                for token, count in query_tokens.items()
            ) / max(sum(query_tokens.values()), 1)
            quality = questionability_score(chunk)
            freshness = 0.0 if str(chunk.get("chunk_id")) in excluded else 0.12
            ranked.append((0.58 * quality + 0.30 * overlap + freshness, chunk))
        ranked.sort(key=lambda item: (item[0], str(item[1].get("chunk_id"))), reverse=True)

        fresh = [item for item in ranked if str(item[1].get("chunk_id")) not in excluded]
        anchor_pool = (fresh or ranked)[: min(4, len(fresh or ranked))]
        weights = [max(score, 0.05) for score, _ in anchor_pool]
        anchor = random.choices(
            [chunk for _, chunk in anchor_pool],
            weights=weights,
            k=1,
        )[0]
        anchor_metadata = anchor.get("metadata") or {}
        companions = []
        for score, chunk in ranked:
            if chunk.get("chunk_id") == anchor.get("chunk_id"):
                continue
            metadata = chunk.get("metadata") or {}
            different_source = chunk.get("source") != anchor.get("source")
            same_module = bool(metadata.get("module")) and (
                metadata.get("module") == anchor_metadata.get("module")
            )
            role_bonus = 0.14 if different_source else (0.08 if same_module else 0.0)
            companions.append((score + role_bonus, different_source, chunk))
        companions.sort(
            key=lambda item: (item[0], item[1], str(item[2].get("chunk_id"))),
            reverse=True,
        )

        chosen = [anchor]
        for _, _, chunk in companions:
            if len(chosen) >= max(1, min(top_k, 3)):
                break
            normalized_text = _normalized(str(chunk.get("text") or ""))
            if any(
                normalized_text == _normalized(str(item.get("text") or ""))
                for item in chosen
            ):
                continue
            chosen.append(chunk)

        packet = []
        remaining = MAX_EVIDENCE_PACKET_CHARS
        for index, chunk in enumerate(chosen):
            if remaining <= 0:
                break
            text = _bounded_evidence_text(str(chunk.get("text") or ""), remaining)
            remaining -= len(text)
            metadata = dict(chunk.get("metadata") or {})
            quality = questionability_score(chunk)
            role = "anchor"
            if index > 0:
                role = (
                    "contrast"
                    if chunk.get("source") != anchor.get("source")
                    else "related"
                )
            metadata.update(
                questionability_score=quality,
                evidence_role=role,
                canonical_chunk=True,
                request_scoped_window=True,
            )
            packet.append(
                {
                    **chunk,
                    "text": text,
                    "metadata": metadata,
                    "score": quality,
                }
            )
        return packet

    def generation_status(self, certification_code: str) -> dict:
        payload = self._load()
        blueprint = payload["blueprints"].get(certification_code) or {}
        entries = [
            dict(item)
            for item in blueprint.get("objectives", [])
            if isinstance(item, dict) and item.get("domain") and item.get("objective")
        ]
        grouped: dict[tuple[str, str], list[dict]] = {}
        for chunk in payload["chunks"]:
            metadata = chunk.get("metadata") or {}
            if metadata.get("certification") != certification_code:
                continue
            key = (
                _normalized(str(metadata.get("domain") or "")),
                _normalized(str(metadata.get("skill_objective") or "")),
            )
            grouped.setdefault(key, []).append(chunk)
        objective_rows = []
        eligible_total = 0
        raw_total = 0
        for entry in entries:
            chunks = grouped.get(
                (
                    _normalized(entry["domain"]),
                    _normalized(entry["objective"]),
                ),
                [],
            )
            eligible = sum(
                questionability_score(chunk) >= MIN_QUESTIONABLE_SCORE
                for chunk in chunks
            )
            distinct_chunks = len({
                _normalized(str(chunk.get("text") or "")) for chunk in chunks
            })
            eligible_total += eligible
            raw_total += len(chunks)
            objective_rows.append(
                {
                    **entry,
                    "chunk_count": len(chunks),
                    "distinct_chunk_count": distinct_chunks,
                    "questionable_chunk_count": eligible,
                    "ready": eligible >= 1,
                    "case_study_ready": eligible >= 1 and distinct_chunks >= 2,
                }
            )
        ready_count = sum(item["ready"] for item in objective_rows)
        case_study_ready_count = sum(
            item["case_study_ready"] for item in objective_rows
        )
        return {
            "ready": bool(entries) and ready_count == len(entries),
            "objective_count": len(entries),
            "ready_objective_count": ready_count,
            "chunk_count": raw_total,
            "questionable_chunk_count": eligible_total,
            "case_study_ready_objective_count": case_study_ready_count,
            "objectives": objective_rows,
        }

    def scoped_chunks(
        self,
        certification_code: str,
        domain: str,
        learning_objective: str,
    ) -> list[dict]:
        """Return every raw official chunk for corpus preparation, never generation."""
        normalized_domain = _normalized(domain)
        normalized_objective = _normalized(learning_objective)
        return [
            dict(chunk)
            for chunk in self._load()["chunks"]
            if (chunk.get("metadata") or {}).get("certification")
            == certification_code
            and _normalized(str((chunk.get("metadata") or {}).get("domain") or ""))
            == normalized_domain
            and _normalized(
                str((chunk.get("metadata") or {}).get("skill_objective") or "")
            )
            == normalized_objective
            and (chunk.get("metadata") or {}).get("blueprint_aligned") is True
        ]

    def count(self) -> int:
        return len(self._load()["chunks"])

    def sources(self, certification_code: str) -> list[dict]:
        sources: dict[str, dict] = {}
        for chunk in self._load()["chunks"]:
            metadata = chunk.get("metadata") or {}
            if metadata.get("certification") != certification_code:
                continue
            if metadata.get("blueprint_aligned") is not True:
                continue
            sid = str(metadata.get("source_id") or chunk.get("source"))
            entry = sources.setdefault(
                sid,
                {
                    "id": sid,
                    "title": metadata.get("topic") or "Microsoft Learn",
                    "status": "indexed",
                    "expected_chunks": 0,
                    "indexed_chunks": 0,
                    "chapter_count": 0,
                    "domains": set(),
                    "source_url": metadata.get("source_url"),
                },
            )
            entry["expected_chunks"] += 1
            entry["indexed_chunks"] += 1
            if metadata.get("domain"):
                entry["domains"].add(metadata["domain"])
        result = []
        for entry in sources.values():
            entry["domains"] = sorted(entry["domains"])
            result.append(entry)
        return sorted(result, key=lambda item: str(item["title"]).casefold())
