"""Tests for application-level monitoring orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from tavan_takip.application import (
    MonitoringOrchestrator,
    MonitoringRunStatus,
    SymbolMonitoringStatus,
)
from tavan_takip.data_providers import DataProvider, DataProviderNoDataError
from tavan_takip.domain import IPOTrackingConfig, IPOTrackingState, MarketQuote, MonitoringMode
from tavan_takip.market import DEFAULT_MARKET_TIMEZONE
from tavan_takip.notifications import NotificationMessage
from tavan_takip.persistence import SQLiteIPOTrackingStateRepository


class FakeDataProvider(DataProvider):
    """In-memory data provider used by orchestrator tests."""

    def __init__(self, quotes: dict[str, MarketQuote]) -> None:
        self._quotes = quotes
        self.requested_symbols: list[str] = []

    def get_quote(self, symbol: str) -> MarketQuote:
        self.requested_symbols.append(symbol)
        quote = self._quotes.get(symbol)
        if quote is None:
            raise DataProviderNoDataError(f"missing quote for {symbol}")
        return quote


class FakeNotifier:
    """Notifier fake used by orchestration tests."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.messages: list[NotificationMessage] = []

    def send(self, message: NotificationMessage) -> None:
        if self._error is not None:
            raise self._error
        self.messages.append(message)


def make_quote(
    *,
    symbol: str,
    price: str = "11.00",
    previous_close: str = "10.00",
    timestamp: datetime | None = None,
) -> MarketQuote:
    return MarketQuote.from_raw_values(
        symbol=symbol,
        price=price,
        previous_close=previous_close,
        open_price=previous_close,
        high_price=price,
        low_price=previous_close,
        volume=1_000,
        currency="TRY",
        timestamp=timestamp or datetime(2026, 1, 5, 10, 30, tzinfo=DEFAULT_MARKET_TIMEZONE),
    )


def test_market_closed_provider_not_called() -> None:
    provider = FakeDataProvider(quotes={"ORNEK.IS": make_quote(symbol="ORNEK.IS")})
    orchestrator = MonitoringOrchestrator(data_provider=provider)

    result = orchestrator.run(
        checked_at=datetime(2026, 1, 5, 9, 0, tzinfo=DEFAULT_MARKET_TIMEZONE),
        configs=[IPOTrackingConfig(symbol="ORNEK.IS")],
    )

    assert result.status == MonitoringRunStatus.MARKET_CLOSED
    assert result.market_session.is_open is False
    assert result.symbol_results == ()
    assert provider.requested_symbols == []


def test_market_open_provider_called() -> None:
    provider = FakeDataProvider(quotes={"ORNEK.IS": make_quote(symbol="ORNEK.IS")})
    orchestrator = MonitoringOrchestrator(data_provider=provider)

    result = orchestrator.run(
        checked_at=datetime(2026, 1, 5, 10, 30, tzinfo=DEFAULT_MARKET_TIMEZONE),
        configs=[IPOTrackingConfig(symbol="ORNEK.IS")],
    )

    assert result.status == MonitoringRunStatus.COMPLETED
    assert result.provider_was_used is True
    assert provider.requested_symbols == ["ORNEK.IS"]


def test_quote_processed_through_tracker() -> None:
    provider = FakeDataProvider(quotes={"ORNEK.IS": make_quote(symbol="ORNEK.IS")})
    orchestrator = MonitoringOrchestrator(data_provider=provider)

    result = orchestrator.run(
        checked_at=datetime(2026, 1, 5, 10, 30, tzinfo=DEFAULT_MARKET_TIMEZONE),
        configs=[IPOTrackingConfig(symbol="ORNEK.IS")],
    )

    symbol_result = result.symbol_results[0]
    assert symbol_result.status == SymbolMonitoringStatus.PROCESSED
    assert symbol_result.tracking_result is not None
    assert symbol_result.tracking_result.updated_state.consecutive_ceiling_days == 1
    assert symbol_result.tracking_result.monitoring_mode == MonitoringMode.EARLY


def test_missing_symbol_handled() -> None:
    provider = FakeDataProvider(quotes={})
    orchestrator = MonitoringOrchestrator(data_provider=provider)

    result = orchestrator.run(
        checked_at=datetime(2026, 1, 5, 10, 30, tzinfo=DEFAULT_MARKET_TIMEZONE),
        configs=[IPOTrackingConfig(symbol="ORNEK.IS")],
    )

    assert result.status == MonitoringRunStatus.COMPLETED
    assert result.missing_symbols == ("ORNEK.IS",)
    assert result.symbol_results[0].status == SymbolMonitoringStatus.MISSING_QUOTE
    assert result.symbol_results[0].tracking_result is None
    assert result.symbol_results[0].error_message == "missing quote for ORNEK.IS"


def test_multiple_symbols_handled() -> None:
    provider = FakeDataProvider(
        quotes={
            "ALFA.IS": make_quote(symbol="ALFA.IS"),
            "BRAVO.IS": make_quote(symbol="BRAVO.IS", price="10.95"),
        }
    )
    orchestrator = MonitoringOrchestrator(data_provider=provider)

    result = orchestrator.run(
        checked_at=datetime(2026, 1, 5, 10, 30, tzinfo=DEFAULT_MARKET_TIMEZONE),
        configs=[
            IPOTrackingConfig(symbol="ALFA.IS"),
            IPOTrackingConfig(symbol="BRAVO.IS"),
            IPOTrackingConfig(symbol="CHARLIE.IS"),
        ],
    )

    assert provider.requested_symbols == ["ALFA.IS", "BRAVO.IS", "CHARLIE.IS"]
    assert result.missing_symbols == ("CHARLIE.IS",)
    assert [symbol_result.status for symbol_result in result.symbol_results] == [
        SymbolMonitoringStatus.PROCESSED,
        SymbolMonitoringStatus.PROCESSED,
        SymbolMonitoringStatus.MISSING_QUOTE,
    ]
    bravo_result = result.symbol_results[1].tracking_result
    assert bravo_result is not None
    assert bravo_result.ceiling_signal.should_alert is True


def test_explicit_state_is_used_without_global_state() -> None:
    provider = FakeDataProvider(quotes={"ORNEK.IS": make_quote(symbol="ORNEK.IS")})
    orchestrator = MonitoringOrchestrator(data_provider=provider)
    existing_state = IPOTrackingState(
        symbol="ORNEK.IS",
        consecutive_ceiling_days=5,
        last_processed_trading_date=datetime(2026, 1, 2, tzinfo=UTC).date(),
    )

    result = orchestrator.run(
        checked_at=datetime(2026, 1, 5, 10, 30, tzinfo=DEFAULT_MARKET_TIMEZONE),
        configs=[IPOTrackingConfig(symbol="ORNEK.IS")],
        states={"ORNEK.IS": existing_state},
    )

    tracking_result = result.symbol_results[0].tracking_result
    assert tracking_result is not None
    assert tracking_result.previous_state == existing_state
    assert tracking_result.updated_state.consecutive_ceiling_days == 6


def test_no_network_access_is_required() -> None:
    provider = FakeDataProvider(quotes={"ORNEK.IS": make_quote(symbol="ORNEK.IS")})
    orchestrator = MonitoringOrchestrator(data_provider=provider)

    result = orchestrator.run(
        checked_at=datetime(2026, 1, 5, 10, 30, tzinfo=DEFAULT_MARKET_TIMEZONE),
        configs=[IPOTrackingConfig(symbol="ORNEK.IS", tolerance=Decimal("0.01"))],
    )

    assert result.status == MonitoringRunStatus.COMPLETED
    assert provider.requested_symbols == ["ORNEK.IS"]


def test_empty_configs_are_rejected() -> None:
    provider = FakeDataProvider(quotes={})
    orchestrator = MonitoringOrchestrator(data_provider=provider)

    with pytest.raises(ValueError, match="at least one"):
        orchestrator.run(
            checked_at=datetime(2026, 1, 5, 10, 30, tzinfo=DEFAULT_MARKET_TIMEZONE),
            configs=[],
        )


def test_duplicate_configs_are_rejected() -> None:
    provider = FakeDataProvider(quotes={})
    orchestrator = MonitoringOrchestrator(data_provider=provider)

    with pytest.raises(ValueError, match="duplicate"):
        orchestrator.run(
            checked_at=datetime(2026, 1, 5, 10, 30, tzinfo=DEFAULT_MARKET_TIMEZONE),
            configs=[IPOTrackingConfig(symbol="ORNEK.IS"), IPOTrackingConfig(symbol=" ornek.is ")],
        )


def test_invalid_state_mapping_is_rejected() -> None:
    provider = FakeDataProvider(quotes={"ORNEK.IS": make_quote(symbol="ORNEK.IS")})
    orchestrator = MonitoringOrchestrator(data_provider=provider)

    with pytest.raises(ValueError, match="state mapping key"):
        orchestrator.run(
            checked_at=datetime(2026, 1, 5, 10, 30, tzinfo=DEFAULT_MARKET_TIMEZONE),
            configs=[IPOTrackingConfig(symbol="ORNEK.IS")],
            states={"ORNEK.IS": IPOTrackingState(symbol="BASKA.IS")},
        )


def test_orchestrator_persists_updated_state_when_repository_is_injected(tmp_path: Path) -> None:
    repository = SQLiteIPOTrackingStateRepository(tmp_path / "tracking.sqlite3")
    provider = FakeDataProvider(quotes={"ORNEK.IS": make_quote(symbol="ORNEK.IS")})
    orchestrator = MonitoringOrchestrator(
        data_provider=provider,
        state_repository=repository,
    )

    result = orchestrator.run(
        checked_at=datetime(2026, 1, 5, 10, 30, tzinfo=DEFAULT_MARKET_TIMEZONE),
        configs=[IPOTrackingConfig(symbol="ORNEK.IS")],
    )

    tracking_result = result.symbol_results[0].tracking_result
    assert tracking_result is not None
    assert repository.load("ORNEK.IS") == tracking_result.updated_state


def test_orchestrator_sends_notification_on_break_signal() -> None:
    notifier = FakeNotifier()
    provider = FakeDataProvider(quotes={"ORNEK.IS": make_quote(symbol="ORNEK.IS", price="10.95")})
    orchestrator = MonitoringOrchestrator(data_provider=provider, notifier=notifier)

    result = orchestrator.run(
        checked_at=datetime(2026, 1, 5, 10, 30, tzinfo=DEFAULT_MARKET_TIMEZONE),
        configs=[IPOTrackingConfig(symbol="ORNEK.IS")],
    )

    assert len(notifier.messages) == 1
    assert notifier.messages[0].title == "Ceiling break alert: ORNEK.IS"
    assert "Current price: 10.95" in notifier.messages[0].body
    assert result.symbol_results[0].notification_sent is True
    assert result.symbol_results[0].notification_error is None


def test_orchestrator_does_not_notify_when_no_alert() -> None:
    notifier = FakeNotifier()
    provider = FakeDataProvider(quotes={"ORNEK.IS": make_quote(symbol="ORNEK.IS")})
    orchestrator = MonitoringOrchestrator(data_provider=provider, notifier=notifier)

    result = orchestrator.run(
        checked_at=datetime(2026, 1, 5, 10, 30, tzinfo=DEFAULT_MARKET_TIMEZONE),
        configs=[IPOTrackingConfig(symbol="ORNEK.IS")],
    )

    assert notifier.messages == []
    assert result.symbol_results[0].notification_sent is False
    assert result.symbol_results[0].notification_error is None


def test_orchestrator_does_not_notify_when_market_closed() -> None:
    notifier = FakeNotifier()
    provider = FakeDataProvider(quotes={"ORNEK.IS": make_quote(symbol="ORNEK.IS", price="10.95")})
    orchestrator = MonitoringOrchestrator(data_provider=provider, notifier=notifier)

    result = orchestrator.run(
        checked_at=datetime(2026, 1, 5, 9, 0, tzinfo=DEFAULT_MARKET_TIMEZONE),
        configs=[IPOTrackingConfig(symbol="ORNEK.IS")],
    )

    assert result.symbol_results == ()
    assert notifier.messages == []


def test_orchestrator_surfaces_notification_failure_without_crashing() -> None:
    notifier = FakeNotifier(error=RuntimeError("telegram unavailable"))
    provider = FakeDataProvider(quotes={"ORNEK.IS": make_quote(symbol="ORNEK.IS", price="10.95")})
    orchestrator = MonitoringOrchestrator(data_provider=provider, notifier=notifier)

    result = orchestrator.run(
        checked_at=datetime(2026, 1, 5, 10, 30, tzinfo=DEFAULT_MARKET_TIMEZONE),
        configs=[IPOTrackingConfig(symbol="ORNEK.IS")],
    )

    assert result.symbol_results[0].notification_sent is False
    assert result.symbol_results[0].notification_error == "telegram unavailable"
