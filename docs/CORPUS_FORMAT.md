# Structured Markdown corpus format

The local desktop application imports UTF-8 Markdown files up to 5 MB. The
format is intentionally strict: every document is bound to one enabled
certification and one configured exam domain before it can enter the local
semantic index.

## Required template

```markdown
---
schema: quiz-machine-corpus/v1
document_id: quiz-machine-foundry-evaluation
certification_code: AI-103
domain: Plan and manage an Azure AI solution
title: Foundry evaluation notes
language: en
source_url: https://learn.microsoft.com/azure/ai-foundry/
learning_objective: Evaluate and select models for an AI solution
---

# Foundry evaluation notes

## Evaluation criteria

Use representative test data to compare quality, safety, latency and cost.

## Operational checks

Record model versions and evaluation settings so results remain reproducible.
```

Required frontmatter fields:

- `schema`: exactly `quiz-machine-corpus/v1`;
- `document_id`: 3 to 80 lowercase letters, digits, dots, underscores or
  hyphens; it is also the stable local filename and must be unique;
- `certification_code`: `AI-901`, `AI-103`, `AI-200`, `AI-300` or `AI-500`;
- `domain`: exactly one domain configured for that certification;
- `title`: must exactly match the single level-1 heading in the body;
- `language`: a short human-readable language code or name.

Optional fields:

- `source_url`: a complete HTTPS URL;
- `learning_objective`: the objective used to label local evidence.

The body must contain exactly one `#` title and at least one non-empty `##`
section. Each `##` section becomes one or more bounded semantic chunks. Nested
headings may be used inside a section. Unknown frontmatter fields, nested YAML,
duplicate fields and unsupported domains are rejected instead of being silently
ignored.

## Import experience

Open **Import corpus**, drop one or more `.md` files from Finder or use the file
picker, then confirm the content rights. The app validates every file before
enabling import. Errors identify the file, line when available, failed rule and
a suggested correction. Files with duplicate `document_id` values cannot be
imported together.

An accepted document is stored only in the local application-data directory.
The backend rebuilds the Ollama embedding index and rolls the file back if that
rebuild fails.

## Evidence selection

The Microsoft Learn cache is the canonical prepared corpus. Imported Markdown
does not silently replace official evidence. A local passage can contribute only
when its certification, domain, and learning objective match the requested
scope and its source metadata passes validation.

Each generated question receives a temporary packet of one to three chunks for
one measured objective, bounded to 5,200 characters. The packet is assembled
before the Ollama call and is not stored as a second authoritative corpus.
Microsoft Learn Search/Fetch is used during corpus preparation, never while the
learner is answering a prepared question.

## Legacy JSON compatibility

The backend still accepts the earlier JSON `chunks` and `chapters` contracts for
existing local data and scripts. The desktop import dialog now deliberately
exposes only the stricter Markdown v1 format so new documents always carry a
certification and valid domain. Existing JSON files under ignored local data
directories remain indexable.

Only import material you created or are permitted to use. Anonymizing or
combining third-party content does not by itself create redistribution rights.
