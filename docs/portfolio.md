# Portfolio Overview

## Project Summary

BIST Market Monitor is a production-oriented Python application for monitoring selected Borsa
Istanbul IPO symbols and detecting potential daily ceiling-break events. It started as a focused IPO
ceiling-break alert system and evolved into a modular market monitoring platform with domain logic,
persistence, notifications, scheduling, Docker deployment, CI, and a read-only dashboard.

The project is monitoring and alerting only. It does not execute trades and is not investment
advice.

## Problem Solved

Newly listed BIST stocks can trade at their daily upper price limit for multiple sessions. Investors
who manually monitor these symbols need to know when a ceiling streak may be weakening, but manual
checking is repetitive, time-sensitive, and prone to missed context.

This project solves the engineering problem of turning that manual workflow into a testable,
observable, restart-safe monitoring system:

- track IPO symbols across trading days,
- calculate theoretical ceiling prices with decimal precision,
- detect potential ceiling breaks with tolerance rules,
- avoid repeated alerts for the same break state,
- persist state locally,
- respect market session rules,
- run as a CLI, Docker service, and dashboard-backed monitor.

## Technical Highlights

- Clean Architecture with domain logic isolated from yfinance, SQLite, Telegram, FastAPI, and Docker.
- Decimal-based financial calculations to avoid floating-point drift.
- Explicit domain models for quotes, ceiling status, tracking state, tracking result, and signals.
- Provider abstraction with yfinance as demo data and AlgoLab mock as future integration boundary.
- SQLite persistence with schema versioning, migrations, integrity constraints, and alert
  deduplication.
- Optional Telegram notification adapter with retry/error handling and no hard dependency in the
  domain layer.
- Adaptive scheduling policy that decides next run times without external schedulers.
- Production runner that reuses the orchestrator and scheduler instead of duplicating monitoring
  logic.
- FastAPI/Jinja2/HTMX dashboard that reads application-level models and avoids business logic in
  routes.
- Docker Compose setup with persistent SQLite volume.
- GitHub Actions CI for tests, linting, formatting, and static typing.
- 136 automated tests covering core rules, adapters, orchestration, dashboard, CLI, persistence,
  notifications, and runner behavior.

## Engineering Decisions

### Clean Architecture

The domain layer contains deterministic business rules and depends on no framework or infrastructure
tool. This keeps the core IPO tracking logic testable and stable while adapters can change.

### SQLite For v1.0

SQLite is enough for a local monitoring service and keeps deployment simple. The schema has explicit
versioning so the persistence layer can evolve without turning the first release into a database
platform.

### yfinance As Demo Provider

yfinance is useful for local demonstration, but the documentation is honest that it may be delayed
or incomplete. A provider factory and AlgoLab mock prepare the system for future licensed data
integration.

### Optional Notifications

Telegram is implemented behind a notifier interface. Notification failures are surfaced without
crashing the whole monitoring run, and alert deduplication prevents repeated alerts for the same
state.

### Scheduler Policy Before Scheduler Framework

The project uses a pure scheduling policy instead of immediately adding APScheduler or another
runtime dependency. This made the hard part, deciding when to run, deterministic and easy to test.

## What Makes This Portfolio-Worthy

This project shows the ability to take a real-world product idea and turn it into a maintainable
engineering system rather than a script. It demonstrates product thinking, architecture discipline,
testing, documentation, deployment awareness, and honest risk communication.

Strong portfolio signals include:

- clear layering and dependency boundaries,
- realistic adapter and factory design,
- persistence with migrations instead of ad hoc files,
- production runner behavior with graceful shutdown,
- no-network unit tests,
- Docker and CI readiness,
- professional README, release notes, security notes, and engineering docs.

## Skills Demonstrated

- Python application architecture
- Clean Architecture and SOLID design
- Domain modeling
- Financial calculation discipline with `Decimal`
- Test-driven hardening and mocking external systems
- SQLite schema design and migrations
- FastAPI dashboard development
- Docker Compose deployment
- GitHub Actions CI
- Technical writing and release engineering
- Product risk communication

## How To Explain It In Interviews

Start with the product story, then move to the architecture:

> I built a Python monitoring platform for BIST IPO ceiling-break detection. The domain layer models
> market quotes, ceiling calculations, tracking state, and break signals. The application layer
> orchestrates market-session checks, provider calls, tracking, persistence, and optional
> notifications. Infrastructure concerns like yfinance, SQLite, Telegram, Docker, and FastAPI are
> isolated behind adapters.

Then emphasize one engineering challenge:

> The most important hardening work was preventing repeated alerts and keeping the system
> restart-safe. I added explicit persisted tracking state, alert deduplication, schema versioning,
> and tests that verify provider failures and notification failures do not bring down the whole run.

Close with limitations:

> It is not a trading bot and not investment advice. yfinance is only a demo data provider. A real
> production version would need licensed market data, authentication for the dashboard, richer BIST
> calendar support, and stronger operational monitoring.
