# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-06-26

### Added

- Clean Architecture project foundation with typed domain, application, adapter, and infrastructure
  layers.
- Market data provider port with yfinance as the default demo/delayed data adapter.
- Configurable provider selection with a network-free AlgoLab mock adapter for future integration
  work.
- `MarketQuote` domain model and Decimal-based IPO ceiling price calculation.
- IPO ceiling-break detection with configurable daily limit, tick size, tolerance, and alert
  severity.
- IPO tracking engine for consecutive ceiling days, lifecycle state, monitoring mode, and
  same-trading-day deduplication.
- Market calendar/session engine with timezone-aware datetimes, market hours, weekends, holidays,
  and structured status.
- Monitoring orchestrator that connects session checks, provider calls, tracking, persistence, and
  optional notifications.
- One-shot CLI entry point for local monitoring cycles.
- SQLite persistence for tracking state, alert deduplication, alert history, runner status, schema
  versioning, and migrations.
- Telegram notification adapter with message formatting, retry behavior, and mocked HTTP tests.
- Adaptive scheduling policy for early and hourly IPO monitoring modes.
- Long-running production runner for Docker deployment that reuses the scheduler and orchestrator.
- FastAPI/Jinja2/HTMX dashboard with system status, runner status, persisted symbol state, recent
  alerts, and Chart.js visualization.
- Dockerfile and Docker Compose support with SQLite volume persistence.
- GitHub Actions CI for tests, Ruff, Black, and mypy.
- Professional README, engineering docs, release notes, and roadmap.
- 136 automated tests covering domain logic, orchestration, persistence, dashboard rendering,
  provider selection, scheduler behavior, notifications, CLI output, and runner behavior.

### Security

- Documented that the project does not provide investment advice, does not execute trades, and must
  not be treated as a financial decision system.
- Kept Telegram credentials and local `.env` files outside the Docker image.
- Added explicit documentation for yfinance demo/delayed data limitations and future licensed data
  provider work.

### Known Limitations

- yfinance is suitable only for demo/development use and may provide delayed, incomplete, or
  inaccurate market data.
- AlgoLab is represented by a mock adapter only; real AlgoLab integration is not implemented.
- SQLite is intended for local/single-process deployment.
- The dashboard is read-only and has no authentication layer yet.
- BIST tick-size and holiday rules are simplified and configurable, not official.
