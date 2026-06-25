"""Notification abstractions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class NotificationSeverity(StrEnum):
    """Severity level for outbound notifications."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class NotificationMessage:
    """Structured notification message independent of any delivery channel."""

    title: str
    body: str
    severity: NotificationSeverity

    def __post_init__(self) -> None:
        """Validate message content."""
        if not self.title.strip():
            raise ValueError("title must not be blank")
        if not self.body.strip():
            raise ValueError("body must not be blank")


class NotificationError(RuntimeError):
    """Raised when a notifier cannot deliver a message."""

    def __init__(self, message: str, *, transient: bool = False) -> None:
        super().__init__(message)
        self.transient = transient


class Notifier(Protocol):
    """Port for delivering notification messages."""

    def send(self, message: NotificationMessage) -> None:
        """Deliver a notification message."""
