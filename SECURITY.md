# Security Policy

## Supported versions

The current `0.1.x` line receives security fixes. This is a local, single-user desktop tool; there is no hosted service.

## Reporting a vulnerability

Please use GitHub's **private vulnerability reporting** flow:

1. Open the repository's **Security** tab.
2. Choose **Report a vulnerability**.
3. Include the affected version, a minimal reproduction, and the impact.

Do not open a public issue containing an API key, token, personal data, or a working exploit. If a secret was exposed, revoke and rotate it first.

## Scope

In scope:

- Secret handling and accidental logging
- Prompt-injection paths from feed content into model output
- HTML escaping and unsafe link handling
- The JavaScript ↔ Python bridge and desktop actions
- Dependency or configuration issues that affect the local app

Out of scope:

- Vulnerabilities in upstream sources, model providers, or Windows itself
- Social engineering or physical access
- Denial of service against a third-party API

## Design notes

- API keys live in environment variables or `.env`; `print-config` redacts them.
- Runtime state, feedback, logs, and generated digests are git-ignored.
- Feed text is treated as data, never as instructions. Model output is parsed and validated as JSON; it is not executed as a shell command or tool call.
- Rendered HTML is autoescaped. Article links are passed through a URL sanitizer.
- The app has no telemetry and no arbitrary shell/file-access feature.
