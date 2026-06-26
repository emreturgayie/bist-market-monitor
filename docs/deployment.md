# Deployment

## Local Development

Create a virtual environment and install the project with development dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run one monitoring cycle:

```bash
TAVAN_TAKIP_TRACKED_SYMBOLS=THYAO.IS,SISE.IS tavan-takip
```

Run the read-only dashboard:

```bash
TAVAN_TAKIP_TRACKED_SYMBOLS=THYAO.IS,SISE.IS tavan-takip-dashboard
```

The dashboard listens on `127.0.0.1:8000` by default.

Run quality checks:

```bash
pytest
ruff check .
black --check .
mypy src tests
```

## Docker Compose

Create a local environment file:

```bash
cp .env.example .env
```

Edit `.env` and set at least:

```text
TAVAN_TAKIP_TRACKED_SYMBOLS=THYAO.IS,SISE.IS
```

Run with Docker Compose:

```bash
docker compose up --build
```

Run a one-off container:

```bash
docker compose run --rm app
```

Run the dashboard container:

```bash
docker compose --profile dashboard up dashboard --build
```

The dashboard is available at `http://localhost:8000` unless `TAVAN_TAKIP_DASHBOARD_PORT` is
changed.

## Environment Variables

| Variable | Purpose |
| --- | --- |
| `TAVAN_TAKIP_TRACKED_SYMBOLS` | Comma-separated symbols to monitor |
| `TAVAN_TAKIP_DATA_PROVIDER` | Data provider adapter: `yfinance` or `algolab_mock` |
| `TAVAN_TAKIP_YFINANCE_RETRY_ATTEMPTS` | yfinance retry attempts |
| `TAVAN_TAKIP_YFINANCE_RETRY_WAIT_SECONDS` | wait time between yfinance retries |
| `TAVAN_TAKIP_SQLITE_DATABASE_PATH` | SQLite database path |
| `TAVAN_TAKIP_TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TAVAN_TAKIP_TELEGRAM_CHAT_ID` | Telegram chat ID |
| `TAVAN_TAKIP_TELEGRAM_RETRY_ATTEMPTS` | Telegram retry attempts |
| `TAVAN_TAKIP_TELEGRAM_RETRY_WAIT_SECONDS` | wait time between Telegram retries |
| `TAVAN_TAKIP_DASHBOARD_HOST` | dashboard bind host |
| `TAVAN_TAKIP_DASHBOARD_PORT` | dashboard bind port |

Telegram variables are optional. If token or chat ID is missing, Telegram notifications are disabled.
The `algolab_mock` data provider is network-free and exists only as a placeholder for future real
AlgoLab integration.

## SQLite Volume

In Docker Compose, SQLite state is stored at:

```text
/data/tavan_takip.sqlite3
```

The path is backed by the `sqlite-data` named volume.

Local runs default to:

```text
tavan_takip.sqlite3
```

unless `TAVAN_TAKIP_SQLITE_DATABASE_PATH` is set.

## CI/CD Overview

GitHub Actions runs on pushes and pull requests to `main`.

The CI workflow:

1. checks out the repository,
2. sets up Python 3.14,
3. installs the project with development dependencies,
4. runs tests,
5. runs Ruff,
6. checks Black formatting,
7. runs mypy.

There is no deployment pipeline yet.

## Operational Notes

- The current CLI runs one monitoring cycle and exits.
- The dashboard is read-only and shows persisted SQLite state.
- A production runner or external scheduler is future work.
- SQLite is suitable for local/single-process use.
- yfinance data can be delayed, incomplete, or unavailable.
- Provider failures are reported per symbol where possible.
- Notification failures are captured and do not crash the entire monitoring run.

## Security Notes

- Do not commit `.env`.
- Do not bake Telegram credentials into Docker images.
- Docker Compose loads `.env` at runtime.
- SQLite data is persisted in a volume, not inside the image.
- The application does not execute trades or place orders.
