# Demo Script

## 1-Minute Demo Script

1. Open the repository and show the README status, badges, and safety disclaimer.
2. Explain the core idea: monitor selected BIST IPO symbols for potential ceiling-break events.
3. Show the architecture diagram and point out that the domain layer is independent from adapters.
4. Open the dashboard and highlight market status, tracked symbols, monitoring modes, recent alerts,
   and runner status.
5. Mention SQLite persistence, Telegram notifications, Docker Compose, CI, and 136 tests.
6. Close with the limitation: yfinance is demo/delayed data, this is not investment advice, and
   there is no automatic trading.

## 3-Minute Demo Script

1. Start with the product problem:
   "Newly listed BIST stocks may stay at the daily ceiling for several sessions. This project turns
   manual monitoring into a restart-safe, testable monitoring system."
2. Show the README feature list and support matrix.
3. Show the architecture diagram:
   - Domain: ceiling calculation, tracking, break detection.
   - Application: orchestration, CLI, runner, dashboard read models.
   - Adapters: yfinance, SQLite, Telegram, Docker, FastAPI.
4. Show the dashboard:
   - market status,
   - current time,
   - tracked symbol count,
   - monitoring mode summary,
   - symbols table,
   - chart,
   - recent alerts,
   - system status.
5. Show the CLI command and explain that it runs one monitoring cycle.
6. Show Docker Compose and explain that the production runner is the default service and the
   dashboard is optional.
7. Show the test command and mention 136 passing tests.
8. End with limitations:
   "This is monitoring only, yfinance is demo data, and real licensed provider integration is future
   work."

## Dashboard Demo Flow

1. Start the dashboard:

   ```bash
   TAVAN_TAKIP_TRACKED_SYMBOLS=THYAO.IS,SISE.IS tavan-takip-dashboard
   ```

2. Open `http://127.0.0.1:8000`.
3. Show the homepage metrics:
   - market status,
   - current time,
   - tracked symbols,
   - monitoring modes.
4. Show the symbols table:
   - symbol,
   - consecutive ceiling days,
   - lifecycle status,
   - monitoring mode,
   - last processed trading date,
   - alert status.
5. Open Recent Alerts and explain alert deduplication.
6. Open System Status and show:
   - database path,
   - scheduler status,
   - Telegram configured status,
   - data provider,
   - runner status.
7. Explain that the dashboard is read-only and does not contain trading functionality.

## CLI Demo Flow

1. Run one monitoring cycle:

   ```bash
   TAVAN_TAKIP_TRACKED_SYMBOLS=THYAO.IS,SISE.IS tavan-takip
   ```

2. Explain the result:
   - if market is closed, no prices are fetched;
   - if market is open, each symbol is processed independently;
   - missing quotes and provider errors are reported per symbol;
   - break signals are structured and can trigger notifications when configured.
3. Point out that the CLI always includes the "Not investment advice" disclaimer.

## Docker Demo Flow

1. Create a local environment file:

   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and set `TAVAN_TAKIP_TRACKED_SYMBOLS`.
3. Start the production runner:

   ```bash
   docker compose up --build
   ```

4. Explain that SQLite state is stored in the `/data` volume.
5. Start the dashboard profile:

   ```bash
   docker compose --profile dashboard up --build
   ```

6. Open the dashboard at `http://127.0.0.1:8000`.
7. Mention that secrets stay in `.env` and are not copied into the Docker image.
