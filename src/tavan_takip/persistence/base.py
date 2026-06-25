"""Persistence interfaces for application state."""

from __future__ import annotations

from typing import Protocol

from tavan_takip.domain import IPOTrackingState


class IPOTrackingStateRepository(Protocol):
    """Port for storing and loading IPO tracking state."""

    def save(self, state: IPOTrackingState) -> None:
        """Persist a tracking state, replacing any existing state for the symbol."""

    def load(self, symbol: str) -> IPOTrackingState | None:
        """Load a tracking state by symbol, or return None when it is missing."""

    def get_or_create(self, symbol: str) -> IPOTrackingState:
        """Load a tracking state or return a default state when it is missing."""

    def load_all(self) -> dict[str, IPOTrackingState]:
        """Load all persisted tracking states keyed by symbol."""


class BreakAlertRepository(Protocol):
    """Port for deduplicating break-alert notifications."""

    def has_break_alert_been_sent(self, symbol: str) -> bool:
        """Return whether the current broken state has already been alerted."""

    def mark_break_alert_sent(self, symbol: str) -> None:
        """Persist that a break alert has been successfully sent."""

    def clear_break_alert(self, symbol: str) -> None:
        """Clear the sent marker after the symbol leaves the broken state."""
