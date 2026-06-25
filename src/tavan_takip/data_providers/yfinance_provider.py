"""yfinance-backed market data adapter."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
import logging
from typing import Any

import pandas as pd
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_fixed
import yfinance as yf

from tavan_takip.data_providers.base import DataProvider, DataProviderError, DataProviderNoDataError
from tavan_takip.domain import MarketQuote

TickerFactory = Callable[[str], Any]
REQUIRED_HISTORY_COLUMNS = frozenset(("Open", "High", "Low", "Close", "Volume"))

logger = logging.getLogger(__name__)


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
        metadata = _as_mapping(getattr(ticker, "fast_info", {}))
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


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _first_available(
    values: Mapping[str, Any],
    keys: tuple[str, ...],
    *,
    fallback: Any,
) -> Any:
    for key in keys:
        value = values.get(key)
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
