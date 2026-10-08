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
RELEASE_CHANNEL="public" \
./scripts/package_macos.sh
```

The script builds the Python backend, Flutter `.app`, signed `.dmg`, third-party
licence report, and SHA-256 file under `release/`.

## Windows

Run in PowerShell on Windows after installing the prerequisites:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
$env:RELEASE_CHANNEL = "public"
$env:WINDOWS_SIGN_CERTIFICATE_THUMBPRINT = "CERTIFICATE THUMBPRINT"
.\scripts\package_windows.ps1
```

The initial format is a ZIP containing the desktop executable and runtime
files. The script signs every executable before creating the archive. Public
mode fails closed if the certificate or `signtool.exe` is unavailable.

Both scripts read the release version from the root `VERSION` file. Run
`python scripts/check_version.py` before tagging. A pushed `v<version>` tag
starts `.github/workflows/release.yml`; it refuses a mismatched tag, requires
both signing identities, notarizes macOS, publishes checksums, and creates the
GitHub Release only after both platform jobs succeed. It also publishes signed
GitHub build-provenance attestations, which can be checked with
`gh attestation verify <artifact> --repo Sidox-ops/quiz-machine-local`.

The release workflow expects these GitHub Actions secrets:

- `MACOS_CERTIFICATE_P12_BASE64`, `MACOS_CERTIFICATE_PASSWORD`,
  `MACOS_SIGN_IDENTITY`, `APPLE_ID`, `APPLE_TEAM_ID`, and
  `APPLE_APP_PASSWORD`;
- `WINDOWS_CERTIFICATE_PFX_BASE64` and `WINDOWS_CERTIFICATE_PASSWORD`.

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
- confirm onboarding and `start.sh` never download a generation or embedding
  model, including when no compatible model is installed;
- sign and scan the exact release artifacts;
- compare published SHA-256 hashes after downloading them;
- verify the immutable source tag is available beside the binary;
- publish release notes and retain the previous stable binary temporarily.
