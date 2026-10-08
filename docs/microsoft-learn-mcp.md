# Microsoft Learn MCP

## Local retrieval flow

Quiz Machine Local uses the public Microsoft Learn MCP service by default to
prepare a certification corpus. It never treats a raw search result as a trusted
answer and never calls MCP while the learner is answering a prepared question.

For AI-901, AI-103, AI-200, AI-300, or AI-500, the preparation job:

1. fetches the official study guide and derives its measured domains and
   objectives;
2. discovers the runtime MCP tool schemas;
3. searches and fetches bounded Microsoft Learn pages for each objective;
4. converts accepted content into heading-bounded chunks;
5. persists the canonical cache in
   `storage/microsoft_learn_corpus.json`;
6. scores chunks for questionability and later builds a temporary evidence
   packet of one to three chunks for one objective.

The packet is limited to 5,200 characters and favors an anchor plus related or
contrasting evidence. The application does not create or read a second compact
corpus. Existing `storage/standardized_corpora/` files are historical runtime
artifacts and are ignored.

Question generation then runs locally through Ollama: candidate generation,
factual option audit, canonical fingerprint freeze, explanation, and final
deterministic checks. Reasoning traces are discarded. Stable option IDs are the
correctness keys; A-D labels come only from presentation order.

## Transport

The fixed endpoint is:

```text
https://learn.microsoft.com/api/mcp
```

No Microsoft token is required for this public service. The client negotiates
Streamable HTTP, accepts JSON or SSE responses, retains `Mcp-Session-Id`, sends
`notifications/initialized`, calls `tools/list`, and uses the discovered search
and fetch schemas instead of assuming a fixed tool payload.

If Fetch is unavailable or fails, an official search excerpt may be retained as
bounded evidence. Content is still associated with one certification, domain,
and measured objective before use.

## Trust and privacy boundary

MCP requests contain certification, domain, objective, and documentation search
terms. Imported corpora, quiz answers, scores, question-bank content, and
personal identifiers are not intentionally transmitted.

Search relevance is not proof of syllabus membership. The backend validates the
official study-guide structure, Microsoft host, certification scope, objective
mapping, chunk length, and source metadata. It rejects unsupported or ambiguous
content rather than widening the scope to another certification.

The cache and every derived question remain local. Only a small request-scoped
evidence packet is sent to the local Ollama endpoint.

## Offline mode and imports

Set the following value before launch to use the legacy indexed AI-103 corpus
without Microsoft Learn network access:

```dotenv
QUIZ_MACHINE_KNOWLEDGE_PROVIDER=local
```

The visual importer accepts one or more `quiz-machine-corpus/v1` Markdown files.
Imported material is stored locally and may contribute evidence only when it is
properly scoped. The user remains responsible for content rights.

## Failure behavior

Preparation retries transient network failures with bounded backoff and can be
cancelled. A previously complete canonical cache can be reused. When required
evidence for an objective is missing, generation fails closed instead of using
an unrelated certification or unsupported model knowledge.

## Verification

Unit tests cover session negotiation, JSON/SSE parsing, tool discovery, search
and fetch mappings, certification isolation, cache persistence, packet bounds,
and failure paths with fakes. The scheduled `mcp-smoke.yml` workflow performs a
bounded live negotiation and one official search twice per week. It does not
prepare or persist a certification corpus and sends no user data.

References:

- [Microsoft Learn MCP developer reference](https://learn.microsoft.com/training/support/mcp-developer-reference)
- [Microsoft Learn MCP FAQ](https://learn.microsoft.com/training/support/mcp-faq)
- [MCP Streamable HTTP transport](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports)
