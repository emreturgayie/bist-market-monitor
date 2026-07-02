"""Tests for the yfinance data provider adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from decimal import Decimal
from typing import Any

import pandas as pd
import pytest

from tavan_takip.data_providers import (
    DataProviderError,
    DataProviderNoDataError,
    YFinanceProvider,
)


@dataclass
class FakeTicker:
    history_payload: pd.DataFrame
    fast_info: Any

    def history(self, **_: object) -> pd.DataFrame:
        return self.history_payload


class FakeFastInfo:
    """yfinance FastInfo-like object that supports get but is not a Mapping."""

    def __init__(self, values: dict[str, Any]) -> None:
        self._values = values

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)


def test_yfinance_provider_maps_history_to_market_quote() -> None:
    history = pd.DataFrame(
        [
            {
                "Open": 10.0,
                "High": 11.0,
                "Low": 9.5,
                "Close": 10.75,
                "Volume": 1500,
            }
        ],
        index=pd.DatetimeIndex(["2026-01-02 10:30:00+03:00"]),
    )

    provider = YFinanceProvider(
        ticker_factory=lambda symbol: FakeTicker(
            history_payload=history,
            fast_info={"previous_close": 10.0, "currency": "TRY", "symbol": symbol},
        ),
        retry_wait_seconds=0,
    )

    quote = provider.get_quote(" thyao.is ")

    assert quote.symbol == "THYAO.IS"
    assert quote.price == Decimal("10.75")
    assert quote.previous_close == Decimal("10.0")
    assert quote.volume == 1500
    assert quote.currency == "TRY"
    assert quote.timestamp.tzinfo is not None
    assert quote.timestamp.utcoffset() is not None


def test_yfinance_provider_reads_non_mapping_fast_info_previous_close() -> None:
    history = pd.DataFrame(
        [
            {
                "Open": 48.400002,
                "High": 48.400002,
                "Low": 48.400002,
                "Close": 48.400002,
                "Volume": 83435,
            }
        ],
        index=pd.DatetimeIndex(["2026-07-02 12:51:00+03:00"]),
    )
    provider = YFinanceProvider(
        ticker_factory=lambda _: FakeTicker(
            history_payload=history,
            fast_info=FakeFastInfo(
                {
                    "previous_close": None,
                    "regularMarketPreviousClose": 44.0,
                    "currency": "TRY",
                }
            ),
        ),
        retry_wait_seconds=0,
    )

    quote = provider.get_quote("BETAE.IS")

    assert quote.symbol == "BETAE.IS"
    assert quote.price == Decimal("48.400002")
    assert quote.previous_close == Decimal("44.0")


def test_yfinance_provider_adds_utc_to_naive_timestamps() -> None:
    history = pd.DataFrame(
        [{"Open": 10, "High": 11, "Low": 9, "Close": 10, "Volume": 100}],
        index=pd.DatetimeIndex(["2026-01-02 10:30:00"]),
    )
    provider = YFinanceProvider(
        ticker_factory=lambda _: FakeTicker(
            history_payload=history,
            fast_info={"previous_close": 9, "currency": "TRY"},
        ),
        retry_wait_seconds=0,
    )

    quote = provider.get_quote("THYAO.IS")

    assert quote.timestamp.tzinfo is UTC


def test_yfinance_provider_raises_no_data_for_empty_history() -> None:
    history = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    provider = YFinanceProvider(
        ticker_factory=lambda _: FakeTicker(history_payload=history, fast_info={}),
        retry_attempts=1,
        retry_wait_seconds=0,
    )

    with pytest.raises(DataProviderNoDataError):
        provider.get_quote("THYAO.IS")


def test_yfinance_provider_retries_transient_errors() -> None:
    history = pd.DataFrame(
        [{"Open": 10, "High": 11, "Low": 9, "Close": 10, "Volume": 100}],
        index=pd.DatetimeIndex(["2026-01-02 10:30:00+00:00"]),
    )
    attempts = 0

    def ticker_factory(_: str) -> FakeTicker:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary failure")
        return FakeTicker(history_payload=history, fast_info={"previous_close": 9})

    provider = YFinanceProvider(
        ticker_factory=ticker_factory,
        retry_attempts=2,
        retry_wait_seconds=0,
    )

    quote = provider.get_quote("THYAO.IS")

    assert quote.price == Decimal("10")
    assert attempts == 2


def test_yfinance_provider_wraps_unexpected_provider_errors() -> None:
    provider = YFinanceProvider(
        ticker_factory=lambda _: (_ for _ in ()).throw(RuntimeError("boom")),
        retry_attempts=1,
        retry_wait_seconds=0,
    )

    with pytest.raises(DataProviderError, match="failed to retrieve quote"):
        provider.get_quote("THYAO.IS")
