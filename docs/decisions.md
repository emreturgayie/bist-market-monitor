# Architecture Decision Records

This document records key design decisions. The format is intentionally lightweight.

## ADR 001: Use Python 3.14

**Status:** Accepted

**Decision:** Target Python 3.14.

**Rationale:** The project is a portfolio-oriented modern Python codebase. Python 3.14 enables current
typing/runtime behavior and keeps the stack forward-looking.

**Consequence:** CI and Docker are configured for Python 3.14. Contributors need a compatible Python
runtime.

## ADR 002: Use Clean Architecture

**Status:** Accepted

**Decision:** Keep domain logic independent from infrastructure.

**Rationale:** The project integrates market data, persistence, scheduling, and notifications. Clean
Architecture keeps business rules testable and makes adapters replaceable.

**Consequence:** More modules exist than in a simple script, but the boundaries are clearer and easier
to extend.

## ADR 003: Use SQLite for Local Persistence

**Status:** Accepted

**Decision:** Persist IPO tracking state and alert deduplication state in SQLite.

**Rationale:** SQLite is simple, local, reliable enough for a one-process monitoring tool, and easy to
mount as a Docker volume.

**Consequence:** SQLite is not intended as a multi-writer distributed store. A different persistence
adapter may be needed for a larger production deployment.

## ADR 004: Use yfinance as Demo Data Provider

**Status:** Accepted

**Decision:** Implement yfinance as the first data provider adapter.

**Rationale:** yfinance is easy to use for development and portfolio demonstration.

**Consequence:** It is not an official BIST data source. Data may be delayed, incomplete, or inaccurate.
Production-grade data should come from an official or licensed provider.

## ADR 005: Use Telegram as First Notification Channel

**Status:** Accepted

**Decision:** Implement Telegram through a notifier port.

**Rationale:** Telegram is practical for alerting and easy to configure locally.

**Consequence:** Telegram remains optional. The notifier port allows additional channels later.

## ADR 006: Use Docker Compose for Local Deployment

**Status:** Accepted

**Decision:** Provide Docker and Docker Compose for local runtime packaging.

**Rationale:** Docker Compose gives a repeatable runtime environment and a straightforward SQLite
volume setup.

**Consequence:** Docker Compose runs the production runner by default and can run the read-only
dashboard through an optional profile. Image publishing is not automated yet.

## ADR 007: Use GitHub Actions for CI

**Status:** Accepted

**Decision:** Run tests, linting, formatting checks, and type checks in GitHub Actions.

**Rationale:** CI protects the main branch and demonstrates professional engineering hygiene.

**Consequence:** Docker build validation is not included yet.

## ADR 008: No Automatic Trading

**Status:** Accepted

**Decision:** The system will not place orders, execute trades, or integrate with order-routing APIs.

**Rationale:** The project is a monitoring and alerting system, not an automated trading system.

**Consequence:** Any future broker or order execution integration is out of scope unless the project
scope is explicitly changed.

## ADR 009: No Investment Advice

**Status:** Accepted

**Decision:** Keep clear disclaimers in README, CLI output, and Telegram messages.

**Rationale:** The software emits technical monitoring signals, not financial recommendations.

**Consequence:** Users must verify data independently and make their own financial decisions.

## ADR 010: Use FastAPI, Jinja2, HTMX, and Chart.js for the Dashboard

**Status:** Accepted

**Decision:** Implement the first dashboard as a lightweight server-rendered FastAPI application with
Jinja2 templates, HTMX partial refreshes, and Chart.js visualizations.

**Rationale:** The dashboard should be simple, inspectable, and easy to deploy alongside the existing
Python application. Server-rendered pages avoid a separate frontend build pipeline, while HTMX and
Chart.js provide enough interactivity for persisted monitoring state.

**Consequence:** The dashboard is read-only and intentionally modest. It does not replace the CLI,
run monitoring cycles, or introduce a single-page application stack.

## ADR 011: Add Provider Selection with an AlgoLab Mock Adapter

**Status:** Accepted

**Decision:** Add `TAVAN_TAKIP_DATA_PROVIDER` with `yfinance` and `algolab_mock` options. Keep
yfinance as the default demo provider and add a network-free AlgoLab mock adapter.

**Rationale:** The system needs a clean extension point for production-grade BIST data providers
before real credentials, API behavior, and licensing details are introduced. A mock adapter lets the
application, CLI, dashboard, and tests exercise provider selection without making unsupported claims
about real AlgoLab integration.

**Consequence:** `algolab_mock` is not a live data provider and performs no network calls. Real
AlgoLab or another licensed real-time provider remains future work behind the existing `DataProvider`
port.

## ADR 012: Add a Production Monitoring Runner

**Status:** Accepted

**Decision:** Add a long-running production runner that reuses `MonitoringSchedulePolicy`,
`MonitoringOrchestrator`, SQLite persistence, provider factories, and optional notifiers.

**Rationale:** Docker deployment needs a process that can run continuously without duplicating
scheduling or monitoring business logic. Keeping the runner in the application layer lets it
coordinate existing services while preserving domain and adapter boundaries.

**Consequence:** Docker now defaults to the production runner. The one-shot CLI remains available for
manual checks, and the dashboard remains a read-only interface that observes persisted runner state.
