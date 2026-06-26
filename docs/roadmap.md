# Roadmap

## Completed Milestones

- Project foundation and package structure
- Domain model for market quotes
- Data provider port and yfinance adapter
- Ceiling-price calculation and ceiling-break detection
- IPO tracking state and monitoring modes
- Market session engine
- Application-level monitoring orchestrator
- One-shot CLI
- SQLite persistence with schema versioning
- Telegram notification engine
- Adaptive scheduling policy
- Docker and Docker Compose support
- GitHub Actions CI
- Professional README
- Engineering documentation
- Read-only FastAPI monitoring dashboard
- Production data provider selection foundation with AlgoLab mock adapter
- 129 automated tests

## Short-Term Roadmap

- Add a production runner that uses the adaptive scheduler policy.
- Add better CLI error handling for operational failures.
- Add Docker image build validation to CI.
- Add dashboard authentication before any public deployment.
- Improve README examples with real but safe sample configurations.
- Add architecture decision records as files if the decision log grows.

## Long-Term Roadmap

- Replace the AlgoLab mock with a real licensed/official real-time data provider adapter.
- Expand the dashboard with historical charts and richer operational views.
- Add richer BIST calendar support, including half-days and official holidays.
- Add configurable tick-size rules for BIST price bands.
- Add additional notification channels.
- Add deployment documentation for a long-running production environment.
- Prepare a public release with versioned artifacts and changelog discipline.

## Explicit Future Work

These items are not currently implemented:

- Real AlgoLab or real-time licensed market data integration
- continuous production runner
- authenticated public dashboard deployment
- public release process
- broker integration
- automatic trading

Automatic trading remains intentionally out of scope.
