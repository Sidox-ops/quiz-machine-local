# Build and distribute Quiz Machine Local

This document covers the maintainer workflow. End users install Ollama and
follow the application onboarding.

## Release prerequisites

- build macOS releases on macOS and Windows releases on Windows;
- Python 3.10 or newer with runtime and build requirements installed;
- Flutter desktop toolchain;
- a trusted signing identity for the target platform;
- a public release location that provides the binary, checksum, notices, and
  corresponding source for the exact version.

Install build-only dependencies inside the project virtual environment:

```bash
.venv/bin/python -m pip install -r requirements-build.txt
```

## macOS

Store the signing identity and notarization credentials in the macOS keychain,
never in the repository.

```bash
MACOS_SIGN_IDENTITY="Developer ID Application: YOUR NAME (TEAMID)" \
NOTARY_PROFILE="quiz-machine-notary" \
VERSION="0.1.0" \
./scripts/package_macos.sh
```

The script builds the Python backend, Flutter `.app`, signed `.dmg`, third-party
licence report, and SHA-256 file under `release/`.

## Windows

Run in PowerShell on Windows after installing the prerequisites:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
$env:VERSION = "0.1.0"
.\scripts\package_windows.ps1
```

The initial format is a ZIP containing the desktop executable and runtime
files. Sign the executable and archive with the chosen Windows code-signing
workflow before publication.

## AGPL source availability

Every distributed binary must be accompanied by the complete corresponding
source under the `AGPL-3.0-only` terms. For a tagged GitHub release, publish the
binary beside the immutable tag and its automatically generated source archive,
and ensure the release notes clearly link that exact tag.

Do not point users only to a moving default branch. Retain the tagged source for
as long as the corresponding binary remains available. Include `LICENSE`,
`PRIVACY.md`, `THIRD_PARTY_NOTICES.md`, the Doto OFL text, and the generated
package-licence report with each bundle.

## Release checklist

- run the Python and Flutter test suites and shell syntax checks;
- verify the open-source licence and privacy notice on a clean user account;
- confirm that the release contains no `.env`, signing credential, runtime JSON,
  private corpus, question bank, progress, log, build cache, or Graphify output;
- verify Ollama installation, model selection, Microsoft Learn preparation, and
  Markdown import in an isolated test profile;
- sign and scan the exact release artifacts;
- compare published SHA-256 hashes after downloading them;
- verify the immutable source tag is available beside the binary;
- publish release notes and retain the previous stable binary temporarily.
