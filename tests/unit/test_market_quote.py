"""Tests for the MarketQuote domain model."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from tavan_takip.domain import MarketQuote


def test_market_quote_normalizes_symbols_and_exposes_changes() -> None:
    quote = MarketQuote.from_raw_values(
        symbol=" thyao.is ",
        price="11.50",
        previous_close="10",
        open_price="10.25",
        high_price="12",
        low_price="10",
        volume="1200",
        currency=" try ",
        timestamp=datetime(2026, 1, 2, 10, 30, tzinfo=UTC),
    )

    assert quote.symbol == "THYAO.IS"
    assert quote.currency == "TRY"
    assert quote.change == Decimal("1.50")
    assert quote.change_percent == Decimal("15.00")


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("price", "-1"),
        ("previous_close", "-1"),
        ("open_price", "-1"),
        ("high_price", "-1"),
        ("low_price", "-1"),
    ],
)
def test_market_quote_rejects_negative_prices(field_name: str, value: str) -> None:
    values: dict[str, Any] = {
        "symbol": "THYAO.IS",
        "price": "10",
        "previous_close": "9",
        "open_price": "9.5",
        "high_price": "11",
        "low_price": "9",
        "volume": 100,
        "currency": "TRY",
        "timestamp": datetime(2026, 1, 2, 10, 30, tzinfo=UTC),
    }
    values[field_name] = value

    with pytest.raises(ValueError, match=field_name):
        MarketQuote.from_raw_values(**values)


def test_market_quote_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        MarketQuote.from_raw_values(
            symbol="THYAO.IS",
            price="10",
            previous_close="9",
            open_price="9.5",
            high_price="11",
            low_price="9",
            volume=100,
            currency="TRY",
            timestamp=datetime(2026, 1, 2, 10, 30),
        )
