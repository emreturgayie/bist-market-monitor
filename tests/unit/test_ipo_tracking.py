"""Tests for the domain-level IPO tracking engine."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tavan_takip.domain import (
    IPOTracker,
    IPOTrackingConfig,
    IPOTrackingLifecycleState,
    IPOTrackingState,
    MarketQuote,
    MonitoringMode,
)


def make_quote(
    *,
    symbol: str = "ORNEK.IS",
    price: str = "11.00",
    previous_close: str = "10.00",
    timestamp: datetime,
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
        timestamp=timestamp,
    )


def test_first_ceiling_day_counted() -> None:
    tracker = IPOTracker()
    config = IPOTrackingConfig(symbol="ORNEK.IS")
    quote = make_quote(timestamp=datetime(2026, 1, 2, 10, 30, tzinfo=UTC))

    result = tracker.track(quote=quote, config=config)

    assert result.new_ceiling_day_counted is True
    assert result.updated_state.consecutive_ceiling_days == 1
    assert result.updated_state.last_processed_trading_date == quote.timestamp.date()
    assert result.monitoring_mode == MonitoringMode.EARLY
    assert result.lifecycle_state == IPOTrackingLifecycleState.MONITORING


def test_same_day_not_double_counted() -> None:
    tracker = IPOTracker()
    config = IPOTrackingConfig(symbol="ORNEK.IS")
    state = IPOTrackingState(
        symbol="ORNEK.IS",
        consecutive_ceiling_days=1,
        last_processed_trading_date=datetime(2026, 1, 2, tzinfo=UTC).date(),
    )
    quote = make_quote(timestamp=datetime(2026, 1, 2, 15, 30, tzinfo=UTC))

    result = tracker.track(quote=quote, config=config, state=state)

    assert result.new_ceiling_day_counted is False
    assert result.updated_state.consecutive_ceiling_days == 1
    assert result.updated_state.last_processed_trading_date == quote.timestamp.date()


def test_consecutive_ceiling_days_increment_correctly() -> None:
    tracker = IPOTracker()
    config = IPOTrackingConfig(symbol="ORNEK.IS")
    state = IPOTrackingState(
        symbol="ORNEK.IS",
        consecutive_ceiling_days=2,
        last_processed_trading_date=datetime(2026, 1, 2, tzinfo=UTC).date(),
    )
    quote = make_quote(timestamp=datetime(2026, 1, 5, 10, 30, tzinfo=UTC))

    result = tracker.track(quote=quote, config=config, state=state)

    assert result.new_ceiling_day_counted is True
    assert result.updated_state.consecutive_ceiling_days == 3
    assert result.monitoring_mode == MonitoringMode.EARLY


def test_switching_to_hourly_mode_after_five_ceiling_days() -> None:
    tracker = IPOTracker()
    config = IPOTrackingConfig(symbol="ORNEK.IS")
    state = IPOTrackingState(
        symbol="ORNEK.IS",
        consecutive_ceiling_days=5,
        last_processed_trading_date=datetime(2026, 1, 8, tzinfo=UTC).date(),
    )
    quote = make_quote(timestamp=datetime(2026, 1, 9, 10, 30, tzinfo=UTC))

    result = tracker.track(quote=quote, config=config, state=state)

    assert result.updated_state.consecutive_ceiling_days == 6
    assert result.monitoring_mode == MonitoringMode.HOURLY


def test_five_ceiling_days_still_use_early_mode() -> None:
    state = IPOTrackingState(symbol="ORNEK.IS", consecutive_ceiling_days=5)

    assert state.monitoring_mode == MonitoringMode.EARLY


def test_break_signal_stops_ceiling_streak() -> None:
    tracker = IPOTracker()
    config = IPOTrackingConfig(symbol="ORNEK.IS")
    state = IPOTrackingState(
        symbol="ORNEK.IS",
        consecutive_ceiling_days=4,
        last_processed_trading_date=datetime(2026, 1, 8, tzinfo=UTC).date(),
    )
    quote = make_quote(price="10.95", timestamp=datetime(2026, 1, 9, 10, 30, tzinfo=UTC))

    result = tracker.track(quote=quote, config=config, state=state)

    assert result.ceiling_signal.should_alert is True
    assert result.ceiling_streak_reset is True
    assert result.updated_state.consecutive_ceiling_days == 0
    assert result.lifecycle_state == IPOTrackingLifecycleState.CEILING_BROKEN
    assert result.monitoring_mode == MonitoringMode.EARLY


def test_noise_filtered_signal_does_not_stop_ceiling_streak() -> None:
    tracker = IPOTracker()
    config = IPOTrackingConfig(symbol="ORNEK.IS", price_tick=Decimal("0.01"))
    state = IPOTrackingState(
        symbol="ORNEK.IS",
        consecutive_ceiling_days=3,
        last_processed_trading_date=datetime(2026, 1, 8, tzinfo=UTC).date(),
    )
    quote = make_quote(price="10.99", timestamp=datetime(2026, 1, 9, 10, 30, tzinfo=UTC))

    result = tracker.track(quote=quote, config=config, state=state)

    assert result.ceiling_signal.should_alert is False
    assert result.new_ceiling_day_counted is False
    assert result.ceiling_streak_reset is False
    assert result.updated_state.consecutive_ceiling_days == 3
    assert result.lifecycle_state == IPOTrackingLifecycleState.MONITORING


def test_tracking_works_without_persistence() -> None:
    tracker = IPOTracker()
    config = IPOTrackingConfig(symbol="ORNEK.IS")

    first_result = tracker.track(
        quote=make_quote(timestamp=datetime(2026, 1, 2, 10, 30, tzinfo=UTC)),
        config=config,
    )
    second_result = tracker.track(
        quote=make_quote(timestamp=datetime(2026, 1, 5, 10, 30, tzinfo=UTC)),
        config=config,
        state=first_result.updated_state,
    )

    assert first_result.updated_state.consecutive_ceiling_days == 1
    assert second_result.updated_state.consecutive_ceiling_days == 2


@pytest.mark.parametrize(
    "state_factory",
    [
        lambda: IPOTrackingState(symbol=""),
        lambda: IPOTrackingState(symbol="ORNEK.IS", consecutive_ceiling_days=-1),
        lambda: IPOTrackingState(
            symbol="ORNEK.IS",
            consecutive_ceiling_days=1,
            lifecycle_state=IPOTrackingLifecycleState.CEILING_BROKEN,
        ),
    ],
)
def test_invalid_state_edge_cases(state_factory: Callable[[], IPOTrackingState]) -> None:
    with pytest.raises(ValueError):
        state_factory()


def test_tracker_rejects_state_config_symbol_mismatch() -> None:
    tracker = IPOTracker()
    config = IPOTrackingConfig(symbol="ORNEK.IS")
    state = IPOTrackingState(symbol="BASKA.IS")
    quote = make_quote(timestamp=datetime(2026, 1, 2, 10, 30, tzinfo=UTC))

    with pytest.raises(ValueError, match="state symbol"):
        tracker.track(quote=quote, config=config, state=state)


def test_tracker_rejects_quote_config_symbol_mismatch() -> None:
    tracker = IPOTracker()
    config = IPOTrackingConfig(symbol="ORNEK.IS")
    quote = make_quote(symbol="BASKA.IS", timestamp=datetime(2026, 1, 2, 10, 30, tzinfo=UTC))

    with pytest.raises(ValueError, match="quote symbol"):
        tracker.track(quote=quote, config=config)
