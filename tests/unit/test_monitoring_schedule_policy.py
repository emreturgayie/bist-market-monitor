"""Tests for adaptive monitoring schedule policy."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from tavan_takip.domain import IPOTrackingState
from tavan_takip.market import DEFAULT_MARKET_TIMEZONE, TradingCalendar
from tavan_takip.scheduler import (
    MonitoringSchedulePolicy,
    ScheduleDecisionReason,
    ScheduleMode,
)


def early_state() -> IPOTrackingState:
    return IPOTrackingState(symbol="ORNEK.IS", consecutive_ceiling_days=5)


def hourly_state() -> IPOTrackingState:
    return IPOTrackingState(symbol="ORNEK.IS", consecutive_ceiling_days=6)


def local_datetime(hour: int, minute: int = 0, *, day: int = 5) -> datetime:
    return datetime(2026, 1, day, hour, minute, tzinfo=DEFAULT_MARKET_TIMEZONE)


def test_early_mode_before_first_window() -> None:
    policy = MonitoringSchedulePolicy()

    decision = policy.decide(
        state=early_state(),
        checked_at=local_datetime(10, 5),
    )

    assert decision.schedule_mode == ScheduleMode.EARLY
    assert decision.reason == ScheduleDecisionReason.WAITING_FOR_NEXT_WINDOW
    assert decision.should_run_now is False
    assert decision.next_run_at == local_datetime(10, 15)


def test_early_mode_between_windows_is_due_once() -> None:
    policy = MonitoringSchedulePolicy()

    first_decision = policy.decide(
        state=early_state(),
        checked_at=local_datetime(11, 0),
    )
    second_decision = policy.decide(
        state=early_state(),
        checked_at=local_datetime(11, 5),
        last_run_at=local_datetime(11, 0),
    )

    assert first_decision.reason == ScheduleDecisionReason.DUE_IN_CURRENT_WINDOW
    assert first_decision.should_run_now is True
    assert first_decision.next_run_at == local_datetime(11, 0)
    assert second_decision.reason == ScheduleDecisionReason.ALREADY_RAN_IN_WINDOW
    assert second_decision.should_run_now is False
    assert second_decision.next_run_at == local_datetime(12, 30)


def test_early_mode_after_last_window_moves_to_next_trading_day_after_run() -> None:
    policy = MonitoringSchedulePolicy()

    decision = policy.decide(
        state=early_state(),
        checked_at=local_datetime(17, 45),
        last_run_at=local_datetime(17, 20),
    )

    assert decision.reason == ScheduleDecisionReason.ALREADY_RAN_IN_WINDOW
    assert decision.should_run_now is False
    assert decision.next_run_at == datetime(2026, 1, 6, 10, 15, tzinfo=DEFAULT_MARKET_TIMEZONE)


def test_hourly_mode_during_market_hours() -> None:
    policy = MonitoringSchedulePolicy()

    first_decision = policy.decide(
        state=hourly_state(),
        checked_at=local_datetime(14, 20),
    )
    second_decision = policy.decide(
        state=hourly_state(),
        checked_at=local_datetime(14, 30),
        last_run_at=local_datetime(14, 20),
    )

    assert first_decision.schedule_mode == ScheduleMode.HOURLY
    assert first_decision.reason == ScheduleDecisionReason.DUE_IN_CURRENT_WINDOW
    assert first_decision.should_run_now is True
    assert second_decision.reason == ScheduleDecisionReason.ALREADY_RAN_IN_WINDOW
    assert second_decision.next_run_at == local_datetime(15, 0)


def test_market_closed_before_open() -> None:
    policy = MonitoringSchedulePolicy()

    decision = policy.decide(
        state=early_state(),
        checked_at=local_datetime(9, 30),
    )

    assert decision.reason == ScheduleDecisionReason.MARKET_BEFORE_OPEN
    assert decision.should_run_now is False
    assert decision.next_run_at == local_datetime(10, 15)


def test_market_closed_after_close() -> None:
    policy = MonitoringSchedulePolicy()

    decision = policy.decide(
        state=hourly_state(),
        checked_at=local_datetime(18, 0),
    )

    assert decision.reason == ScheduleDecisionReason.MARKET_AFTER_CLOSE
    assert decision.should_run_now is False
    assert decision.next_run_at == datetime(2026, 1, 6, 10, 0, tzinfo=DEFAULT_MARKET_TIMEZONE)


def test_weekend_behavior() -> None:
    policy = MonitoringSchedulePolicy()

    decision = policy.decide(
        state=early_state(),
        checked_at=datetime(2026, 1, 3, 12, 0, tzinfo=DEFAULT_MARKET_TIMEZONE),
    )

    assert decision.reason == ScheduleDecisionReason.MARKET_WEEKEND
    assert decision.next_run_at == datetime(2026, 1, 5, 10, 15, tzinfo=DEFAULT_MARKET_TIMEZONE)


def test_holiday_behavior() -> None:
    calendar = TradingCalendar(holidays=frozenset((date(2026, 1, 5),)))
    policy = MonitoringSchedulePolicy(calendar=calendar)

    decision = policy.decide(
        state=early_state(),
        checked_at=local_datetime(12, 0),
    )

    assert decision.reason == ScheduleDecisionReason.MARKET_HOLIDAY
    assert decision.next_run_at == datetime(2026, 1, 6, 10, 15, tzinfo=DEFAULT_MARKET_TIMEZONE)


def test_timezone_aware_handling() -> None:
    policy = MonitoringSchedulePolicy()

    decision = policy.decide(
        state=hourly_state(),
        checked_at=datetime(2026, 1, 5, 11, 30, tzinfo=UTC),
    )

    assert decision.checked_at == datetime(2026, 1, 5, 14, 30, tzinfo=DEFAULT_MARKET_TIMEZONE)
    assert decision.next_run_at == datetime(2026, 1, 5, 14, 30, tzinfo=DEFAULT_MARKET_TIMEZONE)
    assert decision.should_run_now is True


def test_custom_timezone_and_check_windows() -> None:
    london = ZoneInfo("Europe/London")
    calendar = TradingCalendar(
        timezone=london,
        market_open_time=time(hour=8),
        market_close_time=time(hour=16),
    )
    policy = MonitoringSchedulePolicy(
        calendar=calendar,
        early_check_times=(time(hour=8, minute=30), time(hour=11), time(hour=15)),
    )

    decision = policy.decide(
        state=early_state(),
        checked_at=datetime(2026, 1, 5, 7, 15, tzinfo=UTC),
    )

    assert decision.checked_at == datetime(2026, 1, 5, 7, 15, tzinfo=london)
    assert decision.next_run_at == datetime(2026, 1, 5, 8, 30, tzinfo=london)


def test_naive_datetime_is_rejected() -> None:
    policy = MonitoringSchedulePolicy()

    with pytest.raises(ValueError, match="timezone-aware"):
        policy.decide(
            state=early_state(),
            checked_at=datetime(2026, 1, 5, 10, 30),
        )


@pytest.mark.parametrize(
    "check_times",
    [
        (time(hour=10), time(hour=12)),
        (time(hour=10), time(hour=12), time(hour=12)),
        (time(hour=9), time(hour=12), time(hour=15)),
        (time(hour=10, tzinfo=UTC), time(hour=12), time(hour=15)),
    ],
)
def test_invalid_early_check_windows(check_times: tuple[time, ...]) -> None:
    with pytest.raises(ValueError):
        MonitoringSchedulePolicy(early_check_times=check_times)
