"""Command-line helpers for running one monitoring cycle."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TextIO

from tavan_takip.application.monitoring import (
    MonitoringOrchestrator,
    MonitoringRunResult,
    MonitoringRunStatus,
    SymbolMonitoringResult,
    SymbolMonitoringStatus,
)
from tavan_takip.config import Settings
from tavan_takip.data_providers import DataProvider
from tavan_takip.domain import IPOTrackingConfig, IPOTrackingState
from tavan_takip.market import DEFAULT_MARKET_TIMEZONE, MarketSessionEngine
from tavan_takip.notifications import Notifier
from tavan_takip.persistence import IPOTrackingStateRepository

DISCLAIMER = "Not investment advice."


@dataclass(frozen=True, slots=True)
class CliRunOutcome:
    """Result of executing one CLI monitoring cycle."""

    exit_code: int
    monitoring_result: MonitoringRunResult | None = None


def run_monitoring_cycle(
    *,
    settings: Settings,
    data_provider: DataProvider,
    output: TextIO,
    market_session_engine: MarketSessionEngine | None = None,
    state_repository: IPOTrackingStateRepository | None = None,
    notifier: Notifier | None = None,
    now_provider: Callable[[], datetime] | None = None,
) -> CliRunOutcome:
    """Run one local monitoring cycle and write readable CLI output."""
    if not settings.tracked_symbols:
        output.write("BIST IPO Ceiling Break Alert System\n")
        output.write("No symbols configured. Set TAVAN_TAKIP_TRACKED_SYMBOLS to run monitoring.\n")
        output.write(f"{DISCLAIMER}\n")
        return CliRunOutcome(exit_code=0)

    configs = _build_configs(settings.tracked_symbols)
    states = _build_initial_states(configs)
    checked_at = _current_time(now_provider)
    orchestrator = MonitoringOrchestrator(
        data_provider=data_provider,
        market_session_engine=market_session_engine or MarketSessionEngine(),
        state_repository=state_repository,
        notifier=notifier,
    )
    result = orchestrator.run(
        checked_at=checked_at,
        configs=configs,
        states=None if state_repository is not None else states,
    )

    output.write(render_monitoring_result(result))
    return CliRunOutcome(exit_code=0, monitoring_result=result)


def render_monitoring_result(result: MonitoringRunResult) -> str:
    """Render a monitoring result as stable human-readable CLI text."""
    lines = [
        "BIST IPO Ceiling Break Alert System",
        f"Checked at: {result.market_session.local_datetime.isoformat()}",
        f"Market status: {result.market_session.status.value}",
    ]

    if result.status == MonitoringRunStatus.MARKET_CLOSED:
        lines.append("Monitoring skipped because the market is closed.")
        lines.append(DISCLAIMER)
        return "\n".join(lines) + "\n"

    lines.append("Monitoring results:")
    for symbol_result in result.symbol_results:
        lines.extend(_render_symbol_result(symbol_result))

    if result.missing_symbols:
        lines.append(f"Missing quotes: {', '.join(result.missing_symbols)}")

    lines.append(DISCLAIMER)
    return "\n".join(lines) + "\n"


def _render_symbol_result(symbol_result: SymbolMonitoringResult) -> list[str]:
    if symbol_result.status == SymbolMonitoringStatus.MISSING_QUOTE:
        detail = symbol_result.error_message or "quote unavailable"
        return [f"- {symbol_result.symbol}: missing quote ({detail})"]

    tracking_result = symbol_result.tracking_result
    if tracking_result is None:
        return [f"- {symbol_result.symbol}: no tracking result"]

    signal = tracking_result.ceiling_signal
    status = "BREAK SIGNAL" if signal.should_alert else "ok"
    lines = [
        (
            f"- {symbol_result.symbol}: {status}; "
            f"price={signal.current_price}; ceiling={signal.theoretical_ceiling_price}; "
            f"gap={signal.ceiling_gap}; mode={tracking_result.monitoring_mode.value}; "
            f"ceiling_days={tracking_result.updated_state.consecutive_ceiling_days}"
        )
    ]
    if signal.should_alert:
        lines.append(f"  Break reason: {signal.reason.value}")
    if symbol_result.notification_sent:
        lines.append("  Notification: sent")
    if symbol_result.notification_error is not None:
        lines.append(f"  Notification error: {symbol_result.notification_error}")
    return lines


def _build_configs(symbols: tuple[str, ...]) -> tuple[IPOTrackingConfig, ...]:
    return tuple(IPOTrackingConfig(symbol=symbol) for symbol in symbols)


def _build_initial_states(
    configs: tuple[IPOTrackingConfig, ...],
) -> dict[str, IPOTrackingState]:
    return {config.symbol: IPOTrackingState(symbol=config.symbol) for config in configs}


def _current_time(now_provider: Callable[[], datetime] | None) -> datetime:
    if now_provider is not None:
        return now_provider()
    return datetime.now(DEFAULT_MARKET_TIMEZONE)
