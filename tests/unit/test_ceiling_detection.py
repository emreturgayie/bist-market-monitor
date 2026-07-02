"""Tests for IPO ceiling calculation and ceiling-break detection."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tavan_takip.domain import (
    CeilingBreakDetector,
    CeilingCalculator,
    CeilingSignalReason,
    CeilingStatus,
    IPOTrackingConfig,
    MarketQuote,
    SignalSeverity,
)

QUOTE_TIME = datetime(2026, 1, 2, 10, 30, tzinfo=UTC)


def make_quote(
    *,
    symbol: str = "ORNEK.IS",
    price: str,
    previous_close: str = "10.00",
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
        timestamp=QUOTE_TIME,
    )


def test_normal_ceiling_intact() -> None:
    detector = CeilingBreakDetector()
    quote = make_quote(price="11.00")
    config = IPOTrackingConfig(symbol="ORNEK.IS")

    signal = detector.detect(quote, config)

    assert signal.status == CeilingStatus.AT_CEILING
    assert signal.severity == SignalSeverity.NONE
    assert signal.reason == CeilingSignalReason.CEILING_INTACT
    assert signal.theoretical_ceiling_price == Decimal("11.00")
    assert signal.ceiling_gap == Decimal("0")
    assert signal.is_at_ceiling is True
    assert signal.is_below_ceiling is False
    assert signal.should_alert is False


def test_price_below_ceiling_emits_break_signal() -> None:
    detector = CeilingBreakDetector()
    quote = make_quote(price="10.95")
    config = IPOTrackingConfig(symbol="ORNEK.IS")

    signal = detector.detect(quote, config)

    assert signal.status == CeilingStatus.BROKEN
    assert signal.severity == SignalSeverity.HIGH
    assert signal.reason == CeilingSignalReason.CEILING_BREAK
    assert signal.ceiling_gap == Decimal("0.05")
    assert signal.is_at_ceiling is False
    assert signal.is_below_ceiling is True
    assert signal.should_alert is True


def test_tolerance_prevents_false_positive() -> None:
    detector = CeilingBreakDetector()
    quote = make_quote(price="10.98")
    config = IPOTrackingConfig(symbol="ORNEK.IS", tolerance=Decimal("0.02"))

    signal = detector.detect(quote, config)

    assert signal.status == CeilingStatus.AT_CEILING
    assert signal.reason == CeilingSignalReason.FILTERED_BY_TOLERANCE
    assert signal.ceiling_gap == Decimal("0.02")
    assert signal.should_alert is False


def test_one_tick_difference_is_filtered_by_default() -> None:
    detector = CeilingBreakDetector()
    quote = make_quote(price="10.99")
    config = IPOTrackingConfig(symbol="ORNEK.IS", price_tick=Decimal("0.01"))

    signal = detector.detect(quote, config)

    assert signal.status == CeilingStatus.BELOW_CEILING
    assert signal.reason == CeilingSignalReason.FILTERED_BY_SINGLE_TICK
    assert signal.severity == SignalSeverity.LOW
    assert signal.should_alert is False


def test_one_tick_difference_can_be_configured_to_alert() -> None:
    detector = CeilingBreakDetector()
    quote = make_quote(price="10.99")
    config = IPOTrackingConfig(
        symbol="ORNEK.IS",
        price_tick=Decimal("0.01"),
        ignore_single_tick_difference=False,
    )

    signal = detector.detect(quote, config)

    assert signal.status == CeilingStatus.BROKEN
    assert signal.reason == CeilingSignalReason.CEILING_BREAK
    assert signal.should_alert is True


def test_configurable_daily_limit() -> None:
    calculator = CeilingCalculator()

    ceiling_price = calculator.calculate(
        base_price=Decimal("20.00"),
        daily_limit_percent=Decimal("5"),
        price_tick=Decimal("0.01"),
    )

    assert ceiling_price == Decimal("21.00")


def test_decimal_precision_rounds_down_to_configured_tick() -> None:
    calculator = CeilingCalculator()

    ceiling_price = calculator.calculate(
        base_price=Decimal("10.07"),
        daily_limit_percent=Decimal("10"),
        price_tick=Decimal("0.01"),
    )

    assert ceiling_price == Decimal("11.07")


@pytest.mark.parametrize(
    "config_factory",
    [
        lambda: IPOTrackingConfig(symbol=""),
        lambda: IPOTrackingConfig(symbol="ORNEK.IS", ipo_price=Decimal("0")),
        lambda: IPOTrackingConfig(symbol="ORNEK.IS", daily_limit_percent=Decimal("0")),
        lambda: IPOTrackingConfig(symbol="ORNEK.IS", price_tick=Decimal("0")),
        lambda: IPOTrackingConfig(symbol="ORNEK.IS", tolerance=Decimal("-0.01")),
    ],
)
def test_invalid_ipo_config(config_factory: Callable[[], IPOTrackingConfig]) -> None:
    with pytest.raises(ValueError):
        config_factory()


def test_detector_rejects_symbol_mismatch() -> None:
    detector = CeilingBreakDetector()
    quote = make_quote(symbol="AAA.IS", price="11.00")
    config = IPOTrackingConfig(symbol="BBB.IS")

    with pytest.raises(ValueError, match="symbol"):
        detector.detect(quote, config)


@pytest.mark.parametrize(
    (
        "symbol",
        "base_price",
        "last_price",
        "daily_limit_percent",
        "price_tick",
        "expected_ceiling",
        "expected_status",
        "should_alert",
    ),
    [
        (
            "ALFA.IS",
            "20.00",
            "22.00",
            "10",
            "0.01",
            Decimal("22.00"),
            CeilingStatus.AT_CEILING,
            False,
        ),
        (
            "BRAVO.IS",
            "9.30",
            "10.20",
            "10",
            "0.01",
            Decimal("10.23"),
            CeilingStatus.BROKEN,
            True,
        ),
        (
            "DELTA.IS",
            "13.50",
            "14.16",
            "5",
            "0.01",
            Decimal("14.17"),
            CeilingStatus.BELOW_CEILING,
            False,
        ),
        (
            "EGEEN.IS",
            "47.25",
            "51.95",
            "10",
            "0.05",
            Decimal("51.95"),
            CeilingStatus.AT_CEILING,
            False,
        ),
    ],
)
def test_multiple_realistic_bist_like_examples(
    *,
    symbol: str,
    base_price: str,
    last_price: str,
    daily_limit_percent: str,
    price_tick: str,
    expected_ceiling: Decimal,
    expected_status: CeilingStatus,
    should_alert: bool,
) -> None:
    detector = CeilingBreakDetector()
    quote = make_quote(symbol=symbol, price=last_price, previous_close=base_price)
    config = IPOTrackingConfig(
        symbol=symbol,
        daily_limit_percent=Decimal(daily_limit_percent),
        price_tick=Decimal(price_tick),
    )

    signal = detector.detect(quote, config)

    assert signal.theoretical_ceiling_price == expected_ceiling
    assert signal.status == expected_status
    assert signal.should_alert is should_alert


def test_ipo_price_can_be_used_instead_of_previous_close() -> None:
    detector = CeilingBreakDetector()
    quote = make_quote(price="16.50", previous_close="14.00")
    config = IPOTrackingConfig(symbol="ORNEK.IS", ipo_price=Decimal("15.00"))

    signal = detector.detect(quote, config)

    assert signal.theoretical_ceiling_price == Decimal("16.50")
    assert signal.status == CeilingStatus.AT_CEILING


def test_betae_limit_up_close_is_not_reported_as_ceiling_break() -> None:
    detector = CeilingBreakDetector()
    quote = make_quote(symbol="BETAE.IS", price="48.400002", previous_close="44.00")
    config = IPOTrackingConfig(symbol="BETAE.IS")

    signal = detector.detect(quote, config)

    assert signal.theoretical_ceiling_price == Decimal("48.40")
    assert signal.status == CeilingStatus.AT_CEILING
    assert signal.reason == CeilingSignalReason.CEILING_INTACT
    assert signal.should_alert is False
