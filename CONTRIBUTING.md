# Contributing

Issues and pull requests are welcome. Describe the problem, the expected behavior, and a small reproducible example. Keep pull requests focused and include the checks you ran.

## Setup and checks

Follow the root README for demo mode or the full local stack. Backend dependencies are managed by Poetry; frontend and animator dependencies use their committed npm lockfiles.

```sh
poetry -C backend install --extras ai
npm ci --prefix frontend
python3 backend/scripts/check_hexagonal_boundaries.py --root backend/src
poetry -C backend run tach check
poetry -C backend run ruff check src tests
poetry -C backend run mypy
poetry -C backend run pytest tests/unit
npm --prefix frontend run build
npm --prefix frontend run format:check
npm --prefix frontend test
```

Run integration tests with Docker available using `poetry -C backend run pytest tests/integration`. Live AI tests are opt-in. Preserve all always-on architecture, typing, lint, and coverage gates in pre-commit and CI.

## Architecture and tests

Follow [AGENTS.md](AGENTS.md). Keep business rules pure, expose explicit use-case DTOs, inject ports, and implement infrastructure at the edge. New backend domains need an explicit entry in `backend/tach.toml`. Use deterministic fakes for unit tests and real disposable dependencies for adapter integration tests. Do not monkey patch.

## Secrets and media

Never commit live credentials, database exports, generated conversation logs, signed asset URLs, or private account data. Use placeholders in environment examples. Run `gitleaks dir . --redact` and `gitleaks git --redact --log-opts="--all"` before publishing changes. Review screenshots and generated videos before adding them. Preserve third-party license notices.

Contributions are distributed under the project's MIT license, subject to existing third-party notices.
