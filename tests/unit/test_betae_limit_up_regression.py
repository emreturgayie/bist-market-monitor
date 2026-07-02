"""Regression tests for BETAE.IS consecutive limit-up handling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd

from tavan_takip.application import DashboardService, MonitoringOrchestrator
from tavan_takip.config import Settings
from tavan_takip.data_providers import YFinanceProvider
from tavan_takip.domain import CeilingStatus, IPOTrackingConfig, IPOTrackingLifecycleState
from tavan_takip.market import DEFAULT_MARKET_TIMEZONE
from tavan_takip.persistence import SQLiteIPOTrackingStateRepository

BETAE_CHECK_TIME = datetime(2026, 7, 2, 12, 55, tzinfo=DEFAULT_MARKET_TIMEZONE)


@dataclass
class FakeTicker:
    """Ticker double that never performs network requests."""

    intraday_history: pd.DataFrame
    daily_history: pd.DataFrame
    fast_info: Any

    def history(self, **kwargs: object) -> pd.DataFrame:
        if kwargs.get("interval") == "1d":
            return self.daily_history
        return self.intraday_history


class FakeFastInfo:
    """yfinance FastInfo-like object with a get method but no Mapping inheritance."""

    def __init__(self, values: dict[str, Any]) -> None:
        self._values = values

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)


def test_betae_limit_up_run_persists_dashboard_ceiling_streak(tmp_path: Path) -> None:
    repository = SQLiteIPOTrackingStateRepository(tmp_path / "betae.sqlite3")
    orchestrator = MonitoringOrchestrator(
        data_provider=YFinanceProvider(
            ticker_factory=lambda _: FakeTicker(
                intraday_history=_betae_intraday_history(),
                daily_history=_betae_daily_history(),
                fast_info=FakeFastInfo(
                    {
                        "previous_close": None,
                        "regularMarketPreviousClose": 44.0,
                        "currency": "TRY",
                    }
                ),
            ),
            retry_wait_seconds=0,
        ),
        state_repository=repository,
    )

    run_result = orchestrator.run(
        checked_at=BETAE_CHECK_TIME,
        configs=(IPOTrackingConfig(symbol="BETAE.IS"),),
    )

    symbol_result = run_result.symbol_results[0]
    assert symbol_result.tracking_result is not None
    tracking_result = symbol_result.tracking_result
    assert tracking_result.ceiling_signal.current_price == Decimal("48.400002")
    assert tracking_result.ceiling_signal.theoretical_ceiling_price == Decimal("48.40")
    assert tracking_result.ceiling_signal.status == CeilingStatus.AT_CEILING
    assert tracking_result.updated_state.consecutive_ceiling_days == 2
    assert tracking_result.updated_state.lifecycle_state == IPOTrackingLifecycleState.MONITORING
    assert tracking_result.updated_state.last_processed_trading_date == date(2026, 7, 2)

    persisted_state = repository.load("BETAE.IS")
    assert persisted_state is not None
    assert persisted_state.consecutive_ceiling_days == 2

    dashboard = DashboardService(
        settings=Settings(
            tracked_symbols=("BETAE.IS",),
            sqlite_database_path=tmp_path / "betae.sqlite3",
        ),
        state_repository=repository,
        alert_repository=repository,
        alert_read_repository=repository,
        now_provider=lambda: BETAE_CHECK_TIME,
        docker_status_provider=lambda: "not detected",
    )

    rows = dashboard.get_symbol_rows()

    assert rows[0].symbol == "BETAE.IS"
    assert rows[0].consecutive_ceiling_days == 2
    assert rows[0].lifecycle_status == IPOTrackingLifecycleState.MONITORING.value
    assert rows[0].alert_status == "clear"


def _betae_intraday_history() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Open": 48.400002,
                "High": 48.400002,
                "Low": 48.400002,
                "Close": 48.400002,
                "Volume": 83435,
            }
        ],
        index=pd.DatetimeIndex(["2026-07-02 12:51:00+03:00"]),
    )


def _betae_daily_history() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Open": 44.000000,
                "High": 44.000000,
                "Low": 44.000000,
                "Close": 44.000000,
                "Volume": 70412,
            },
            {
                "Open": 48.400002,
                "High": 48.400002,
                "Low": 48.400002,
                "Close": 48.400002,
                "Volume": 83435,
            },
        ],
        index=pd.DatetimeIndex(["2026-07-01 00:00:00+03:00", "2026-07-02 00:00:00+03:00"]),
    )
