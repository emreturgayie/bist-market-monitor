"""Application-level monitoring orchestration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from tavan_takip.data_providers import DataProvider, DataProviderNoDataError
from tavan_takip.domain import IPOTracker, IPOTrackingConfig, IPOTrackingResult, IPOTrackingState
from tavan_takip.market import MarketSession, MarketSessionEngine
from tavan_takip.persistence import IPOTrackingStateRepository


class MonitoringRunStatus(StrEnum):
    """Overall status for one monitoring run."""

    MARKET_CLOSED = "market_closed"
    COMPLETED = "completed"


class SymbolMonitoringStatus(StrEnum):
    """Status for one symbol processed during a monitoring run."""

    PROCESSED = "processed"
    MISSING_QUOTE = "missing_quote"


@dataclass(frozen=True, slots=True)
class SymbolMonitoringResult:
    """Structured result for one configured IPO symbol."""

    symbol: str
    status: SymbolMonitoringStatus
    tracking_result: IPOTrackingResult | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class MonitoringRunResult:
    """Structured result for one monitoring orchestrator run."""

    status: MonitoringRunStatus
    market_session: MarketSession
    symbol_results: tuple[SymbolMonitoringResult, ...]
    missing_symbols: tuple[str, ...]

    @property
    def provider_was_used(self) -> bool:
        """Return whether the run attempted to fetch market quotes."""
        return self.status == MonitoringRunStatus.COMPLETED


class MonitoringOrchestrator:
    """Coordinate market-session checks, quote retrieval, and IPO tracking."""

    def __init__(
        self,
        *,
        data_provider: DataProvider,
        market_session_engine: MarketSessionEngine | None = None,
        tracker: IPOTracker | None = None,
        state_repository: IPOTrackingStateRepository | None = None,
    ) -> None:
        self._data_provider = data_provider
        self._market_session_engine = market_session_engine or MarketSessionEngine()
        self._tracker = tracker or IPOTracker()
        self._state_repository = state_repository

    def run(
        self,
        *,
        checked_at: datetime,
        configs: Sequence[IPOTrackingConfig],
        states: Mapping[str, IPOTrackingState] | None = None,
    ) -> MonitoringRunResult:
        """Execute one monitoring run for the configured IPO symbols."""
        normalized_configs = _validate_configs(configs)
        market_session = self._market_session_engine.evaluate(checked_at)

        if not market_session.is_open:
            return MonitoringRunResult(
                status=MonitoringRunStatus.MARKET_CLOSED,
                market_session=market_session,
                symbol_results=(),
                missing_symbols=(),
            )

        normalized_states = self._resolve_states(configs=normalized_configs, states=states)
        symbol_results: list[SymbolMonitoringResult] = []
        missing_symbols: list[str] = []
        for config in normalized_configs:
            result = self._monitor_symbol(config=config, states=normalized_states)
            symbol_results.append(result)
            if result.status == SymbolMonitoringStatus.MISSING_QUOTE:
                missing_symbols.append(result.symbol)
            elif result.tracking_result is not None and self._state_repository is not None:
                self._state_repository.save(result.tracking_result.updated_state)

        return MonitoringRunResult(
            status=MonitoringRunStatus.COMPLETED,
            market_session=market_session,
            symbol_results=tuple(symbol_results),
            missing_symbols=tuple(missing_symbols),
        )

    def _monitor_symbol(
        self,
        *,
        config: IPOTrackingConfig,
        states: Mapping[str, IPOTrackingState],
    ) -> SymbolMonitoringResult:
        try:
            quote = self._data_provider.get_quote(config.symbol)
        except DataProviderNoDataError as exc:
            return SymbolMonitoringResult(
                symbol=config.symbol,
                status=SymbolMonitoringStatus.MISSING_QUOTE,
                error_message=str(exc),
            )

        tracking_result = self._tracker.track(
            quote=quote,
            config=config,
            state=states.get(config.symbol),
        )
        return SymbolMonitoringResult(
            symbol=config.symbol,
            status=SymbolMonitoringStatus.PROCESSED,
            tracking_result=tracking_result,
        )

    def _resolve_states(
        self,
        *,
        configs: tuple[IPOTrackingConfig, ...],
        states: Mapping[str, IPOTrackingState] | None,
    ) -> dict[str, IPOTrackingState]:
        if states is not None:
            return _normalize_states(states)
        if self._state_repository is None:
            return {}
        return {
            config.symbol: self._state_repository.get_or_create(config.symbol) for config in configs
        }


def _validate_configs(configs: Sequence[IPOTrackingConfig]) -> tuple[IPOTrackingConfig, ...]:
    if not configs:
        raise ValueError("at least one IPO tracking config is required")

    normalized_configs = tuple(configs)
    seen_symbols: set[str] = set()
    for config in normalized_configs:
        if config.symbol in seen_symbols:
            raise ValueError(f"duplicate IPO tracking config symbol: {config.symbol}")
        seen_symbols.add(config.symbol)
    return normalized_configs


def _normalize_states(
    states: Mapping[str, IPOTrackingState],
) -> dict[str, IPOTrackingState]:
    normalized_states: dict[str, IPOTrackingState] = {}
    for symbol, state in states.items():
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("state symbol key must not be blank")
        if normalized_symbol != state.symbol:
            raise ValueError("state mapping key must match IPO tracking state symbol")
        normalized_states[normalized_symbol] = state
    return normalized_states
