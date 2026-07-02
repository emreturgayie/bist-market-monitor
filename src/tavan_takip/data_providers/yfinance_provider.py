"""yfinance-backed market data adapter."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
import logging
from typing import Any, Protocol, cast

import pandas as pd
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_fixed
import yfinance as yf

from tavan_takip.data_providers.base import (
    DailyPriceBar,
    DataProvider,
    DataProviderError,
    DataProviderNoDataError,
)
from tavan_takip.domain import MarketQuote

TickerFactory = Callable[[str], Any]
REQUIRED_HISTORY_COLUMNS = frozenset(("Open", "High", "Low", "Close", "Volume"))

logger = logging.getLogger(__name__)


class MetadataSource(Protocol):
    """Minimal metadata protocol supported by yfinance FastInfo and dictionaries."""

    def get(self, key: str, default: Any = None) -> Any:
        """Return a metadata value by key."""


class YFinanceProvider(DataProvider):
    """Retrieve market quotes using the yfinance package."""

    def __init__(
        self,
        *,
        ticker_factory: TickerFactory | None = None,
        retry_attempts: int = 3,
        retry_wait_seconds: float = 1.0,
    ) -> None:
        if retry_attempts < 1:
            raise ValueError("retry_attempts must be at least 1")
        if retry_wait_seconds < 0:
            raise ValueError("retry_wait_seconds must be greater than or equal to zero")

        self._ticker_factory = ticker_factory or yf.Ticker
        self._retry_attempts = retry_attempts
        self._retry_wait_seconds = retry_wait_seconds

    def get_quote(self, symbol: str) -> MarketQuote:
        """Return the latest quote for a symbol, retrying transient provider failures."""
        retrying = Retrying(
            stop=stop_after_attempt(self._retry_attempts),
            wait=wait_fixed(self._retry_wait_seconds),
            retry=retry_if_exception_type(DataProviderError),
            reraise=True,
        )

        for attempt in retrying:
            with attempt:
                return self._fetch_quote(symbol)

        raise DataProviderError("quote retrieval ended without a result")

    def get_daily_bars(self, symbol: str, *, period: str = "1mo") -> tuple[DailyPriceBar, ...]:
        """Return recent daily OHLCV bars for a symbol."""
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must not be blank")
        if not period.strip():
            raise ValueError("period must not be blank")

        try:
            ticker = self._ticker_factory(normalized_symbol)
            history = ticker.history(period=period, interval="1d", auto_adjust=False)
        except Exception as exc:
            logger.warning(
                "market_data_provider_daily_history_failed",
                extra={"provider": "yfinance", "symbol": normalized_symbol},
                exc_info=exc,
            )
            raise DataProviderError(
                f"failed to retrieve daily history for {normalized_symbol}"
            ) from exc

        if not isinstance(history, pd.DataFrame):
            raise DataProviderError("yfinance returned an unexpected daily history payload")
        _validate_history_columns(history)

        non_empty_history = history.dropna(subset=["Open", "High", "Low", "Close"])
        if non_empty_history.empty:
            raise DataProviderNoDataError(f"no daily history found for {normalized_symbol}")

        metadata = _as_metadata_source(getattr(ticker, "fast_info", {}))
        currency = str(
            _first_available(
                metadata,
                ("currency", "quoteCurrency"),
                fallback="TRY",
            )
        )
        return tuple(
            _daily_bar_from_row(
                symbol=normalized_symbol,
                index_value=index_value,
                row=row,
                currency=currency,
            )
            for index_value, row in non_empty_history.iterrows()
        )

    def _fetch_quote(self, symbol: str) -> MarketQuote:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must not be blank")

        try:
            ticker = self._ticker_factory(normalized_symbol)
            history = ticker.history(period="1d", interval="1m", auto_adjust=False)
        except Exception as exc:
            logger.warning(
                "market_data_provider_fetch_failed",
                extra={"provider": "yfinance", "symbol": normalized_symbol},
                exc_info=exc,
            )
            raise DataProviderError(f"failed to retrieve quote for {normalized_symbol}") from exc

        if not isinstance(history, pd.DataFrame):
            raise DataProviderError("yfinance returned an unexpected history payload")
        _validate_history_columns(history)

        non_empty_history = history.dropna(subset=["Close"])
        if non_empty_history.empty:
            logger.info(
                "market_data_provider_no_data",
                extra={"provider": "yfinance", "symbol": normalized_symbol},
            )
            raise DataProviderNoDataError(f"no quote data found for {normalized_symbol}")

        latest_row = non_empty_history.iloc[-1]
        metadata = _as_metadata_source(getattr(ticker, "fast_info", {}))
        timestamp = _timestamp_from_index(non_empty_history.index[-1])

        previous_close = _first_available(
            metadata,
            ("previous_close", "regularMarketPreviousClose", "previousClose"),
            fallback=latest_row.get("Open"),
        )
        currency = str(
            _first_available(
                metadata,
                ("currency", "quoteCurrency"),
                fallback="TRY",
            )
        )

        return MarketQuote.from_raw_values(
            symbol=normalized_symbol,
            price=latest_row["Close"],
            previous_close=previous_close,
            open_price=latest_row["Open"],
            high_price=latest_row["High"],
            low_price=latest_row["Low"],
            volume=latest_row["Volume"],
            currency=currency,
            timestamp=timestamp,
        )


def _validate_history_columns(history: pd.DataFrame) -> None:
    missing_columns = REQUIRED_HISTORY_COLUMNS.difference(history.columns)
    if missing_columns:
        missing_column_list = ", ".join(sorted(missing_columns))
        raise DataProviderError(f"yfinance history is missing columns: {missing_column_list}")


def _as_metadata_source(value: Any) -> MetadataSource:
    getter = getattr(value, "get", None)
    if callable(getter):
        return cast(MetadataSource, value)
    return {}


def _first_available(
    values: MetadataSource,
    keys: tuple[str, ...],
    *,
    fallback: Any,
) -> Any:
    for key in keys:
        try:
            value = values.get(key)
        except Exception:
            logger.debug(
                "market_data_provider_metadata_key_failed",
                extra={"provider": "yfinance", "metadata_key": key},
                exc_info=True,
            )
            continue
        if value is not None:
            return value
    return fallback


def _timestamp_from_index(value: Any) -> datetime:
    if isinstance(value, pd.Timestamp):
        timestamp = value.to_pydatetime()
    elif isinstance(value, datetime):
        timestamp = value
    else:
        raise DataProviderError("quote timestamp has an unsupported type")

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp


def _daily_bar_from_row(
    *,
    symbol: str,
    index_value: Any,
    row: pd.Series,
    currency: str,
) -> DailyPriceBar:
    timestamp = _timestamp_from_index(index_value)
    return DailyPriceBar(
        symbol=symbol,
        trading_date=timestamp.date(),
        open_price=_to_decimal(row["Open"]),
        high_price=_to_decimal(row["High"]),
        low_price=_to_decimal(row["Low"]),
        close_price=_to_decimal(row["Close"]),
        volume=int(row["Volume"]),
        currency=currency,
    )


def _to_decimal(value: Any) -> Decimal:
    return Decimal(str(value))
