"""Factory for constructing configured market data providers."""

from __future__ import annotations

from tavan_takip.config import DataProviderName, Settings
from tavan_takip.data_providers.algolab_mock_provider import AlgoLabMockProvider
from tavan_takip.data_providers.base import DataProvider
from tavan_takip.data_providers.yfinance_provider import YFinanceProvider


def create_data_provider(settings: Settings) -> DataProvider:
    """Create the configured market data provider adapter."""
    if settings.data_provider == DataProviderName.YFINANCE:
        return YFinanceProvider(
            retry_attempts=settings.yfinance_retry_attempts,
            retry_wait_seconds=settings.yfinance_retry_wait_seconds,
        )
    if settings.data_provider == DataProviderName.ALGOLAB_MOCK:
        return AlgoLabMockProvider()
    raise ValueError(f"unsupported data provider: {settings.data_provider}")
