# Contributing

Thanks for your interest in contributing to BIST Market Monitor.

This project is intentionally scoped as a monitoring and alerting system. Automatic trading, broker
integration, and order execution are out of scope.

## Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Code Style

- Use Python 3.14-compatible code.
- Keep type hints strict and complete.
- Keep business logic in the domain/application layers.
- Keep external integrations behind ports/adapters.
- Prefer small, maintainable functions.
- Do not add placeholder implementations or TODO comments.
- Do not perform real network calls in tests.

## Quality Checks

Run the full local quality suite before opening a pull request:

```bash
pytest
ruff check .
black --check .
mypy src tests
```

If a formatting check fails, run:

```bash
black .
```

## Tests

Tests should be focused, deterministic, and network-free. Use fakes or mocks for market data,
Telegram, scheduler timing, and persistence edge cases.

Add or update tests when changing:

- domain calculations,
- tracking behavior,
- scheduling decisions,
- persistence schemas,
- notification behavior,
- dashboard-rendered content,
- runner orchestration.

## Branch Naming

Use short, descriptive branch names. Preferred prefixes:

- `feat/` for features,
- `fix/` for bug fixes,
- `docs/` for documentation,
- `refactor/` for internal cleanup,
- `test/` for test-only changes.

Examples:

- `feat/real-data-provider`
- `fix/alert-deduplication`
- `docs/release-notes`

## Commit Conventions

Use concise conventional-style commit messages:

- `feat: add production runner`
- `fix: handle provider failure per symbol`
- `docs: update deployment guide`
- `test: cover scheduler edge cases`
- `refactor: isolate provider factory`

## Pull Requests

Pull requests should include:

- a clear summary of the change,
- tests or a short explanation when tests are not needed,
- confirmation that quality checks passed,
- notes about configuration, migration, or documentation changes.

Keep pull requests focused. Avoid mixing unrelated refactors with behavior changes.

## Safety Requirements

Do not add automatic trading, order execution, broker integration, or investment advice features.
Market data and alerts must remain informational.
