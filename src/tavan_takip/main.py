"""Command-line entry point for one local monitoring cycle."""

from __future__ import annotations

import sys

from tavan_takip.application import run_monitoring_cycle
from tavan_takip.config import get_settings
from tavan_takip.data_providers import YFinanceProvider
from tavan_takip.persistence import SQLiteIPOTrackingStateRepository


def main() -> int:
    """Run one monitoring cycle and return a process exit code."""
    settings = get_settings()
    provider = YFinanceProvider(
        retry_attempts=settings.yfinance_retry_attempts,
        retry_wait_seconds=settings.yfinance_retry_wait_seconds,
    )
    state_repository = SQLiteIPOTrackingStateRepository(settings.sqlite_database_path)
    outcome = run_monitoring_cycle(
        settings=settings,
        data_provider=provider,
        state_repository=state_repository,
        output=sys.stdout,
    )
    return outcome.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
