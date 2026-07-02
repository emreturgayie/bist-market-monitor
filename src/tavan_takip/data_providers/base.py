"""Data provider abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from tavan_takip.domain import MarketQuote


@dataclass(frozen=True, slots=True)
class DailyPriceBar:
    """Daily OHLCV market data used to initialize tracking state."""

    symbol: str
    trading_date: date
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: int
    currency: str


class DataProviderError(RuntimeError):
    """Base exception raised by market data providers."""


class DataProviderNoDataError(DataProviderError):
    """Raised when a provider cannot find quote data for a symbol."""


class DataProvider(ABC):
    """Port for retrieving market quote data from an external source."""

    @abstractmethod
    def get_quote(self, symbol: str) -> MarketQuote:
        """Return the latest market quote for a single symbol."""

    def get_quotes(self, symbols: Sequence[str]) -> list[MarketQuote]:
        """Return the latest market quotes for all requested symbols."""
        return [self.get_quote(symbol) for symbol in symbols]

    def get_daily_bars(self, symbol: str, *, period: str = "1mo") -> tuple[DailyPriceBar, ...]:
        """Return recent daily bars for initializing tracking state."""
        raise DataProviderNoDataError(f"daily bar history is not available for {symbol}")
