"""Market calendar and session evaluation logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import StrEnum
from zoneinfo import ZoneInfo

DEFAULT_MARKET_TIMEZONE = ZoneInfo("Europe/Istanbul")
DEFAULT_MARKET_OPEN_TIME = time(hour=10, minute=0)
DEFAULT_MARKET_CLOSE_TIME = time(hour=18, minute=0)
WEEKEND_DAYS = frozenset((5, 6))


class MarketSessionStatus(StrEnum):
    """Reasoned market-session status for a point in time."""

    OPEN = "open"
    BEFORE_OPEN = "before_open"
    AFTER_CLOSE = "after_close"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"


@dataclass(frozen=True, slots=True)
class TradingCalendar:
    """Configurable trading calendar for market-session decisions."""

    timezone: ZoneInfo = DEFAULT_MARKET_TIMEZONE
    market_open_time: time = DEFAULT_MARKET_OPEN_TIME
    market_close_time: time = DEFAULT_MARKET_CLOSE_TIME
    holidays: frozenset[date] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        """Validate calendar configuration."""
        if self.market_open_time.tzinfo is not None or self.market_close_time.tzinfo is not None:
            raise ValueError("market open and close times must be timezone-naive")
        if self.market_open_time >= self.market_close_time:
            raise ValueError("market_open_time must be before market_close_time")
        object.__setattr__(self, "holidays", frozenset(self.holidays))

    def localize(self, value: datetime) -> datetime:
        """Convert a timezone-aware datetime to the calendar timezone."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime must be timezone-aware")
        return value.astimezone(self.timezone)

    def is_weekend(self, trading_date: date) -> bool:
        """Return whether the trading date falls on a weekend."""
        return trading_date.weekday() in WEEKEND_DAYS

    def is_holiday(self, trading_date: date) -> bool:
        """Return whether the trading date is configured as a holiday."""
        return trading_date in self.holidays


@dataclass(frozen=True, slots=True)
class MarketSession:
    """Structured market-session decision for a point in time."""

    checked_at: datetime
    local_datetime: datetime
    trading_date: date
    timezone: ZoneInfo
    status: MarketSessionStatus
    market_open_time: time
    market_close_time: time

    @property
    def is_open(self) -> bool:
        """Return whether monitoring may run during the session."""
        return self.status == MarketSessionStatus.OPEN


class MarketSessionEngine:
    """Evaluate whether market monitoring should run at a given time."""

    def __init__(self, calendar: TradingCalendar | None = None) -> None:
        self._calendar = calendar or TradingCalendar()

    def evaluate(self, checked_at: datetime) -> MarketSession:
        """Return the market-session status for a timezone-aware datetime."""
        local_datetime = self._calendar.localize(checked_at)
        trading_date = local_datetime.date()
        status = self._status_for(local_datetime=local_datetime, trading_date=trading_date)

        return MarketSession(
            checked_at=checked_at,
            local_datetime=local_datetime,
            trading_date=trading_date,
            timezone=self._calendar.timezone,
            status=status,
            market_open_time=self._calendar.market_open_time,
            market_close_time=self._calendar.market_close_time,
        )

    def _status_for(
        self,
        *,
        local_datetime: datetime,
        trading_date: date,
    ) -> MarketSessionStatus:
        if self._calendar.is_weekend(trading_date):
            return MarketSessionStatus.WEEKEND
        if self._calendar.is_holiday(trading_date):
            return MarketSessionStatus.HOLIDAY

        local_time = local_datetime.time()
        if local_time < self._calendar.market_open_time:
            return MarketSessionStatus.BEFORE_OPEN
        if local_time >= self._calendar.market_close_time:
            return MarketSessionStatus.AFTER_CLOSE
        return MarketSessionStatus.OPEN
