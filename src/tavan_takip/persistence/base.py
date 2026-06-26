"""Persistence interfaces for application state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from tavan_takip.domain import IPOTrackingState


@dataclass(frozen=True, slots=True)
class BreakAlertRecord:
    """Persisted record of a sent break alert."""

    symbol: str
    sent_at: datetime


@dataclass(frozen=True, slots=True)
class RunnerStatusRecord:
    """Persisted operational status for the production runner."""

    status: str
    updated_at: datetime
    last_started_at: datetime | None = None
    last_execution_at: datetime | None = None
    last_shutdown_at: datetime | None = None
    last_error: str | None = None


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


class BreakAlertReadRepository(Protocol):
    """Port for reading sent break-alert history."""

    def list_alerts(self, limit: int = 20) -> tuple[BreakAlertRecord, ...]:
        """Return recent break-alert records ordered newest first."""


class RunnerStatusRepository(Protocol):
    """Port for storing production runner operational status."""

    def save_runner_status(self, status: RunnerStatusRecord) -> None:
        """Persist the latest runner status."""

    def load_runner_status(self) -> RunnerStatusRecord | None:
        """Load the latest runner status, or return None when unavailable."""
