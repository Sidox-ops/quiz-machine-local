# Contributing

Thank you for improving Quiz Machine Local.

## Before opening a change

- Search existing issues and keep the proposal focused.
- For substantial product or architecture changes, open an issue before writing
  a large patch.
- Do not submit copied certification questions, exam dumps, paid training
  material, private corpora, model files, generated runtime state, or secrets.
- Confirm that every asset and dataset you add permits redistribution under the
  terms stated in the repository.

## Development

Use the pinned Python and Flutter dependency files. Prefer a project virtual
environment and do not install Python packages globally.

```bash
./scripts/doctor.sh
./setup.sh

.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q backend tests build_index.py quiz.py
bash -n setup.sh start.sh run_backend.sh scripts/*.sh

cd flutter_app
flutter analyze
flutter test
```

Tests must not require a live Ollama model or write into a user's application
data. Use fakes and temporary directories for external or persistent behavior.

## Pull requests

- Make one reviewable change at a time.
- Explain the user-visible behavior and the trust or data boundary affected.
- Add tests for business rules, persistence behavior, and failure paths.
- Update nearby documentation when behavior changes.
- Run `git diff --check` and list the verification commands in the pull request.

The `main` branch is protected. All changes must arrive through a pull request,
pass the required CI and security checks, resolve review conversations, and be
approved by the repository owner. `CODEOWNERS` makes that ownership explicit;
opening a pull request never grants approval or merge access to a contributor.

By submitting a contribution, you agree that it is licensed under the
repository's `AGPL-3.0-only` licence and that you have the right to provide it.
