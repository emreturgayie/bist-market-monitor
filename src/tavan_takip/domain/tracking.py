"""Domain-level IPO tracking state and business rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from tavan_takip.domain.ceiling import (
    CeilingBreakDetector,
    CeilingBreakSignal,
    IPOTrackingConfig,
)
from tavan_takip.domain.market_quote import MarketQuote

EARLY_MONITORING_MAX_CEILING_DAYS = 5


class MonitoringMode(StrEnum):
    """Polling mode implied by the current IPO ceiling streak."""

    EARLY = "early"
    HOURLY = "hourly"


class IPOTrackingLifecycleState(StrEnum):
    """Lifecycle state of a tracked IPO symbol."""

    MONITORING = "monitoring"
    CEILING_BROKEN = "ceiling_broken"


@dataclass(frozen=True, slots=True)
class IPOTrackingState:
    """Explicit in-memory state for one tracked IPO symbol."""

    symbol: str
    consecutive_ceiling_days: int = 0
    last_processed_trading_date: date | None = None
    lifecycle_state: IPOTrackingLifecycleState = IPOTrackingLifecycleState.MONITORING

    def __post_init__(self) -> None:
        """Normalize the symbol and validate state invariants."""
        normalized_symbol = self.symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must not be blank")
        if self.consecutive_ceiling_days < 0:
            raise ValueError("consecutive_ceiling_days must be greater than or equal to zero")
        if (
            self.lifecycle_state == IPOTrackingLifecycleState.CEILING_BROKEN
            and self.consecutive_ceiling_days != 0
        ):
            raise ValueError("ceiling-broken state cannot keep a positive ceiling streak")

        object.__setattr__(self, "symbol", normalized_symbol)

    @property
    def monitoring_mode(self) -> MonitoringMode:
        """Return the monitoring mode implied by the ceiling streak."""
        if self.consecutive_ceiling_days <= EARLY_MONITORING_MAX_CEILING_DAYS:
            return MonitoringMode.EARLY
        return MonitoringMode.HOURLY


@dataclass(frozen=True, slots=True)
class IPOTrackingResult:
    """Structured result of processing one market quote through the tracker."""

    symbol: str
    trading_date: date
    previous_state: IPOTrackingState
    updated_state: IPOTrackingState
    ceiling_signal: CeilingBreakSignal
    monitoring_mode: MonitoringMode
    lifecycle_state: IPOTrackingLifecycleState
    new_ceiling_day_counted: bool
    ceiling_streak_reset: bool


class IPOTracker:
    """Track IPO ceiling streak state using the ceiling-break detector."""

    def __init__(self, detector: CeilingBreakDetector | None = None) -> None:
        self._detector = detector or CeilingBreakDetector()

    def track(
        self,
        *,
        quote: MarketQuote,
        config: IPOTrackingConfig,
        state: IPOTrackingState | None = None,
    ) -> IPOTrackingResult:
        """Process one quote and return an updated tracking result."""
        current_state = state or IPOTrackingState(symbol=config.symbol)
        self._ensure_state_matches_config(current_state, config)

        ceiling_signal = self._detector.detect(quote, config)
        trading_date = quote.timestamp.date()
        updated_state, new_ceiling_day_counted, ceiling_streak_reset = self._next_state(
            state=current_state,
            signal=ceiling_signal,
            trading_date=trading_date,
        )

        return IPOTrackingResult(
            symbol=config.symbol,
            trading_date=trading_date,
            previous_state=current_state,
            updated_state=updated_state,
            ceiling_signal=ceiling_signal,
            monitoring_mode=updated_state.monitoring_mode,
            lifecycle_state=updated_state.lifecycle_state,
            new_ceiling_day_counted=new_ceiling_day_counted,
            ceiling_streak_reset=ceiling_streak_reset,
        )

    @staticmethod
    def _ensure_state_matches_config(
        state: IPOTrackingState,
        config: IPOTrackingConfig,
    ) -> None:
        if state.symbol != config.symbol:
            raise ValueError("tracking state symbol must match IPO tracking config symbol")

    @staticmethod
    def _next_state(
        *,
        state: IPOTrackingState,
        signal: CeilingBreakSignal,
        trading_date: date,
    ) -> tuple[IPOTrackingState, bool, bool]:
        if signal.should_alert:
            return (
                IPOTrackingState(
                    symbol=state.symbol,
                    consecutive_ceiling_days=0,
                    last_processed_trading_date=trading_date,
                    lifecycle_state=IPOTrackingLifecycleState.CEILING_BROKEN,
                ),
                False,
                state.consecutive_ceiling_days > 0,
            )

        is_new_trading_day = state.last_processed_trading_date != trading_date
        new_ceiling_day_counted = signal.is_at_ceiling and is_new_trading_day
        consecutive_ceiling_days = state.consecutive_ceiling_days
        if new_ceiling_day_counted:
            consecutive_ceiling_days += 1

        return (
            IPOTrackingState(
                symbol=state.symbol,
                consecutive_ceiling_days=consecutive_ceiling_days,
                last_processed_trading_date=trading_date,
                lifecycle_state=IPOTrackingLifecycleState.MONITORING,
            ),
            new_ceiling_day_counted,
            False,
        )
