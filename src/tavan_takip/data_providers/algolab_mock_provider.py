"""Mock AlgoLab market data adapter.

This adapter intentionally performs no network calls. It exists to make provider
selection and future production integration points explicit before real AlgoLab
credentials or API behavior are introduced.
"""

from __future__ import annotations

from collections.abc import Mapping

from tavan_takip.data_providers.base import DataProvider, DataProviderNoDataError
from tavan_takip.domain import MarketQuote


class AlgoLabMockProvider(DataProvider):
    """Network-free placeholder for a future real AlgoLab data provider."""

    def __init__(self, quotes: Mapping[str, MarketQuote] | None = None) -> None:
        self._quotes = {symbol.strip().upper(): quote for symbol, quote in (quotes or {}).items()}

    def get_quote(self, symbol: str) -> MarketQuote:
        """Return a seeded quote or raise a clear mock-provider no-data error."""
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must not be blank")
        quote = self._quotes.get(normalized_symbol)
        if quote is None:
            raise DataProviderNoDataError(
                "AlgoLab mock provider has no quote data for "
                f"{normalized_symbol}; real AlgoLab integration is future work"
            )
        return quote
