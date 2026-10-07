# Open-source extraction audit

Date: 2026-10-07.

## Method

The public repository was created as a new Git repository from an explicit list
of tracked files. The source repository's `.git` directory was not copied, so
deleted files, old branches, commit messages, and historical blobs are absent.

The export included the local Flutter/FastAPI/Ollama runtime, tests, packaging,
local documentation, and the separately licensed demonstration corpus. It
excluded the hosted SaaS, production workflows, deployment and operations
documentation, Stripe/Foundry configuration, Firebase download site, private
corpora, generated state, caches, builds, and release artifacts.

## Secret and data controls

- the export was limited to tracked files;
- common Stripe, AWS, GitHub, Slack, and private-key signatures were scanned;
- `.env*`, signing material, runtime JSON/logs, private corpus directories,
  builds, releases, and Graphify output are ignored;
- no secret signature was found in the exported snapshot;
- no source repository Git history was imported.

This scan reduces risk but is not a guarantee that prose contains no personal or
commercially sensitive information. Contributors must continue to review every
new file before publication.

## Licensing review

- application code: `AGPL-3.0-only`;
- demonstration corpus: CC0 1.0 dedication in `data/reference/LICENSE`;
- Doto font: SIL Open Font License 1.1 beside the font file;
- package and model licences remain independent and are described in
  `THIRD_PARTY_NOTICES.md`.

The prior proprietary application licence and its embedded acceptance text were
replaced. The onboarding now presents an open-source licence notice and privacy
acknowledgement rather than a restriction on modification or redistribution.

## History policy

The clean initial commit is intentional. Future changes occur normally in this
repository. If provenance from the earlier private development period is needed,
record it in release notes without importing private commits or blobs.
