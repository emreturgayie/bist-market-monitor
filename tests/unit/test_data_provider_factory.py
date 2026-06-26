"""Tests for configured market data provider selection."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from tavan_takip.config import DataProviderName, Settings
from tavan_takip.data_providers import (
    AlgoLabMockProvider,
    DataProvider,
    DataProviderNoDataError,
    YFinanceProvider,
    create_data_provider,
)
from tavan_takip.domain import MarketQuote
from tavan_takip.market import DEFAULT_MARKET_TIMEZONE


def test_provider_factory_returns_yfinance_by_default() -> None:
    provider = create_data_provider(Settings())

    assert isinstance(provider, YFinanceProvider)


def test_provider_factory_returns_algolab_mock_when_configured() -> None:
    provider = create_data_provider(Settings(data_provider=DataProviderName.ALGOLAB_MOCK))

    assert isinstance(provider, AlgoLabMockProvider)


def test_algolab_mock_provider_follows_data_provider_interface() -> None:
    quote = _make_quote("ORNEK.IS")
    provider: DataProvider = AlgoLabMockProvider({"ornek.is": quote})

    assert provider.get_quote("ORNEK.IS") == quote


def test_algolab_mock_provider_does_not_make_network_calls() -> None:
    provider = AlgoLabMockProvider()

    with pytest.raises(DataProviderNoDataError, match="real AlgoLab integration is future work"):
        provider.get_quote("ORNEK.IS")


def test_algolab_mock_provider_rejects_blank_symbol() -> None:
    provider = AlgoLabMockProvider()

    with pytest.raises(ValueError, match="symbol"):
        provider.get_quote(" ")


def _make_quote(symbol: str) -> MarketQuote:
    return MarketQuote(
        symbol=symbol,
        price=Decimal("11.00"),
        previous_close=Decimal("10.00"),
        open_price=Decimal("10.00"),
        high_price=Decimal("11.00"),
        low_price=Decimal("10.00"),
        volume=1_000,
        currency="TRY",
        timestamp=datetime(2026, 1, 5, 10, 30, tzinfo=DEFAULT_MARKET_TIMEZONE),
    )
