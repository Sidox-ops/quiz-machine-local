from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .certifications import certification
from .config import DATA_DIR, REFERENCE_DATA_DIR, USER_DATA_DIR


MAX_CHARS = 1400
OVERLAP_CHARS = 180
MARKDOWN_SCHEMA = "quiz-machine-corpus/v1"
MARKDOWN_MAX_BYTES = 5 * 1024 * 1024
_MARKDOWN_REQUIRED_FIELDS = (
    "schema",
    "document_id",
    "certification_code",
    "domain",
    "title",
    "language",
)
_MARKDOWN_ALLOWED_FIELDS = {
    *_MARKDOWN_REQUIRED_FIELDS,
    "source_url",
    "learning_objective",
}


@dataclass(frozen=True, slots=True)
class MarkdownCorpusIssue:
    code: str
    message: str
    field: str | None = None
    line: int | None = None
    hint: str | None = None

    def public_dict(self) -> dict:
        return {
            key: value
            for key, value in {
                "code": self.code,
                "message": self.message,
                "field": self.field,
                "line": self.line,
                "hint": self.hint,
            }.items()
            if value is not None
        }


class MarkdownCorpusValidationError(ValueError):
    def __init__(self, issues: list[MarkdownCorpusIssue]):
        self.issues = issues
        super().__init__(issues[0].message if issues else "Invalid Markdown corpus.")

    def public_detail(self) -> dict:
        return {
            "message": "This Markdown file does not match the required corpus format.",
            "issues": [issue.public_dict() for issue in self.issues],
        }


def _stable_id(source: str, text: str, suffix: str = "") -> str:
    digest = hashlib.sha1(f"{source}|{suffix}|{text}".encode("utf-8")).hexdigest()[:12]
    return f"chunk_{digest}"


def _window_text(text: str, source: str, metadata: dict) -> list[dict]:
    # Free-form .md and .txt files are converted into overlapping windows so
    # long notes remain searchable without exceeding the embedding model window.
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not text:
        return []
    if len(text) <= MAX_CHARS:
        return [{
            "chunk_id": _stable_id(source, text),
            "source": source,
            "text": text,
            "metadata": metadata,
        }]

    chunks = []
    start = 0
    i = 0
    while start < len(text):
        end = min(len(text), start + MAX_CHARS)
        if end < len(text):
            boundary = max(text.rfind("\n", start, end), text.rfind(". ", start, end))
            if boundary > start + MAX_CHARS // 2:
                end = boundary + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append({
                "chunk_id": _stable_id(source, piece, str(i)),
                "source": source,
                "text": piece,
                "metadata": metadata,
            })
        if end >= len(text):
            break
        start = max(end - OVERLAP_CHARS, start + 1)
        i += 1
    return chunks


def _parse_ai103_json(path: Path, payload: dict) -> list[dict]:
    # Structured corpora with a top-level `chapters` array preserve exam domain,
    # topic and timestamp metadata for domain/chapter practice in the UI.
    raw_metadata = payload.get("metadata")
    corpus_metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
    source_title = (
        payload.get("title")
        or corpus_metadata.get("title")
        or path.stem
    )
    chapters = payload.get("chapters", [])
    chunks = []
    for chapter_index, chapter in enumerate(chapters):
        focus = chapter.get("study_focus", [])
        if isinstance(focus, str):
            focus = [focus]
        topic = chapter.get("topic", "Unknown topic")
        domain = chapter.get("exam_domain", "Unknown domain")
        tags = chapter.get("retrieval_tags", [])
        text = "\n".join([
            f"Topic: {topic}",
            f"AI-103 exam domain: {domain}",
            f"Exam weight: {chapter.get('exam_weight') or 'not specified'}",
            f"Priority: {chapter.get('priority', 'not specified')}",
            "Study focus:",
            *[f"- {item}" for item in focus],
            f"Tags: {', '.join(tags)}" if tags else "",
        ]).strip()
        metadata = {
            "topic": topic,
            "domain": domain,
            "priority": chapter.get("priority"),
            "timestamp_start": chapter.get("start"),
            "timestamp_end": chapter.get("end"),
            "source_url": corpus_metadata.get("source_url"),
            "source_title": source_title,
            "source_type": corpus_metadata.get("source_type"),
            "navigation_kind": "chapter",
            "chapter_index": chapter_index,
        }
        chunk_id = chapter.get("id") or _stable_id(path.name, text)
        chunks.append({
            "chunk_id": chunk_id,
            "source": path.name,
            "text": text,
            "metadata": metadata,
        })
    return chunks


def _parse_json(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    # User-provided question examples guide structure only. Their answer keys may
    # be missing, so indexing them as technical facts would poison grounding.
    if isinstance(payload, dict) and payload.get("purpose") == "question_patterns":
        return []
    if isinstance(payload, dict) and isinstance(payload.get("chapters"), list):
        return _parse_ai103_json(path, payload)
    if isinstance(payload, dict) and isinstance(payload.get("chunks"), list):
        validate_corpus_payload(payload)
        return _parse_generic_json(path, payload)
    # Generic JSON is still accepted, but it will not expose chapter navigation.
    pretty = json.dumps(payload, ensure_ascii=False, indent=2)
    return _window_text(pretty, path.name, {"topic": path.stem, "domain": "unknown"})


def _parse_generic_json(path: Path, payload: dict) -> list[dict]:
    raw_metadata = payload.get("metadata")
    corpus_metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
    source_title = (
        payload.get("title")
        or corpus_metadata.get("title")
        or path.stem
    )
    chunks = []
    for index, item in enumerate(payload["chunks"]):
        content = item["content"].strip()
        metadata = {
            "topic": item.get("topic") or payload.get("title") or path.stem,
            "domain": item.get("domain") or "unknown",
            "language": payload.get("language"),
            "source_title": source_title,
            "source_type": corpus_metadata.get("source_type"),
        }
        chunks.append({
            "chunk_id": item.get("id") or _stable_id(path.name, content, str(index)),
            "source": path.name,
            "text": content,
            "metadata": metadata,
        })
    return chunks


def validate_corpus_payload(payload: object) -> dict:
    """Validate the documented import format before it reaches local storage."""
    if not isinstance(payload, dict):
        raise ValueError("The JSON root must be an object.")

    raw_metadata = payload.get("metadata")
    if raw_metadata is not None and not isinstance(raw_metadata, dict):
        raise ValueError("The optional `metadata` field must be an object.")

    chunks = payload.get("chunks")
    chapters = payload.get("chapters")
    has_chunks = isinstance(chunks, list) and bool(chunks)
    has_chapters = isinstance(chapters, list) and bool(chapters)
    if has_chunks == has_chapters:
        raise ValueError(
            "Provide exactly one non-empty `chunks` or `chapters` array."
        )

    entries = chunks if has_chunks else chapters
    assert isinstance(entries, list)
    if len(entries) > 5000:
        raise ValueError("A corpus can contain at most 5,000 chunks.")

    seen_ids: set[str] = set()
    for index, item in enumerate(entries, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Entry {index} must be an object.")

        if has_chunks:
            content = item.get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError(f"Chunk {index} needs non-empty `content`.")
            if len(content) > 20_000:
                raise ValueError(f"Chunk {index} exceeds 20,000 characters.")
        else:
            topic = item.get("topic")
            domain = item.get("exam_domain")
            focus = item.get("study_focus")
            if not isinstance(topic, str) or not topic.strip():
                raise ValueError(f"Chapter {index} needs a non-empty `topic`.")
            if not isinstance(domain, str) or not domain.strip():
                raise ValueError(
                    f"Chapter {index} needs a non-empty `exam_domain`."
                )
            if isinstance(focus, str):
                focus_items = [focus]
            elif isinstance(focus, list):
                focus_items = focus
            else:
                focus_items = []
            if not focus_items or any(
                not isinstance(value, str) or not value.strip()
                for value in focus_items
            ):
                raise ValueError(
                    f"Chapter {index} needs non-empty `study_focus` text."
                )
            if sum(len(value) for value in focus_items) > 20_000:
                raise ValueError(f"Chapter {index} exceeds 20,000 characters.")

        chunk_id = item.get("id")
        if has_chapters and chunk_id is None:
            raise ValueError(f"Chapter {index} needs a stable `id`.")
        if chunk_id is not None:
            if not isinstance(chunk_id, str) or not chunk_id.strip():
                raise ValueError(f"Entry {index} has an invalid `id`.")
            if chunk_id in seen_ids:
                raise ValueError(f"Entry {index} repeats the id `{chunk_id}`.")
            seen_ids.add(chunk_id)

    corpus_metadata = raw_metadata or {}
    return {
        "title": str(
            payload.get("title")
            or corpus_metadata.get("title")
            or "Untitled corpus"
        ),
        "language": str(
            payload.get("language")
            or corpus_metadata.get("language")
            or "unspecified"
        ),
        "chunk_count": len(entries),
    }


def validate_markdown_corpus(content: str, filename: str = "corpus.md") -> dict:
    """Validate and summarize the strict Markdown import contract."""
    metadata, body, body_start_line = _parse_markdown_frontmatter(content)
    issues: list[MarkdownCorpusIssue] = []

    for field in _MARKDOWN_REQUIRED_FIELDS:
        if not metadata.get(field):
            issues.append(MarkdownCorpusIssue(
                code="missing_field",
                field=field,
                line=1,
                message=f"The `{field}` frontmatter field is required.",
                hint=f"Add `{field}: ...` between the opening `---` lines.",
            ))

    unknown_fields = sorted(set(metadata) - _MARKDOWN_ALLOWED_FIELDS)
    for field in unknown_fields:
        issues.append(MarkdownCorpusIssue(
            code="unknown_field",
            field=field,
            message=f"The `{field}` frontmatter field is not supported.",
            hint="Remove it or move this information into the Markdown body.",
        ))

    if metadata.get("schema") and metadata["schema"] != MARKDOWN_SCHEMA:
        issues.append(MarkdownCorpusIssue(
            code="invalid_schema",
            field="schema",
            message=f"The schema must be `{MARKDOWN_SCHEMA}`.",
            hint=f"Replace the value with `schema: {MARKDOWN_SCHEMA}`.",
        ))

    document_id = metadata.get("document_id", "")
    if document_id and not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,79}", document_id):
        issues.append(MarkdownCorpusIssue(
            code="invalid_document_id",
            field="document_id",
            message="The document id must contain 3 to 80 lowercase letters, numbers, dots, underscores or hyphens.",
            hint="Example: `ai103-foundry-evaluation`.",
        ))

    selected = None
    certification_code = metadata.get("certification_code", "").upper()
    if certification_code:
        try:
            selected = certification(certification_code)
        except ValueError:
            issues.append(MarkdownCorpusIssue(
                code="unsupported_certification",
                field="certification_code",
                message=f"`{certification_code}` is not enabled in this local application.",
                hint="Use one of AI-901, AI-103 or AI-200.",
            ))

    domain = metadata.get("domain", "")
    if selected is not None and domain:
        normalized_domain = _normalized(domain)
        matching_domain = next(
            (value for value in selected.domains if _normalized(value) == normalized_domain),
            None,
        )
        if matching_domain is None:
            issues.append(MarkdownCorpusIssue(
                code="invalid_domain",
                field="domain",
                message=f"`{domain}` is not a configured {selected.code} exam domain.",
                hint="Use exactly one of: " + "; ".join(selected.domains),
            ))
        else:
            metadata["domain"] = matching_domain

    source_url = metadata.get("source_url")
    if source_url:
        parsed_url = urlparse(source_url)
        if parsed_url.scheme != "https" or not parsed_url.netloc:
            issues.append(MarkdownCorpusIssue(
                code="invalid_source_url",
                field="source_url",
                message="The optional source URL must be a complete HTTPS URL.",
                hint="Example: `source_url: https://learn.microsoft.com/...`.",
            ))

    headings = [
        (line_number, match.group(1), match.group(2).strip())
        for line_number, line in enumerate(body.splitlines(), start=body_start_line)
        if (match := re.match(r"^(#{1,6})\s+(.+?)\s*$", line))
    ]
    h1_headings = [item for item in headings if len(item[1]) == 1]
    h2_headings = [item for item in headings if len(item[1]) == 2]
    if len(h1_headings) != 1:
        issues.append(MarkdownCorpusIssue(
            code="invalid_title_heading",
            message="The document body must contain exactly one level-1 heading (`#`).",
            line=body_start_line,
            hint="Start the body with `# <title>`.",
        ))
    elif metadata.get("title") and h1_headings[0][2] != metadata["title"]:
        issues.append(MarkdownCorpusIssue(
            code="title_mismatch",
            field="title",
            line=h1_headings[0][0],
            message="The level-1 heading must exactly match the frontmatter title.",
            hint=f"Use `# {metadata['title']}`.",
        ))
    if not h2_headings:
        issues.append(MarkdownCorpusIssue(
            code="missing_section",
            message="The document needs at least one level-2 section (`##`).",
            line=body_start_line,
            hint="Split the learning material into one or more `##` sections.",
        ))
    if not body.strip():
        issues.append(MarkdownCorpusIssue(
            code="empty_body",
            message="The Markdown body is empty.",
            line=body_start_line,
        ))

    sections = _markdown_sections(body)
    for section in sections:
        if not section["content"].strip():
            issues.append(MarkdownCorpusIssue(
                code="empty_section",
                line=body_start_line + section["line"] - 1,
                message=f"The section `{section['title']}` has no learning content.",
                hint="Add at least one explanatory paragraph below the heading.",
            ))

    size = len(content.encode("utf-8"))
    if size > MARKDOWN_MAX_BYTES:
        issues.append(MarkdownCorpusIssue(
            code="file_too_large",
            message="The corpus exceeds the 5 MB import limit.",
            hint="Split it into several structured Markdown files.",
        ))
    if not filename.lower().endswith(".md"):
        issues.append(MarkdownCorpusIssue(
            code="invalid_extension",
            message="Only `.md` files can be imported through the Markdown importer.",
            hint="Save the document as UTF-8 Markdown.",
        ))

    if issues:
        raise MarkdownCorpusValidationError(issues)

    return {
        "title": metadata["title"],
        "language": metadata["language"],
        "chunk_count": sum(
            max(1, len(_window_text(
                f"## {section['title']}\n\n{section['content']}",
                filename,
                {},
            )))
            for section in sections
        ),
        "document_id": document_id,
        "certification_code": certification_code,
        "domain": metadata["domain"],
        "source_url": source_url,
    }


def _parse_markdown_frontmatter(content: str) -> tuple[dict[str, str], str, int]:
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    issues: list[MarkdownCorpusIssue] = []
    if not lines or lines[0].strip() != "---":
        raise MarkdownCorpusValidationError([MarkdownCorpusIssue(
            code="missing_frontmatter",
            line=1,
            message="The file must start with a `---` frontmatter block.",
            hint=f"Copy the {MARKDOWN_SCHEMA} template and fill in its fields.",
        )])
    try:
        closing_index = next(
            index for index, line in enumerate(lines[1:], start=1)
            if line.strip() == "---"
        )
    except StopIteration as error:
        raise MarkdownCorpusValidationError([MarkdownCorpusIssue(
            code="unclosed_frontmatter",
            line=1,
            message="The frontmatter block is not closed.",
            hint="Add a second `---` line before the Markdown body.",
        )]) from error

    metadata: dict[str, str] = {}
    for line_number, raw_line in enumerate(lines[1:closing_index], start=2):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"([a-z_][a-z0-9_]*)\s*:\s*(.*?)\s*", raw_line)
        if not match:
            issues.append(MarkdownCorpusIssue(
                code="invalid_frontmatter_line",
                line=line_number,
                message="Frontmatter lines must use the flat `key: value` form.",
                hint="Lists and nested YAML are intentionally not supported.",
            ))
            continue
        key, value = match.groups()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1].strip()
        if key in metadata:
            issues.append(MarkdownCorpusIssue(
                code="duplicate_field",
                field=key,
                line=line_number,
                message=f"The `{key}` field is declared more than once.",
            ))
        else:
            metadata[key] = value
    if issues:
        raise MarkdownCorpusValidationError(issues)
    return metadata, "\n".join(lines[closing_index + 1:]).strip(), closing_index + 2


def _markdown_sections(body: str) -> list[dict]:
    lines = body.splitlines()
    starts = [
        index for index, line in enumerate(lines)
        if re.match(r"^##\s+", line)
    ]
    sections = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        title = re.sub(r"^##\s+", "", lines[start]).strip()
        section_lines = lines[start + 1:end]
        if position == 0:
            introduction = [
                line for line in lines[:start]
                if not re.match(r"^#\s+", line)
            ]
            section_lines = [*introduction, *section_lines]
        content = "\n".join(section_lines).strip()
        sections.append({"title": title, "content": content, "line": start + 1})
    return sections


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _parse_markdown_or_text(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix.lower() == ".md" and raw.lstrip().startswith("---"):
        summary = validate_markdown_corpus(raw, path.name)
        metadata, body, _ = _parse_markdown_frontmatter(raw)
        common_metadata = {
            "certification_code": summary["certification_code"],
            "domain": summary["domain"],
            "language": summary["language"],
            "source_title": summary["title"],
            "source_url": summary["source_url"],
            "source_type": "imported_markdown",
            "document_id": summary["document_id"],
            "learning_objective": metadata.get("learning_objective"),
        }
        chunks = []
        for section_index, section in enumerate(_markdown_sections(body)):
            section_text = f"## {section['title']}\n\n{section['content']}"
            chunks.extend(_window_text(
                section_text,
                path.name,
                {
                    **common_metadata,
                    "topic": section["title"],
                    "section": section_index,
                },
            ))
        return chunks
    # Split at markdown headings while preserving heading text.
    sections = re.split(r"(?=^#{1,4}\s+)", raw, flags=re.MULTILINE)
    chunks = []
    for idx, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue
        heading_match = re.match(r"^#{1,4}\s+(.+)$", section.splitlines()[0])
        topic = heading_match.group(1).strip() if heading_match else path.stem
        chunks.extend(_window_text(
            section,
            path.name,
            {
                "topic": topic,
                "domain": "unknown",
                "section": idx,
                "source_title": path.stem,
            },
        ))
    return chunks


def load_chunks(data_dir: Path | None = None) -> list[dict]:
    chunks: list[dict] = []
    path_roots = _source_paths(data_dir)
    for path in sorted(path_roots):
        if not path.is_file():
            continue
        if path.name.lower() == "readme.md":
            continue
        suffix = path.suffix.lower()
        if suffix == ".json":
            parsed = _parse_json(path)
        elif suffix in {".md", ".txt"}:
            parsed = _parse_markdown_or_text(path)
        else:
            continue

        source_id = _source_id(path, path_roots[path], data_dir is not None)
        for chunk in parsed:
            chunk["source"] = source_id
            chunk.setdefault("metadata", {})["source_id"] = source_id
        chunks.extend(parsed)
    return chunks


def excluded_corpus_sources(data_dir: Path | None = None) -> list[dict]:
    """Return recognized files intentionally excluded from factual grounding."""
    excluded = []
    for path, root in _source_paths(data_dir).items():
        if not path.is_file() or path.suffix.lower() != ".json":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, dict) or payload.get("purpose") != "question_patterns":
            continue
        excluded.append({
            "id": _source_id(path, root, data_dir is not None),
            "title": payload.get("title") or path.stem,
            "reason": "Question patterns guide output structure but are not factual grounding.",
        })
    return sorted(excluded, key=lambda item: item["id"].casefold())


def _source_paths(data_dir: Path | None) -> dict[Path, Path]:
    roots = [data_dir] if data_dir else _corpus_roots()
    return {
        path: root
        for root in roots
        if root.exists()
        for path in root.rglob("*")
    }


def _source_id(path: Path, root: Path, explicit_root: bool) -> str:
    relative = path.relative_to(root).as_posix()
    if explicit_root:
        return relative
    if root == DATA_DIR:
        return relative
    if root == REFERENCE_DATA_DIR:
        return f"reference/{relative}"
    if root == USER_DATA_DIR:
        return f"local/{relative}"
    return f"{root.name}/{relative}"


def _corpus_roots() -> list[Path]:
    # Packaged builds separate the bundled demo from imports in app data.
    if "AI103_USER_DATA_DIR" in os.environ:
        return [REFERENCE_DATA_DIR, USER_DATA_DIR]
    return [DATA_DIR]
