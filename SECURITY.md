# Security policy

## Supported versions

Security fixes target the latest published release and the default branch.
Older releases are not maintained unless explicitly stated.

## Reporting a vulnerability

Do not disclose vulnerabilities, credentials, private corpus content, personal
learning data, or working exploits in a public issue.

Use GitHub's private vulnerability reporting feature for this repository. If it
is not enabled, contact the maintainer privately through the account that owns
the repository and provide only a synthetic reproduction in the first message.

Include the affected version, impact, reproduction steps, and any suggested
mitigation. Allow reasonable time for investigation and remediation before
public disclosure.

## Scope

Relevant reports include unsafe local file access, unintended non-loopback
network exposure, token or secret leakage, dependency vulnerabilities, prompt
or corpus injection crossing a trust boundary, insecure update or packaging
behavior, and flaws exposing another operating-system user's local data.

Incorrect quiz answers and ordinary model hallucinations are content-quality
issues rather than security vulnerabilities unless they demonstrate a security
boundary failure.
