# Changelog

All notable user-facing changes are documented here. The project follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and uses semantic
versioning for public releases.

## [Unreleased]

### Added

- AI-300 and AI-500 certification paths backed by their Microsoft Learn study
  guides;
- local discovery and explicit selection of installed Ollama generation models;
- hardware-aware model recommendation and a structured-output compatibility
  probe before selection;
- Microsoft Learn MCP onboarding verification and a scheduled live contract
  smoke test;
- macOS and Windows build verification, platform-specific Flutter golden tests,
  dependency review, CodeQL, Dependabot, and a gated signed-release workflow
  with build-provenance attestations;
- public compatibility, support, roadmap, issue, and pull-request guidance.

### Changed

- historical certification-specific application configuration now uses the
  neutral `QUIZ_MACHINE_*` namespace;
- README product previews now use readable, deterministic Flutter captures;
- onboarding explicitly confirms that Quiz Machine never downloads or replaces
  models;
- release scripts now read the shared application version and refuse unsigned
  public packages.

[Unreleased]: https://github.com/Sidox-ops/quiz-machine-local/commits/main
