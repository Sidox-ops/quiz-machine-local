# Repository instructions

Quiz Machine Local is the desktop Flutter/FastAPI/Ollama application in this
repository. It is independent from any hosted SaaS product.

## Before changing code

1. Check whether `graphify-out/graph.json` exists. If it does, use it as the
   navigation index and verify relevant nodes against the source.
2. Read `README.md` and the neighbouring document for the feature being changed.
3. Inspect the lockfiles before choosing a package manager.
4. Preserve ignored user data under `storage/`, `data/local/`, and
   `data/private/`.

## Architecture boundaries

- `backend/` owns local retrieval, generation, validation, persistence, and the
  loopback HTTP API.
- `flutter_app/` renders state and calls the local API. It must not contain
  model-provider secrets or decide answer correctness.
- Ollama calls remain behind `backend/ollama_client.py`.
- Microsoft Learn MCP calls remain behind `backend/microsoft_learn_mcp.py`.
- Question identity uses stable option IDs. A-D labels are presentation only.
- A review session must be completely prepared before it starts; answering a
  question must not trigger generation.
- Imported content and runtime state remain local by default.

## Toolchain

Prefer the existing local toolchain and never install packages globally.

- Python: use `.venv/bin/python` and `.venv/bin/pip` when present.
- Flutter/Dart: use the existing SDK and `pubspec.lock`.
- Python dependencies: use `requirements.lock`.

Do not run dependency-changing commands as a first reflex. Do not edit generated
platform folders, `.dart_tool`, build output, virtual environments, or runtime
JSON files.

## Verification

For backend changes:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q backend tests build_index.py quiz.py
```

For Flutter changes:

```bash
cd flutter_app
flutter analyze
flutter test
```

For shell changes:

```bash
bash -n setup.sh start.sh run_backend.sh scripts/*.sh
```

Run `git diff --check` and `git status --short` before stopping. Do not commit
private corpora, generated questions, progress, logs, credentials, signing
material, build artifacts, or `graphify-out/`.

## Content and security

- Never add copied exam questions, dumps, paid course material, or content with
  unclear redistribution rights.
- Treat imported documents and model output as untrusted data.
- Keep the backend bound to loopback and preserve the random token used by
  packaged builds.
- Do not add telemetry or a remote publisher-operated API without an explicit
  product decision and updated privacy documentation.
- Keep the application licence, embedded legal notice, privacy notice, and
  third-party notices consistent in the same change.
