"""Domain logic for IPO ceiling price and ceiling-break detection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_FLOOR
from enum import StrEnum

from tavan_takip.domain.market_quote import MarketQuote


class CeilingStatus(StrEnum):
    """Current relationship between the latest quote and the theoretical ceiling."""

    AT_CEILING = "at_ceiling"
    BELOW_CEILING = "below_ceiling"
    BROKEN = "broken"


class SignalSeverity(StrEnum):
    """Severity of a ceiling-break detection result."""

    NONE = "none"
    LOW = "low"
    HIGH = "high"


class CeilingSignalReason(StrEnum):
    """Machine-readable reason for a detector decision."""

    CEILING_INTACT = "ceiling_intact"
    FILTERED_BY_TOLERANCE = "filtered_by_tolerance"
    FILTERED_BY_SINGLE_TICK = "filtered_by_single_tick"
    CEILING_BREAK = "ceiling_break"


@dataclass(frozen=True, slots=True)
class IPOTrackingConfig:
    """Configuration for monitoring one IPO symbol."""

    symbol: str
    ipo_price: Decimal | None = None
    daily_limit_percent: Decimal = Decimal("10")
    price_tick: Decimal = Decimal("0.01")
    tolerance: Decimal = Decimal("0")
    ignore_single_tick_difference: bool = True

    def __post_init__(self) -> None:
        """Normalize the symbol and validate financial parameters."""
        normalized_symbol = self.symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must not be blank")
        if self.ipo_price is not None and self.ipo_price <= Decimal("0"):
            raise ValueError("ipo_price must be greater than zero")
        if self.daily_limit_percent <= Decimal("0"):
            raise ValueError("daily_limit_percent must be greater than zero")
        if self.price_tick <= Decimal("0"):
            raise ValueError("price_tick must be greater than zero")
        if self.tolerance < Decimal("0"):
            raise ValueError("tolerance must be greater than or equal to zero")

        object.__setattr__(self, "symbol", normalized_symbol)

    def ceiling_base_price(self, quote: MarketQuote) -> Decimal:
        """Return the base price used for theoretical ceiling calculation."""
        if self.ipo_price is not None:
            return self.ipo_price
        return quote.previous_close


@dataclass(frozen=True, slots=True)
class CeilingBreakSignal:
    """Structured domain result emitted by the ceiling-break detector."""

    symbol: str
    status: CeilingStatus
    severity: SignalSeverity
    reason: CeilingSignalReason
    current_price: Decimal
    theoretical_ceiling_price: Decimal
    ceiling_gap: Decimal
    tolerance: Decimal
    is_at_ceiling: bool
    is_below_ceiling: bool
    should_alert: bool
    detected_at: datetime


class CeilingCalculator:
    """Calculate theoretical exchange ceiling prices using Decimal arithmetic."""

    def calculate(
        self,
        *,
        base_price: Decimal,
        daily_limit_percent: Decimal,
        price_tick: Decimal,
    ) -> Decimal:
        """Return the ceiling price rounded down to the configured price tick."""
        self._validate_inputs(
            base_price=base_price,
            daily_limit_percent=daily_limit_percent,
            price_tick=price_tick,
        )
        multiplier = Decimal("1") + (daily_limit_percent / Decimal("100"))
        raw_ceiling_price = base_price * multiplier
        return self._round_down_to_tick(raw_ceiling_price, price_tick)

    @staticmethod
    def _validate_inputs(
        *,
        base_price: Decimal,
        daily_limit_percent: Decimal,
        price_tick: Decimal,
    ) -> None:
        if base_price <= Decimal("0"):
            raise ValueError("base_price must be greater than zero")
        if daily_limit_percent <= Decimal("0"):
            raise ValueError("daily_limit_percent must be greater than zero")
        if price_tick <= Decimal("0"):
            raise ValueError("price_tick must be greater than zero")

    @staticmethod
    def _round_down_to_tick(price: Decimal, price_tick: Decimal) -> Decimal:
        tick_count = (price / price_tick).to_integral_value(rounding=ROUND_FLOOR)
        return (tick_count * price_tick).quantize(price_tick)


class CeilingBreakDetector:
    """Detect whether an IPO quote indicates a potential ceiling break."""

    def __init__(self, calculator: CeilingCalculator | None = None) -> None:
        self._calculator = calculator or CeilingCalculator()

    def detect(self, quote: MarketQuote, config: IPOTrackingConfig) -> CeilingBreakSignal:
        """Return a structured signal for the latest quote and tracking config."""
        self._ensure_symbol_match(quote, config)

        theoretical_ceiling_price = self._calculator.calculate(
            base_price=config.ceiling_base_price(quote),
            daily_limit_percent=config.daily_limit_percent,
            price_tick=config.price_tick,
        )
        raw_gap = theoretical_ceiling_price - quote.price
        ceiling_gap = max(raw_gap, Decimal("0"))

        if raw_gap <= config.tolerance:
            return _build_signal(
                quote=quote,
                status=CeilingStatus.AT_CEILING,
                severity=SignalSeverity.NONE,
                reason=(
                    CeilingSignalReason.CEILING_INTACT
                    if raw_gap <= Decimal("0")
                    else CeilingSignalReason.FILTERED_BY_TOLERANCE
                ),
                theoretical_ceiling_price=theoretical_ceiling_price,
                ceiling_gap=ceiling_gap,
                tolerance=config.tolerance,
                should_alert=False,
            )

        if config.ignore_single_tick_difference and raw_gap <= config.price_tick:
            return _build_signal(
                quote=quote,
                status=CeilingStatus.BELOW_CEILING,
                severity=SignalSeverity.LOW,
                reason=CeilingSignalReason.FILTERED_BY_SINGLE_TICK,
                theoretical_ceiling_price=theoretical_ceiling_price,
                ceiling_gap=ceiling_gap,
                tolerance=config.tolerance,
                should_alert=False,
            )

        return _build_signal(
            quote=quote,
            status=CeilingStatus.BROKEN,
            severity=SignalSeverity.HIGH,
            reason=CeilingSignalReason.CEILING_BREAK,
            theoretical_ceiling_price=theoretical_ceiling_price,
            ceiling_gap=ceiling_gap,
            tolerance=config.tolerance,
            should_alert=True,
        )

    @staticmethod
    def _ensure_symbol_match(quote: MarketQuote, config: IPOTrackingConfig) -> None:
        if quote.symbol != config.symbol:
            raise ValueError("quote symbol must match IPO tracking config symbol")


def _build_signal(
    *,
    quote: MarketQuote,
    status: CeilingStatus,
    severity: SignalSeverity,
    reason: CeilingSignalReason,
    theoretical_ceiling_price: Decimal,
    ceiling_gap: Decimal,
    tolerance: Decimal,
    should_alert: bool,
) -> CeilingBreakSignal:
    return CeilingBreakSignal(
        symbol=quote.symbol,
        status=status,
        severity=severity,
        reason=reason,
        current_price=quote.price,
        theoretical_ceiling_price=theoretical_ceiling_price,
        ceiling_gap=ceiling_gap,
        tolerance=tolerance,
        is_at_ceiling=status == CeilingStatus.AT_CEILING,
        is_below_ceiling=status in {CeilingStatus.BELOW_CEILING, CeilingStatus.BROKEN},
        should_alert=should_alert,
        detected_at=quote.timestamp,
    )
