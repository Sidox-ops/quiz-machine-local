# Compatibility and known limitations

Quiz Machine Local is a public alpha. Compatibility means that the application
can communicate with a component and validate its basic contract; it is not a
promise that every model or machine will deliver the same speed or question
quality.

## Desktop platforms

| Platform | Current level | Verification |
| --- | --- | --- |
| macOS Apple Silicon | Primary development platform | Unit, widget, golden and release build checks |
| macOS Intel | Expected to build | GitHub-hosted build coverage; clean-machine testing still required |
| Windows x64 | Alpha | GitHub-hosted build coverage; signed clean-machine testing still required |
| Linux | Contributor/development use | Backend and Flutter tests only; no supported package yet |

The application UI is currently English-only. Keyboard, screen-reader, contrast,
and scaling coverage is improving, but a complete accessibility audit has not
yet been performed.

## Ollama models

Quiz Machine accepts locally installed Ollama models that advertise text
completion, are not cloud-backed or embedding-only, and expose a context window
of at least 8,192 tokens when that metadata is available.

The initial recommendation considers model parameter count, quantization, file
size, and a conservative memory estimate. It avoids models estimated to consume
more than 70% of physical memory when a better-fitting candidate exists. This is
an estimate: GPU offload, unified memory, context allocation, and other running
applications can change real usage.

Selecting a model runs a short local JSON-schema probe before the choice is
saved. The probe catches unavailable models and basic structured-output failures,
but it does not benchmark full question generation or certify educational
quality. If generation is too slow or repeatedly rejected, select a smaller or
better-instructed model from the workspace.

Quiz Machine never downloads, updates, or deletes an Ollama model. Model
licences remain the user's responsibility and are displayed when Ollama exposes
them.

## Microsoft Learn MCP

The default knowledge provider depends on the public Microsoft Learn MCP
endpoint and its advertised tools. A scheduled smoke test checks protocol
negotiation and an official search result. Temporary upstream outages remain
possible; an already complete scoped cache can be reused where the application
can do so without widening certification scope.

## Release limitations

- There is no automatic updater yet.
- Public binaries must be signed; macOS packages must also be notarized.
- A published checksum proves file integrity after publication but is not a
  substitute for platform signature verification.
- Crash reports are not uploaded. This protects privacy but means users must
  provide reproducible steps and sanitized diagnostics when requesting help.
