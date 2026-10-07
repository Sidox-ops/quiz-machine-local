# Privacy notice

Version 2.0 — 7 October 2026

Quiz Machine Local is designed to operate without an account or a
publisher-operated backend.

## Data stored locally

The application processes and stores imported corpora, Microsoft Learn cache
entries, generated questions, answers, scores, learning progress, settings,
indexes, and Ollama responses on the user's computer.

It includes no advertising, analytics, telemetry, or crash-reporting SDK. The
project maintainers do not receive the local quiz history or imported content.

## Network requests

The default configuration contacts the public Microsoft Learn MCP endpoint to
retrieve certification study-guide structure and relevant official learning
pages. Requests contain certification, domain, and objective search terms. The
application does not intentionally send imported corpora, answers, scores,
local question-bank content, or personal identifiers to Microsoft Learn.

Ollama is separate software. The supported configuration calls its local API at
`127.0.0.1`. If a user points Ollama to a remote endpoint, content sent to that
endpoint is governed by its operator and that user's configuration.

Package managers, Git hosting, release hosting, and model downloads used outside
the application may process ordinary technical logs under their own terms.

## Control and deletion

No Quiz Machine account exists. The dashboard provides scoped progress resets.
Uninstalling the application may leave its local application-data directory
behind. Delete the Quiz Machine directory from Application Support on macOS or
AppData on Windows to remove imported corpora, caches, generated questions,
indexes, settings, and progress.

## Contributions and issues

Information voluntarily posted to a public issue or pull request is processed by
the Git hosting provider and becomes visible according to that provider's rules.
Never attach a private corpus, credential, or personal quiz history to an issue.

## Changes

Material changes update the version date and the embedded notice shown during
onboarding.
