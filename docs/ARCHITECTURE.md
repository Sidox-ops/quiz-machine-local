# Local application architecture

Quiz Machine Local is a desktop application composed of a Flutter process, a
loopback-only FastAPI process, local JSON persistence, and Ollama.

```text
Flutter desktop
    │ HTTP on 127.0.0.1 + random token in packaged builds
    ▼
FastAPI backend
    ├── certification catalogue and setup
    ├── Microsoft Learn corpus preparation
    ├── evidence selection and question pipeline
    ├── validated question bank
    └── learning progress
        │
        ├── public Microsoft Learn MCP (preparation only)
        ├── local Ollama API (generation and embeddings)
        └── local application-data JSON files
```

## Runtime boundary

`flutter_app/lib/core/runtime/local_backend_manager.dart` starts the bundled
backend on a random loopback port and gives it a random bearer token. During
development, Flutter connects to the explicitly started backend at
`127.0.0.1:8000`. The backend must not bind a packaged runtime to a public
interface.

Flutter renders state and user intent. It does not calculate correctness,
select evidence, call Ollama, or read local stores directly. The backend owns
those decisions and returns public question DTOs without a correct answer until
the answer endpoint is called.

## Local model selection and onboarding

Ollama remains the single model-provider boundary in
`backend/ollama_client.py`; no model family is hard-coded into the generation
pipeline. During onboarding, the backend reads `/api/tags` and `/api/show`,
filters out embedding-only, cloud-backed, non-completion, and undersized-context
models, then exposes the compatible installed inventory to Flutter. The
recommendation is deliberately transparent: it is the largest compatible model
reported by the local Ollama metadata, not a remote benchmark or an automatic
installation decision.

The user confirms the model before Microsoft Learn preparation is tested. The
choice is stored atomically in the local application-data settings file and can
be changed later for future generations. `QUIZ_MACHINE_LLM_MODEL` overrides
and locks that setting for managed launches. Active generation jobs reject
model changes; already prepared sessions and validated question-bank entries
are not rewritten.

Neither onboarding nor `start.sh` pulls generation or embedding models. Missing
requirements produce an actionable status and remain under the user's control.
Direct llama.cpp and other providers are outside the current boundary; they can
be added later behind a provider interface without moving selection logic into
Flutter.

## Corpus and evidence

`backend/microsoft_learn_corpus.py` prepares and persists the canonical
certification corpus. Search and fetch happen during preparation. A question
later receives one objective and a temporary packet of one to three scored
chunks. `backend/rag.py` also supports the legacy local embedding index.

User imports are untrusted and certification-scoped. Their parser and atomic
write behavior live in `backend/corpus.py`. Runtime data is written only to the
configured application-data and storage directories.

## Question pipeline

`backend/quiz_engine.py` orchestrates:

1. objective and evidence selection;
2. structured candidate generation;
3. factual audit of every option against the evidence;
4. canonical question freeze and fingerprint;
5. explanation generation tied to stable option IDs;
6. deterministic final validation;
7. persistence in the validated question bank.

`backend/question_store.py` owns the versioned bank. A batch reuses compatible
validated questions first and generates only its missing positions. The entire
batch, including corrections, is ready before the learner begins revision.

## Learning state

`backend/progress.py` stores progress per certification and tracks totals,
recent accuracy, response time, objective mastery, streaks, and confusions. The
API exposes scoped reset operations that never delete corpora or the question
bank.

## Trust rules

- Model JSON, MCP responses, and imported documents are untrusted input.
- Stable option IDs, not letters or visible positions, determine correctness.
- The canonical fingerprint prevents an explanation for one question from being
  attached to another.
- Retrieval never falls through to another certification when evidence is
  missing.
- Reasoning traces are not persisted.
- No learner action sends content to a publisher-operated service.
