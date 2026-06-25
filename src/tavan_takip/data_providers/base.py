"""Data provider abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from tavan_takip.domain import MarketQuote


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
