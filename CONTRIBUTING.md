# Contributing

This is primarily a personal daily tool, but focused issues and pull requests are welcome.

## Setup

```powershell
git clone https://github.com/LePhuQuy05/daily-digest.git
cd daily-digest
uv sync
uv run daily-digest demo --no-open
```

The demo uses bundled fixtures and needs no API key or network access.

## Tests

```powershell
uv run pytest -o addopts=''
```

The suite is offline: HTTP and LLM calls are mocked, and desktop integrations are isolated. Add a regression test for every behavior change, especially around fallback paths, HTML escaping, and the JS bridge.

## Pull requests

- Keep the change scoped; explain the problem, the approach, and the trade-off.
- Include the test command and result in the PR description.
- Update the README or `docs/` when behavior or setup changes.
- Do not commit `.env`, `config.yaml`, runtime state, feedback, logs, or generated digests.
- Use conventional commit messages such as `fix(ranking): keep heuristic fallback on timeout`.

For security issues, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.
