"""Application service for initializing IPO tracking state from daily bars."""

from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal

from tavan_takip.data_providers import DailyPriceBar
from tavan_takip.domain import IPOTracker, IPOTrackingConfig, IPOTrackingState, MarketQuote
from tavan_takip.market import DEFAULT_MARKET_TIMEZONE


class IPOTrackingStateBackfiller:
    """Build an initial tracking state from available historical daily bars."""

    def __init__(self, *, tracker: IPOTracker | None = None) -> None:
        self._tracker = tracker or IPOTracker()

    def backfill(
        self,
        *,
        config: IPOTrackingConfig,
        daily_bars: tuple[DailyPriceBar, ...],
    ) -> IPOTrackingState:
        """Return the best initial state that can be inferred from daily bars."""
        sorted_bars = tuple(sorted(daily_bars, key=lambda bar: bar.trading_date))
        if not sorted_bars:
            return IPOTrackingState(symbol=config.symbol)

        state = IPOTrackingState(symbol=config.symbol)
        previous_bar: DailyPriceBar | None = None
        for bar in sorted_bars:
            if bar.symbol != config.symbol:
                raise ValueError("daily bar symbol must match IPO tracking config symbol")
            if previous_bar is None:
                state = self._state_from_first_bar(config=config, bar=bar, state=state)
            else:
                quote = _quote_from_daily_bar(bar=bar, previous_close=previous_bar.close_price)
                state = self._tracker.track(quote=quote, config=config, state=state).updated_state
            previous_bar = bar
        return state

    def _state_from_first_bar(
        self,
        *,
        config: IPOTrackingConfig,
        bar: DailyPriceBar,
        state: IPOTrackingState,
    ) -> IPOTrackingState:
        if config.ipo_price is not None:
            quote = _quote_from_daily_bar(bar=bar, previous_close=config.ipo_price)
            return self._tracker.track(quote=quote, config=config, state=state).updated_state
        if _is_locked_limit_up_like_first_bar(bar):
            return IPOTrackingState(
                symbol=config.symbol,
                consecutive_ceiling_days=1,
                last_processed_trading_date=bar.trading_date,
            )
        return state


def _quote_from_daily_bar(*, bar: DailyPriceBar, previous_close: Decimal) -> MarketQuote:
    return MarketQuote(
        symbol=bar.symbol,
        price=bar.close_price,
        previous_close=previous_close,
        open_price=bar.open_price,
        high_price=bar.high_price,
        low_price=bar.low_price,
        volume=bar.volume,
        currency=bar.currency,
        timestamp=datetime.combine(bar.trading_date, time.min, tzinfo=DEFAULT_MARKET_TIMEZONE),
    )


def _is_locked_limit_up_like_first_bar(bar: DailyPriceBar) -> bool:
    return (
        bar.open_price == bar.high_price
        and bar.high_price == bar.low_price
        and bar.low_price == bar.close_price
        and bar.close_price > Decimal("0")
    )
