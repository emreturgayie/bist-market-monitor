"""Pure scheduling policy for adaptive IPO monitoring."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum

from tavan_takip.domain import IPOTrackingState, MonitoringMode
from tavan_takip.market import TradingCalendar

DEFAULT_EARLY_CHECK_TIMES = (
    time(hour=10, minute=15),
    time(hour=12, minute=30),
    time(hour=15, minute=0),
    time(hour=17, minute=15),
)


class ScheduleMode(StrEnum):
    """Schedule mode selected for the next monitoring decision."""

    EARLY = "early"
    HOURLY = "hourly"


class ScheduleDecisionReason(StrEnum):
    """Machine-readable reason for a scheduling decision."""

    DUE_IN_CURRENT_WINDOW = "due_in_current_window"
    WAITING_FOR_NEXT_WINDOW = "waiting_for_next_window"
    ALREADY_RAN_IN_WINDOW = "already_ran_in_window"
    MARKET_BEFORE_OPEN = "market_before_open"
    MARKET_AFTER_CLOSE = "market_after_close"
    MARKET_WEEKEND = "market_weekend"
    MARKET_HOLIDAY = "market_holiday"


@dataclass(frozen=True, slots=True)
class NextRunDecision:
    """Structured decision for the next monitoring run."""

    symbol: str
    schedule_mode: ScheduleMode
    reason: ScheduleDecisionReason
    checked_at: datetime
    next_run_at: datetime
    should_run_now: bool


class MonitoringSchedulePolicy:
    """Decide when a tracked IPO should be checked next."""

    def __init__(
        self,
        *,
        calendar: TradingCalendar | None = None,
        early_check_times: Sequence[time] = DEFAULT_EARLY_CHECK_TIMES,
    ) -> None:
        self._calendar = calendar or TradingCalendar()
        self._early_check_times = _validate_early_check_times(
            tuple(early_check_times),
            self._calendar,
        )

    def decide(
        self,
        *,
        state: IPOTrackingState,
        checked_at: datetime,
        last_run_at: datetime | None = None,
    ) -> NextRunDecision:
        """Return when the symbol should be monitored next."""
        local_checked_at = self._calendar.localize(checked_at)
        local_last_run_at = (
            self._calendar.localize(last_run_at) if last_run_at is not None else None
        )
        schedule_mode = _schedule_mode_from_monitoring_mode(state.monitoring_mode)

        closed_reason = self._closed_reason(local_checked_at)
        if closed_reason is not None:
            return NextRunDecision(
                symbol=state.symbol,
                schedule_mode=schedule_mode,
                reason=closed_reason,
                checked_at=local_checked_at,
                next_run_at=self._next_scheduled_time_when_closed(
                    schedule_mode,
                    local_checked_at,
                ),
                should_run_now=False,
            )

        if state.monitoring_mode == MonitoringMode.EARLY:
            windows = _combine_windows(
                local_checked_at.date(),
                self._early_check_times,
                self._calendar,
            )
        else:
            windows = self._hourly_windows(local_checked_at.date())

        return self._decide_for_windows(
            state=state,
            schedule_mode=schedule_mode,
            checked_at=local_checked_at,
            last_run_at=local_last_run_at,
            windows=windows,
        )

    def _decide_for_windows(
        self,
        *,
        state: IPOTrackingState,
        schedule_mode: ScheduleMode,
        checked_at: datetime,
        last_run_at: datetime | None,
        windows: tuple[datetime, ...],
    ) -> NextRunDecision:
        previous_windows = tuple(window for window in windows if window <= checked_at)
        if not previous_windows:
            return NextRunDecision(
                symbol=state.symbol,
                schedule_mode=schedule_mode,
                reason=ScheduleDecisionReason.WAITING_FOR_NEXT_WINDOW,
                checked_at=checked_at,
                next_run_at=windows[0],
                should_run_now=False,
            )

        current_window = previous_windows[-1]
        next_window = _next_window_after(windows, current_window)
        if _already_ran_in_window(last_run_at=last_run_at, window_start=current_window):
            return NextRunDecision(
                symbol=state.symbol,
                schedule_mode=schedule_mode,
                reason=ScheduleDecisionReason.ALREADY_RAN_IN_WINDOW,
                checked_at=checked_at,
                next_run_at=next_window
                or self._first_window_next_trading_day(schedule_mode, checked_at),
                should_run_now=False,
            )

        return NextRunDecision(
            symbol=state.symbol,
            schedule_mode=schedule_mode,
            reason=ScheduleDecisionReason.DUE_IN_CURRENT_WINDOW,
            checked_at=checked_at,
            next_run_at=checked_at,
            should_run_now=True,
        )

    def _closed_reason(self, local_checked_at: datetime) -> ScheduleDecisionReason | None:
        checked_date = local_checked_at.date()
        if self._calendar.is_weekend(checked_date):
            return ScheduleDecisionReason.MARKET_WEEKEND
        if self._calendar.is_holiday(checked_date):
            return ScheduleDecisionReason.MARKET_HOLIDAY
        if local_checked_at.time() < self._calendar.market_open_time:
            return ScheduleDecisionReason.MARKET_BEFORE_OPEN
        if local_checked_at.time() >= self._calendar.market_close_time:
            return ScheduleDecisionReason.MARKET_AFTER_CLOSE
        return None

    def _next_market_open(self, local_checked_at: datetime) -> datetime:
        candidate_date = local_checked_at.date()
        if local_checked_at.time() >= self._calendar.market_close_time:
            candidate_date += timedelta(days=1)

        while self._calendar.is_weekend(candidate_date) or self._calendar.is_holiday(
            candidate_date
        ):
            candidate_date += timedelta(days=1)

        return _aware_datetime(candidate_date, self._calendar.market_open_time, self._calendar)

    def _next_scheduled_time_when_closed(
        self,
        schedule_mode: ScheduleMode,
        local_checked_at: datetime,
    ) -> datetime:
        next_open = self._next_market_open(local_checked_at)
        if schedule_mode == ScheduleMode.EARLY:
            return _aware_datetime(next_open.date(), self._early_check_times[0], self._calendar)
        return next_open

    def _first_window_next_trading_day(
        self,
        schedule_mode: ScheduleMode,
        local_checked_at: datetime,
    ) -> datetime:
        next_trading_date = self._next_trading_date_after(local_checked_at.date())
        if schedule_mode == ScheduleMode.EARLY:
            return _aware_datetime(next_trading_date, self._early_check_times[0], self._calendar)
        return _aware_datetime(next_trading_date, self._calendar.market_open_time, self._calendar)

    def _next_trading_date_after(self, current_date: date) -> date:
        candidate_date = current_date + timedelta(days=1)
        while self._calendar.is_weekend(candidate_date) or self._calendar.is_holiday(
            candidate_date
        ):
            candidate_date += timedelta(days=1)
        return candidate_date

    def _hourly_windows(self, trading_date: date) -> tuple[datetime, ...]:
        windows: list[datetime] = []
        current = _aware_datetime(trading_date, self._calendar.market_open_time, self._calendar)
        close_at = _aware_datetime(trading_date, self._calendar.market_close_time, self._calendar)
        while current < close_at:
            windows.append(current)
            current += timedelta(hours=1)
        return tuple(windows)


def _validate_early_check_times(
    check_times: tuple[time, ...],
    calendar: TradingCalendar,
) -> tuple[time, ...]:
    if not 3 <= len(check_times) <= 4:
        raise ValueError("early_check_times must contain 3 or 4 check windows")
    if any(check_time.tzinfo is not None for check_time in check_times):
        raise ValueError("early_check_times must be timezone-naive")
    unique_sorted_times = tuple(sorted(set(check_times)))
    if len(unique_sorted_times) != len(check_times):
        raise ValueError("early_check_times must not contain duplicates")
    for check_time in unique_sorted_times:
        if check_time < calendar.market_open_time or check_time >= calendar.market_close_time:
            raise ValueError("early_check_times must be within market hours")
    return unique_sorted_times


def _combine_windows(
    trading_date: date,
    check_times: tuple[time, ...],
    calendar: TradingCalendar,
) -> tuple[datetime, ...]:
    return tuple(
        datetime.combine(trading_date, check_time, tzinfo=calendar.timezone)
        for check_time in check_times
    )


def _aware_datetime(
    trading_date: date,
    check_time: time,
    calendar: TradingCalendar,
) -> datetime:
    return datetime.combine(trading_date, check_time, tzinfo=calendar.timezone)


def _schedule_mode_from_monitoring_mode(monitoring_mode: MonitoringMode) -> ScheduleMode:
    if monitoring_mode == MonitoringMode.EARLY:
        return ScheduleMode.EARLY
    return ScheduleMode.HOURLY


def _next_window_after(windows: tuple[datetime, ...], current_window: datetime) -> datetime | None:
    for window in windows:
        if window > current_window:
            return window
    return None


def _already_ran_in_window(
    *,
    last_run_at: datetime | None,
    window_start: datetime,
) -> bool:
    return last_run_at is not None and last_run_at >= window_start
