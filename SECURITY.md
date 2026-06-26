# Security Policy

## Scope

BIST Market Monitor is a demo/portfolio monitoring project. It is designed for local monitoring and
alerting workflows, not for financial decision automation.

The project:

- does not execute trades,
- does not place orders,
- does not integrate with brokers,
- does not provide investment advice,
- does not guarantee market-data accuracy or freshness.

## Financial Safety

Signals emitted by this software are technical monitoring outputs only. They are not recommendations
to buy, sell, or hold securities. Users must verify market data through official or licensed sources
before making financial decisions.

yfinance is included as a demo/development adapter and may provide delayed, incomplete, or inaccurate
data. The AlgoLab adapter is currently a mock and performs no real network calls.

## Secrets

Do not commit local secrets, `.env` files, Telegram bot tokens, chat IDs, API credentials, or local
SQLite databases. Docker Compose loads secrets from the local environment at runtime; secrets are not
intended to be baked into images.

## Responsible Disclosure

If you discover a security issue, please avoid opening a public issue with exploitable details.
Contact the maintainer privately through the GitHub profile or repository contact channel, and
include:

- a short description of the issue,
- reproduction steps,
- affected version or commit,
- any relevant logs or screenshots with secrets removed.

The maintainer will review reports on a best-effort basis. This project is currently maintained as a
portfolio/open-source project and does not provide formal security SLAs.

## Supported Versions

| Version | Supported |
| --- | --- |
| `1.0.x` | Yes |
| `< 1.0.0` | No |
