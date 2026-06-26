# Interview Guide

## 30-Second Explanation

BIST Market Monitor is a Python monitoring platform for selected Borsa Istanbul IPO symbols. It
tracks consecutive ceiling days, detects potential ceiling breaks, persists state in SQLite, can send
Telegram alerts, and exposes both a CLI and a FastAPI dashboard. The project uses Clean Architecture,
so the business rules are independent from yfinance, SQLite, Telegram, Docker, and the web layer.

It is monitoring and alerting only, not investment advice and not automatic trading.

## 2-Minute Explanation

The project started with a focused problem: newly listed BIST stocks can remain at their daily price
ceiling for several sessions, and manually checking whether that ceiling has broken is repetitive.
I built a production-oriented monitoring system around that workflow.

The core domain layer models market quotes, IPO tracking configuration, ceiling calculations,
tracking state, lifecycle state, and break signals. Financial calculations use `Decimal`, daily
limit percentages and tolerance values are configurable, and the detector returns structured signals
instead of strings.

The application layer coordinates the system. It checks whether the market is open, fetches quotes
through a data provider interface, processes quotes through the tracker, persists state, deduplicates
alerts, and optionally sends Telegram notifications. The long-running production runner reuses the
same orchestrator and an adaptive scheduling policy, so it does not duplicate business logic.

Infrastructure is replaceable. yfinance is the default demo provider, AlgoLab is represented by a
mock adapter for future work, SQLite stores local state, Telegram is an optional notifier, Docker
Compose runs the service, and GitHub Actions verifies tests and code quality.

The project has 136 tests and documentation for architecture, data flow, deployment, decisions,
roadmap, release notes, security, and contribution workflow.

## 5-Minute Technical Walkthrough

1. The runtime starts from either the CLI, production runner, or dashboard.
2. Configuration is loaded with `pydantic-settings` using the `TAVAN_TAKIP_` environment prefix.
3. The provider factory selects `yfinance` or `algolab_mock` based on configuration.
4. The market session engine evaluates timezone-aware datetimes, weekends, holidays, and configured
   market hours.
5. If the market is closed, the orchestrator returns a structured skipped result without fetching
   prices.
6. If the market is open, the orchestrator fetches each symbol through the `DataProvider` port.
7. Provider failures are captured per symbol so one failed quote does not stop the full run.
8. Each valid quote is processed by the `IPOTracker`, which uses the `CeilingBreakDetector`.
9. The detector calculates the theoretical ceiling price with `Decimal`, applies tolerance, and
   returns a structured break signal when needed.
10. Tracking state stores consecutive ceiling days, lifecycle state, monitoring mode, last processed
    trading date, and alert status.
11. SQLite persists the state using a repository interface and schema migrations.
12. If a new break alert should be sent and has not already been sent for the current break state,
    the optional notifier sends a Telegram message.
13. The scheduler policy chooses the next run based on market status and monitoring mode.
14. The production runner sleeps until the next decision and handles shutdown gracefully.
15. The dashboard reads persisted state and system status through application services.

## Common Interview Questions And Answers

### Why Clean Architecture?

Because the business rules should survive changes to market data providers, notification channels,
storage, and interfaces. The IPO tracking rules are deterministic and easy to unit test because they
do not import yfinance, SQLite, Telegram, or FastAPI.

### Why use `Decimal` instead of `float`?

Financial thresholds and price comparisons should not depend on binary floating-point behavior.
`Decimal` makes rounding, tolerance, and tick-size logic explicit.

### Why SQLite?

SQLite is a pragmatic fit for a local single-service monitor. It gives durable state, simple
deployment, and enough structure for migrations without requiring database infrastructure.

### How do you prevent duplicate alerts?

Alert state is stored with the tracking state. When a symbol remains in the same broken state, the
orchestrator can see that an alert has already been sent and will not send another one for that
state.

### How do you test without real network calls?

External dependencies are behind interfaces. Tests use fake providers, mocked HTTP clients, and
temporary SQLite databases. yfinance and Telegram are not called during tests.

### What happens if one provider call fails?

The orchestrator captures provider errors per symbol and continues processing other symbols. The run
result reports the failure clearly.

### Why not implement automatic trading?

The project intentionally stops at monitoring and alerting. Trading would introduce regulatory,
financial, security, and product risks that are outside the project scope.

### Why not use APScheduler immediately?

The project first needed a deterministic scheduling policy. Keeping that policy pure made it easier
to test market-aware decisions. A scheduler framework can later execute the policy if needed.

## Hardest Technical Decisions

- Balancing simplicity with production readiness. The project needed persistence, Docker, CI, and
  observability without becoming a distributed system.
- Designing alert deduplication without polluting the domain layer with Telegram or SQLite details.
- Keeping the production runner small by reusing the orchestrator and scheduler policy.
- Being honest about yfinance limitations while still making the project runnable for demos.

## Tradeoffs

- SQLite keeps deployment simple but is not intended for multi-instance production.
- yfinance makes demos easy but is not reliable enough for production-grade BIST data.
- The dashboard is intentionally read-only and unauthenticated in v1.0.0.
- Holiday and tick-size rules are configurable but not official exchange-grade rule engines.
- The scheduler policy is testable and lightweight, but there is no external job runner yet.

## What I Would Improve Next

- Replace the AlgoLab mock with a real licensed data provider adapter.
- Add dashboard authentication before any public deployment.
- Improve BIST calendar and tick-size rule accuracy.
- Add structured metrics and richer runner observability.
- Add Docker image build validation and optional publishing in CI.
- Add historical charts and exportable monitoring reports.
