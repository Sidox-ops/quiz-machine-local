# Flutter desktop UI

The recommended development command is run from the repository root:

```bash
./start.sh
```

It starts Ollama and the backend, enables official Microsoft Learn retrieval,
generates missing platform files, and launches the desktop app. Onboarding lists
compatible generation models already installed in Ollama, recommends the largest
one, and asks the user to choose before checking Microsoft Learn. It never
downloads a model. The quiz setup then lets you choose AI-901, AI-103, or AI-200
before generating local QCMs.

Use the **Local model** action in the top bar to switch models for future
generation. Prepared sessions and validated questions are preserved. A launch
configured with `AI103_LLM_MODEL` keeps the selection read-only.

Use the Insights action in the top bar to open the learning dashboard for the
active certification. It shows actionable domain/objective signals and offers
confirmed resets for recent history, the adaptive profile, one certification,
or all progress. These actions do not delete corpora or the question bank.

Set `AI103_KNOWLEDGE_PROVIDER=local` before launching to use the legacy indexed
AI-103 corpus without Microsoft Learn network access.

## Run the UI separately

Start the backend from the repository root:

```bash
./run_backend.sh
```

Then run Flutter in another terminal:

```bash
cd flutter_app
./bootstrap.sh
flutter pub get
flutter run -d macos
```

`bootstrap.sh` preserves the custom application files while generating local
platform runners. Generated runner folders are intentionally ignored by Git.

Development falls back to `http://127.0.0.1:8000`. Packaged builds start an
embedded backend on a random loopback port with a random session token. User
corpora and generated state are stored under Application Support on macOS or
AppData on Windows.

See [`../docs/DISTRIBUTION.md`](../docs/DISTRIBUTION.md) for release packaging.
