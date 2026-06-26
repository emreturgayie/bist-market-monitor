# LinkedIn Post Drafts

## Professional Launch Post

I released v1.0.0 of BIST Market Monitor, a Python portfolio project focused on monitoring selected
Borsa Istanbul IPO symbols for potential daily ceiling-break events.

The goal was not to build a trading bot. The goal was to take a real monitoring workflow and design
it as a maintainable software system.

What it includes:

- Clean Architecture with isolated domain logic
- Decimal-based ceiling price calculations
- IPO tracking state and alert deduplication
- SQLite persistence with schema versioning
- Market session and adaptive scheduling logic
- Optional Telegram notifications
- Long-running production runner
- FastAPI dashboard with HTMX and Chart.js
- Docker Compose support
- GitHub Actions CI
- 136 automated tests
- Architecture, deployment, roadmap, release, and security documentation

yfinance is currently used only as a demo/delayed data provider, and the AlgoLab integration is a
mock placeholder for future licensed data work.

This project is monitoring and alerting only. It is not investment advice and does not execute
trades.

Repository: https://github.com/emreturgayie/bist-market-monitor

## Short Version

I released v1.0.0 of BIST Market Monitor, a Python portfolio project for monitoring selected BIST IPO
symbols and detecting potential ceiling-break events.

It includes Clean Architecture, SQLite persistence, Telegram alerts, adaptive scheduling, a
production runner, FastAPI dashboard, Docker Compose, GitHub Actions CI, and 136 tests.

It is not a trading bot and not investment advice. yfinance is used only as demo/delayed data.

Repository: https://github.com/emreturgayie/bist-market-monitor

## Longer Storytelling Version

One of my goals with this project was to move beyond a simple script and build something closer to
what I would expect from a maintainable production system.

The idea started with a practical BIST workflow: newly listed IPO stocks can trade at their daily
ceiling for multiple sessions, and manually watching for a possible ceiling break is repetitive and
easy to miss.

Instead of hardcoding that workflow into one script, I built BIST Market Monitor as a modular Python
application:

- the domain layer handles quotes, ceiling calculations, tracking state, and break signals,
- the application layer orchestrates market sessions, provider calls, persistence, and notifications,
- adapters isolate yfinance, SQLite, Telegram, Docker, and FastAPI,
- the runner reuses the scheduler policy instead of duplicating monitoring logic,
- the dashboard reads persisted state without owning business rules.

The first stable release includes Docker Compose, GitHub Actions CI, a FastAPI dashboard, SQLite
schema migrations, alert deduplication, Telegram notifications, and 136 automated tests.

I also documented the architecture, data flow, deployment model, decision records, roadmap, release
notes, security notes, and contribution workflow because good engineering is not only code. It is
also clarity.

Important limitations: this is monitoring and alerting only, not investment advice. yfinance is
demo/delayed data, real-time licensed data integration is future work, and there is no automatic
trading.

Repository: https://github.com/emreturgayie/bist-market-monitor
