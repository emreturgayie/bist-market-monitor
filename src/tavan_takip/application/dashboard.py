"""Application-level read models for the monitoring dashboard."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from tavan_takip.config import Settings
from tavan_takip.domain import IPOTrackingState, MonitoringMode
from tavan_takip.market import DEFAULT_MARKET_TIMEZONE, MarketSession, MarketSessionEngine
from tavan_takip.persistence import (
    BreakAlertReadRepository,
    BreakAlertRecord,
    BreakAlertRepository,
    IPOTrackingStateRepository,
    RunnerStatusRepository,
)

DEFAULT_SCHEDULER_STATUS = "adaptive policy active; production runner available"
DEFAULT_DATA_PROVIDER_NAME = "yfinance"


@dataclass(frozen=True, slots=True)
class DashboardSymbolRow:
    """Display-ready state for one tracked symbol."""

    symbol: str
    consecutive_ceiling_days: int
    lifecycle_status: str
    monitoring_mode: str
    last_processed_trading_date: str
    alert_status: str


@dataclass(frozen=True, slots=True)
class MonitoringModeSummary:
    """Aggregated monitoring mode counts for the dashboard homepage."""

    early: int
    hourly: int


@dataclass(frozen=True, slots=True)
class DashboardOverview:
    """Read model for the dashboard homepage."""

    current_time: datetime
    market_session: MarketSession
    tracked_symbol_count: int
    monitoring_mode_summary: MonitoringModeSummary
    symbols: tuple[DashboardSymbolRow, ...]
    chart_labels: tuple[str, ...]
    chart_values: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class RecentAlertRow:
    """Display-ready recent alert row."""

    symbol: str
    sent_at: str


@dataclass(frozen=True, slots=True)
class RecentAlertsView:
    """Read model for the recent alerts page."""

    alerts: tuple[RecentAlertRow, ...]


@dataclass(frozen=True, slots=True)
class SystemStatusView:
    """Read model for the system status page."""

    current_time: datetime
    docker_status: str
    database_path: str
    scheduler_status: str
    runner_status: str
    runner_last_execution_at: str
    telegram_status: str
    data_provider: str


class DashboardService:
    """Build dashboard read models from application ports and settings."""

    def __init__(
        self,
        *,
        settings: Settings,
        state_repository: IPOTrackingStateRepository,
        alert_repository: BreakAlertRepository,
        alert_read_repository: BreakAlertReadRepository,
        runner_status_repository: RunnerStatusRepository | None = None,
        market_session_engine: MarketSessionEngine | None = None,
        now_provider: Callable[[], datetime] | None = None,
        docker_status_provider: Callable[[], str] | None = None,
        scheduler_status: str = DEFAULT_SCHEDULER_STATUS,
        data_provider_name: str = DEFAULT_DATA_PROVIDER_NAME,
    ) -> None:
        self._settings = settings
        self._state_repository = state_repository
        self._alert_repository = alert_repository
        self._alert_read_repository = alert_read_repository
        self._runner_status_repository = runner_status_repository
        self._market_session_engine = market_session_engine or MarketSessionEngine()
        self._now_provider = now_provider or _default_now
        self._docker_status_provider = docker_status_provider or detect_docker_status
        self._scheduler_status = scheduler_status
        self._data_provider_name = data_provider_name

    def get_overview(self) -> DashboardOverview:
        """Return the display model for the dashboard homepage."""
        current_time = self._now_provider()
        symbols = self._build_symbol_rows(self._settings.tracked_symbols)
        mode_counts = Counter(row.monitoring_mode for row in symbols)
        return DashboardOverview(
            current_time=current_time,
            market_session=self._market_session_engine.evaluate(current_time),
            tracked_symbol_count=len(self._settings.tracked_symbols),
            monitoring_mode_summary=MonitoringModeSummary(
                early=mode_counts[MonitoringMode.EARLY.value],
                hourly=mode_counts[MonitoringMode.HOURLY.value],
            ),
            symbols=symbols,
            chart_labels=tuple(row.symbol for row in symbols),
            chart_values=tuple(row.consecutive_ceiling_days for row in symbols),
        )

    def get_symbol_rows(self) -> tuple[DashboardSymbolRow, ...]:
        """Return display-ready rows for the configured symbol table."""
        return self._build_symbol_rows(self._settings.tracked_symbols)

    def get_recent_alerts(self, *, limit: int = 20) -> RecentAlertsView:
        """Return recent sent break alerts."""
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        alerts = tuple(
            _alert_row(record) for record in self._alert_read_repository.list_alerts(limit)
        )
        return RecentAlertsView(alerts=alerts)

    def get_system_status(self) -> SystemStatusView:
        """Return display-ready runtime status details."""
        runner_status, runner_last_execution_at = self._runner_status()
        return SystemStatusView(
            current_time=self._now_provider(),
            docker_status=self._docker_status_provider(),
            database_path=str(self._settings.sqlite_database_path),
            scheduler_status=self._scheduler_status,
            runner_status=runner_status,
            runner_last_execution_at=runner_last_execution_at,
            telegram_status=_telegram_status(self._settings),
            data_provider=self._data_provider_name,
        )

    def _build_symbol_rows(
        self,
        tracked_symbols: Sequence[str],
    ) -> tuple[DashboardSymbolRow, ...]:
        rows: list[DashboardSymbolRow] = []
        for symbol in tracked_symbols:
            state = self._state_repository.load(symbol) or IPOTrackingState(symbol=symbol)
            rows.append(self._symbol_row(state))
        return tuple(rows)

    def _symbol_row(self, state: IPOTrackingState) -> DashboardSymbolRow:
        alert_sent = self._alert_repository.has_break_alert_been_sent(state.symbol)
        return DashboardSymbolRow(
            symbol=state.symbol,
            consecutive_ceiling_days=state.consecutive_ceiling_days,
            lifecycle_status=state.lifecycle_state.value,
            monitoring_mode=state.monitoring_mode.value,
            last_processed_trading_date=(
                state.last_processed_trading_date.isoformat()
                if state.last_processed_trading_date is not None
                else "Never"
            ),
            alert_status="sent" if alert_sent else "clear",
        )

    def _runner_status(self) -> tuple[str, str]:
        if self._runner_status_repository is None:
            return "unavailable", "Never"
        runner_status = self._runner_status_repository.load_runner_status()
        if runner_status is None:
            return "not started", "Never"
        return (
            runner_status.status,
            (
                runner_status.last_execution_at.isoformat()
                if runner_status.last_execution_at is not None
                else "Never"
            ),
        )


def detect_docker_status() -> str:
    """Return a lightweight container status for local system visibility."""
    if Path("/.dockerenv").exists():
        return "inside Docker container"
    return "not detected"


def _default_now() -> datetime:
    return datetime.now(DEFAULT_MARKET_TIMEZONE)


def _telegram_status(settings: Settings) -> str:
    if settings.telegram_bot_token and settings.telegram_chat_id:
        return "configured"
    return "not configured"


def _alert_row(record: BreakAlertRecord) -> RecentAlertRow:
    return RecentAlertRow(symbol=record.symbol, sent_at=record.sent_at.isoformat())
