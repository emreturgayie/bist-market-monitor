"""Tests for the local monitoring CLI workflow."""

from __future__ import annotations

from datetime import datetime
from io import StringIO

from tavan_takip.application import run_monitoring_cycle
from tavan_takip.config import Settings
from tavan_takip.data_providers import DataProvider, DataProviderNoDataError
from tavan_takip.domain import MarketQuote
from tavan_takip.market import DEFAULT_MARKET_TIMEZONE


class FakeDataProvider(DataProvider):
    """Network-free provider for CLI tests."""

    def __init__(self, quotes: dict[str, MarketQuote]) -> None:
        self._quotes = quotes
        self.requested_symbols: list[str] = []

    def get_quote(self, symbol: str) -> MarketQuote:
        self.requested_symbols.append(symbol)
        quote = self._quotes.get(symbol)
        if quote is None:
            raise DataProviderNoDataError(f"missing quote for {symbol}")
        return quote


def make_quote(
    *,
    symbol: str,
    price: str = "11.00",
    previous_close: str = "10.00",
) -> MarketQuote:
    return MarketQuote.from_raw_values(
        symbol=symbol,
        price=price,
        previous_close=previous_close,
        open_price=previous_close,
        high_price=price,
        low_price=previous_close,
        volume=1_000,
        currency="TRY",
        timestamp=datetime(2026, 1, 5, 10, 30, tzinfo=DEFAULT_MARKET_TIMEZONE),
    )


def test_no_symbols_configured() -> None:
    provider = FakeDataProvider(quotes={})
    output = StringIO()

    outcome = run_monitoring_cycle(
        settings=Settings(tracked_symbols=()),
        data_provider=provider,
        output=output,
    )

    assert outcome.exit_code == 0
    assert outcome.monitoring_result is None
    assert provider.requested_symbols == []
    assert "No symbols configured" in output.getvalue()
    assert "Not investment advice." in output.getvalue()


def test_market_closed_output() -> None:
    provider = FakeDataProvider(quotes={"ORNEK.IS": make_quote(symbol="ORNEK.IS")})
    output = StringIO()

    outcome = run_monitoring_cycle(
        settings=Settings(tracked_symbols=("ORNEK.IS",)),
        data_provider=provider,
        output=output,
        now_provider=lambda: datetime(2026, 1, 5, 9, 0, tzinfo=DEFAULT_MARKET_TIMEZONE),
    )

    assert outcome.monitoring_result is not None
    assert provider.requested_symbols == []
    rendered = output.getvalue()
    assert "Market status: before_open" in rendered
    assert "Monitoring skipped because the market is closed." in rendered
    assert "Not investment advice." in rendered


def test_market_open_with_fake_provider() -> None:
    provider = FakeDataProvider(quotes={"ORNEK.IS": make_quote(symbol="ORNEK.IS")})
    output = StringIO()

    outcome = run_monitoring_cycle(
        settings=Settings(tracked_symbols=("ORNEK.IS",)),
        data_provider=provider,
        output=output,
        now_provider=lambda: datetime(2026, 1, 5, 10, 30, tzinfo=DEFAULT_MARKET_TIMEZONE),
    )

    assert outcome.monitoring_result is not None
    assert provider.requested_symbols == ["ORNEK.IS"]
    rendered = output.getvalue()
    assert "Market status: open" in rendered
    assert "- ORNEK.IS: ok;" in rendered
    assert "ceiling_days=1" in rendered
    assert "Not investment advice." in rendered


def test_missing_quote_output() -> None:
    provider = FakeDataProvider(quotes={})
    output = StringIO()

    run_monitoring_cycle(
        settings=Settings(tracked_symbols=("ORNEK.IS",)),
        data_provider=provider,
        output=output,
        now_provider=lambda: datetime(2026, 1, 5, 10, 30, tzinfo=DEFAULT_MARKET_TIMEZONE),
    )

    rendered = output.getvalue()
    assert "- ORNEK.IS: missing quote (missing quote for ORNEK.IS)" in rendered
    assert "Missing quotes: ORNEK.IS" in rendered


def test_break_signal_output() -> None:
    provider = FakeDataProvider(quotes={"ORNEK.IS": make_quote(symbol="ORNEK.IS", price="10.95")})
    output = StringIO()

    run_monitoring_cycle(
        settings=Settings(tracked_symbols=("ORNEK.IS",)),
        data_provider=provider,
        output=output,
        now_provider=lambda: datetime(2026, 1, 5, 10, 30, tzinfo=DEFAULT_MARKET_TIMEZONE),
    )

    rendered = output.getvalue()
    assert "- ORNEK.IS: BREAK SIGNAL;" in rendered
    assert "Break reason: ceiling_break" in rendered
    assert "gap=0.05" in rendered


def test_cli_workflow_uses_no_real_network() -> None:
    provider = FakeDataProvider(
        quotes={
            "ALFA.IS": make_quote(symbol="ALFA.IS"),
            "BRAVO.IS": make_quote(symbol="BRAVO.IS"),
        }
    )
    output = StringIO()

    run_monitoring_cycle(
        settings=Settings(tracked_symbols=("ALFA.IS", "BRAVO.IS")),
        data_provider=provider,
        output=output,
        now_provider=lambda: datetime(2026, 1, 5, 10, 30, tzinfo=DEFAULT_MARKET_TIMEZONE),
    )

    assert provider.requested_symbols == ["ALFA.IS", "BRAVO.IS"]
    assert "ALFA.IS" in output.getvalue()
    assert "BRAVO.IS" in output.getvalue()
