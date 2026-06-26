# Release v1.0.0

## Highlights

BIST Market Monitor v1.0.0 is the first stable portfolio release of the BIST IPO Ceiling Break Alert
System. It provides a modular monitoring platform for tracking selected BIST IPO symbols, detecting
potential ceiling breaks, persisting local state, sending optional Telegram alerts, and observing
state through a lightweight dashboard.

This release is monitoring and alerting only. It does not execute trades and is not investment
advice.

## Features

- Clean Architecture with domain, application, adapter, and infrastructure boundaries.
- Decimal-based ceiling price calculation and ceiling-break detection.
- IPO tracking state with consecutive ceiling-day counting and lifecycle status.
- Market session engine for Istanbul timezone, market hours, weekends, and configured holidays.
- Monitoring orchestrator for quote retrieval, state updates, persistence, and notifications.
- Long-running production runner for Docker deployment.
- One-shot CLI for local monitoring cycles.
- FastAPI dashboard for persisted tracking state, recent alerts, runner status, and system status.
- SQLite persistence with schema versioning and migrations.
- Telegram notification adapter with retry and error handling.
- Adaptive scheduler policy for early and hourly monitoring modes.
- Selectable data provider architecture with yfinance demo data and an AlgoLab mock adapter.
- Docker Compose deployment with persistent SQLite volume.
- GitHub Actions CI for tests, linting, formatting, and type checking.

## Architecture Summary

The domain layer contains deterministic business rules and has no dependency on yfinance, SQLite,
Telegram, Docker, FastAPI, or the CLI. Application services coordinate existing ports and adapters:

- `MonitoringOrchestrator` runs one monitoring cycle.
- `ProductionRunner` loops continuously using `MonitoringSchedulePolicy`.
- `DashboardService` builds read models for the web dashboard.

Adapters remain replaceable:

- yfinance is the current demo market data adapter.
- SQLite is the local persistence adapter.
- Telegram is the first notification adapter.
- AlgoLab is represented by a mock adapter only until real API integration is designed.

## Current Limitations

- yfinance is demo/development data and may be delayed, incomplete, or inaccurate.
- Real AlgoLab or licensed real-time BIST data integration is not implemented.
- SQLite is intended for local/single-process deployments.
- The dashboard is read-only and does not include authentication.
- BIST holiday and tick-size rules are simplified and configurable, not official.
- Docker image publishing is not automated yet.
- No automatic trading or broker integration exists.

## Future Roadmap

- Replace the AlgoLab mock with a real licensed data provider adapter.
- Add richer BIST calendar and tick-size rule support.
- Add dashboard authentication before any public deployment.
- Expand runner observability and historical execution views.
- Add Docker image build validation and optional image publishing in CI.
- Add additional notification channels.

## Verification

Release verification should run:

```bash
pytest
ruff check .
black --check .
mypy src tests
docker compose config
docker compose --profile dashboard config
```
