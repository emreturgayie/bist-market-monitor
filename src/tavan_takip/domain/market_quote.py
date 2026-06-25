"""Domain model for a single market quote."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class MarketQuote:
    """Immutable market quote used by application services and adapters."""

    symbol: str
    price: Decimal
    previous_close: Decimal
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    volume: int
    currency: str
    timestamp: datetime

    def __post_init__(self) -> None:
        """Normalize textual fields and validate market data invariants."""
        normalized_symbol = self.symbol.strip().upper()
        normalized_currency = self.currency.strip().upper()

        if not normalized_symbol:
            raise ValueError("symbol must not be blank")
        if not normalized_currency:
            raise ValueError("currency must not be blank")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        if self.volume < 0:
            raise ValueError("volume must be greater than or equal to zero")

        for field_name in (
            "price",
            "previous_close",
            "open_price",
            "high_price",
            "low_price",
        ):
            value = getattr(self, field_name)
            if value < Decimal("0"):
                raise ValueError(f"{field_name} must be greater than or equal to zero")

        object.__setattr__(self, "symbol", normalized_symbol)
        object.__setattr__(self, "currency", normalized_currency)

    @property
    def change(self) -> Decimal:
        """Absolute price change compared with the previous close."""
        return self.price - self.previous_close

    @property
    def change_percent(self) -> Decimal:
        """Percentage price change compared with the previous close."""
        if self.previous_close == Decimal("0"):
            return Decimal("0")
        return (self.change / self.previous_close) * Decimal("100")

    @classmethod
    def from_raw_values(
        cls,
        *,
        symbol: str,
        price: Any,
        previous_close: Any,
        open_price: Any,
        high_price: Any,
        low_price: Any,
        volume: Any,
        currency: str,
        timestamp: datetime,
    ) -> MarketQuote:
        """Build a quote from adapter-level primitive values."""
        return cls(
            symbol=symbol,
            price=_to_decimal(price, "price"),
            previous_close=_to_decimal(previous_close, "previous_close"),
            open_price=_to_decimal(open_price, "open_price"),
            high_price=_to_decimal(high_price, "high_price"),
            low_price=_to_decimal(low_price, "low_price"),
            volume=_to_int(volume, "volume"),
            currency=currency,
            timestamp=timestamp,
        )


def _to_decimal(value: Any, field_name: str) -> Decimal:
    if value is None:
        raise ValueError(f"{field_name} must not be None")
    return Decimal(str(value))


def _to_int(value: Any, field_name: str) -> int:
    if value is None:
        raise ValueError(f"{field_name} must not be None")
    return int(value)
