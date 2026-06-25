"""Tests for Telegram notification delivery."""

from __future__ import annotations

from typing import Any

import pytest

from tavan_takip.notifications import (
    HttpResponse,
    NotificationError,
    NotificationMessage,
    NotificationSeverity,
    Notifier,
    TelegramNotifier,
)
from tavan_takip.notifications.telegram import format_telegram_message


class FakeTelegramHttpClient:
    """HTTP fake that records Telegram payloads."""

    def __init__(self, responses: list[HttpResponse]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, dict[str, Any], float]] = []

    def post_json(self, url: str, payload: dict[str, Any], timeout_seconds: float) -> HttpResponse:
        self.calls.append((url, payload, timeout_seconds))
        return self._responses.pop(0)


class RecordingNotifier:
    """Simple notifier implementation for protocol compatibility tests."""

    def __init__(self) -> None:
        self.messages: list[NotificationMessage] = []

    def send(self, message: NotificationMessage) -> None:
        self.messages.append(message)


def test_message_formatting_includes_disclaimer() -> None:
    message = NotificationMessage(
        title="Ceiling break alert: ORNEK.IS",
        body="Current price: 10.95",
        severity=NotificationSeverity.CRITICAL,
    )

    rendered = format_telegram_message(message)

    assert "Ceiling break alert: ORNEK.IS" in rendered
    assert "Severity: critical" in rendered
    assert "Current price: 10.95" in rendered
    assert "Not investment advice." in rendered


def test_notifier_interface_accepts_implementations() -> None:
    notifier: Notifier = RecordingNotifier()
    message = NotificationMessage(
        title="Info",
        body="System check",
        severity=NotificationSeverity.INFO,
    )

    notifier.send(message)

    assert isinstance(notifier, RecordingNotifier)
    assert notifier.messages == [message]


def test_telegram_http_call_is_made_with_json_payload() -> None:
    http_client = FakeTelegramHttpClient([HttpResponse(status_code=200, body='{"ok":true}')])
    notifier = TelegramNotifier(
        bot_token="token",
        chat_id="chat",
        http_client=http_client,
        retry_wait_seconds=0,
    )
    message = NotificationMessage(
        title="Alert",
        body="Break detected",
        severity=NotificationSeverity.CRITICAL,
    )

    notifier.send(message)

    assert len(http_client.calls) == 1
    url, payload, timeout_seconds = http_client.calls[0]
    assert url == "https://api.telegram.org/bottoken/sendMessage"
    assert payload["chat_id"] == "chat"
    assert "Break detected" in str(payload["text"])
    assert payload["disable_web_page_preview"] is True
    assert timeout_seconds == 10.0


def test_telegram_http_error_handling() -> None:
    http_client = FakeTelegramHttpClient([HttpResponse(status_code=400, body="bad request")])
    notifier = TelegramNotifier(
        bot_token="token",
        chat_id="chat",
        http_client=http_client,
        retry_attempts=2,
        retry_wait_seconds=0,
    )
    message = NotificationMessage(
        title="Alert",
        body="Break detected",
        severity=NotificationSeverity.CRITICAL,
    )

    with pytest.raises(NotificationError, match="HTTP 400"):
        notifier.send(message)

    assert len(http_client.calls) == 1


def test_telegram_retries_transient_http_errors() -> None:
    http_client = FakeTelegramHttpClient(
        [
            HttpResponse(status_code=500, body="temporary"),
            HttpResponse(status_code=200, body='{"ok":true}'),
        ]
    )
    notifier = TelegramNotifier(
        bot_token="token",
        chat_id="chat",
        http_client=http_client,
        retry_attempts=2,
        retry_wait_seconds=0,
    )
    message = NotificationMessage(
        title="Alert",
        body="Break detected",
        severity=NotificationSeverity.CRITICAL,
    )

    notifier.send(message)

    assert len(http_client.calls) == 2


@pytest.mark.parametrize(
    ("title", "body"),
    [
        ("", "body"),
        ("title", ""),
    ],
)
def test_notification_message_rejects_blank_content(title: str, body: str) -> None:
    with pytest.raises(ValueError):
        NotificationMessage(
            title=title,
            body=body,
            severity=NotificationSeverity.INFO,
        )
