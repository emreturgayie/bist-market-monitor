"""Tests for market calendar and session evaluation."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from tavan_takip.market import (
    DEFAULT_MARKET_TIMEZONE,
    MarketSessionEngine,
    MarketSessionStatus,
    TradingCalendar,
)


def test_weekday_during_market_hours_is_open() -> None:
    engine = MarketSessionEngine()

    session = engine.evaluate(datetime(2026, 1, 5, 14, 30, tzinfo=DEFAULT_MARKET_TIMEZONE))

    assert session.is_open is True
    assert session.status == MarketSessionStatus.OPEN
    assert session.trading_date == date(2026, 1, 5)


def test_before_market_open_is_closed() -> None:
    engine = MarketSessionEngine()

    session = engine.evaluate(datetime(2026, 1, 5, 9, 59, tzinfo=DEFAULT_MARKET_TIMEZONE))

    assert session.is_open is False
    assert session.status == MarketSessionStatus.BEFORE_OPEN


def test_after_market_close_is_closed() -> None:
    engine = MarketSessionEngine()

    session = engine.evaluate(datetime(2026, 1, 5, 18, 0, tzinfo=DEFAULT_MARKET_TIMEZONE))

    assert session.is_open is False
    assert session.status == MarketSessionStatus.AFTER_CLOSE


def test_weekend_is_closed() -> None:
    engine = MarketSessionEngine()

    session = engine.evaluate(datetime(2026, 1, 3, 12, 0, tzinfo=DEFAULT_MARKET_TIMEZONE))

    assert session.is_open is False
    assert session.status == MarketSessionStatus.WEEKEND


def test_configured_holiday_is_closed() -> None:
    calendar = TradingCalendar(holidays=frozenset((date(2026, 1, 5),)))
    engine = MarketSessionEngine(calendar)

    session = engine.evaluate(datetime(2026, 1, 5, 12, 0, tzinfo=DEFAULT_MARKET_TIMEZONE))

    assert session.is_open is False
    assert session.status == MarketSessionStatus.HOLIDAY


def test_timezone_aware_datetime_is_converted_to_market_timezone() -> None:
    engine = MarketSessionEngine()

    session = engine.evaluate(datetime(2026, 1, 5, 8, 0, tzinfo=UTC))

    assert session.local_datetime == datetime(2026, 1, 5, 11, 0, tzinfo=DEFAULT_MARKET_TIMEZONE)
    assert session.status == MarketSessionStatus.OPEN


def test_naive_datetime_is_rejected() -> None:
    engine = MarketSessionEngine()

    with pytest.raises(ValueError, match="timezone-aware"):
        engine.evaluate(datetime(2026, 1, 5, 12, 0))


def test_custom_open_close_time() -> None:
    calendar = TradingCalendar(
        market_open_time=time(hour=9, minute=30),
        market_close_time=time(hour=17, minute=30),
    )
    engine = MarketSessionEngine(calendar)

    before_custom_open = engine.evaluate(
        datetime(2026, 1, 5, 9, 15, tzinfo=DEFAULT_MARKET_TIMEZONE)
    )
    during_custom_session = engine.evaluate(
        datetime(2026, 1, 5, 9, 45, tzinfo=DEFAULT_MARKET_TIMEZONE)
    )
    at_custom_close = engine.evaluate(datetime(2026, 1, 5, 17, 30, tzinfo=DEFAULT_MARKET_TIMEZONE))

    assert before_custom_open.status == MarketSessionStatus.BEFORE_OPEN
    assert during_custom_session.status == MarketSessionStatus.OPEN
    assert at_custom_close.status == MarketSessionStatus.AFTER_CLOSE


def test_custom_timezone() -> None:
    london = ZoneInfo("Europe/London")
    calendar = TradingCalendar(
        timezone=london,
        market_open_time=time(hour=8),
        market_close_time=time(hour=16),
    )
    engine = MarketSessionEngine(calendar)

    session = engine.evaluate(datetime(2026, 1, 5, 9, 0, tzinfo=DEFAULT_MARKET_TIMEZONE))

    assert session.timezone is london
    assert session.local_datetime == datetime(2026, 1, 5, 6, 0, tzinfo=london)
    assert session.status == MarketSessionStatus.BEFORE_OPEN


def test_invalid_calendar_configuration() -> None:
    with pytest.raises(ValueError, match="before"):
        TradingCalendar(market_open_time=time(hour=18), market_close_time=time(hour=10))

    with pytest.raises(ValueError, match="timezone-naive"):
        TradingCalendar(market_open_time=time(hour=10, tzinfo=UTC))
