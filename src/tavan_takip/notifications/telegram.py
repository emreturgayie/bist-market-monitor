"""Telegram Bot API notification adapter."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_fixed

from tavan_takip.notifications.base import NotificationError, NotificationMessage

TELEGRAM_SEND_MESSAGE_URL = "https://api.telegram.org/bot{token}/sendMessage"
TRANSIENT_HTTP_STATUS_CODES = frozenset((429, 500, 502, 503, 504))
DEFAULT_HTTP_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """Minimal HTTP response used by TelegramNotifier."""

    status_code: int
    body: str


class TelegramHttpClient(Protocol):
    """HTTP client port for Telegram API calls."""

    def post_json(self, url: str, payload: dict[str, Any], timeout_seconds: float) -> HttpResponse:
        """POST a JSON payload and return the HTTP response."""


class UrllibTelegramHttpClient:
    """urllib-based Telegram HTTP client."""

    def post_json(self, url: str, payload: dict[str, Any], timeout_seconds: float) -> HttpResponse:
        """POST a JSON payload using the Python standard library."""
        request = Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                body = response.read().decode("utf-8")
                return HttpResponse(status_code=response.status, body=body)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return HttpResponse(status_code=exc.code, body=body)
        except URLError as exc:
            raise NotificationError(
                f"telegram request failed: {exc.reason}", transient=True
            ) from exc


class TelegramNotifier:
    """Send notification messages through the Telegram Bot API."""

    def __init__(
        self,
        *,
        bot_token: str,
        chat_id: str,
        http_client: TelegramHttpClient | None = None,
        retry_attempts: int = 3,
        retry_wait_seconds: float = 1.0,
        timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
    ) -> None:
        normalized_token = bot_token.strip()
        normalized_chat_id = chat_id.strip()
        if not normalized_token:
            raise ValueError("bot_token must not be blank")
        if not normalized_chat_id:
            raise ValueError("chat_id must not be blank")
        if retry_attempts < 1:
            raise ValueError("retry_attempts must be at least 1")
        if retry_wait_seconds < 0:
            raise ValueError("retry_wait_seconds must be greater than or equal to zero")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")

        self._bot_token = normalized_token
        self._chat_id = normalized_chat_id
        self._http_client = http_client or UrllibTelegramHttpClient()
        self._retry_attempts = retry_attempts
        self._retry_wait_seconds = retry_wait_seconds
        self._timeout_seconds = timeout_seconds

    def send(self, message: NotificationMessage) -> None:
        """Send a notification message to the configured Telegram chat."""
        retrying = Retrying(
            stop=stop_after_attempt(self._retry_attempts),
            wait=wait_fixed(self._retry_wait_seconds),
            retry=retry_if_exception(_is_transient_notification_error),
            reraise=True,
        )
        for attempt in retrying:
            with attempt:
                self._send_once(message)
                return

    def _send_once(self, message: NotificationMessage) -> None:
        payload = {
            "chat_id": self._chat_id,
            "text": format_telegram_message(message),
            "disable_web_page_preview": True,
        }
        response = self._http_client.post_json(
            TELEGRAM_SEND_MESSAGE_URL.format(token=self._bot_token),
            payload,
            self._timeout_seconds,
        )
        if 200 <= response.status_code < 300:
            return
        raise NotificationError(
            f"telegram send failed with HTTP {response.status_code}: {response.body}",
            transient=response.status_code in TRANSIENT_HTTP_STATUS_CODES,
        )


def format_telegram_message(message: NotificationMessage) -> str:
    """Format a generic notification message for Telegram."""
    return (
        f"{message.title}\n"
        f"Severity: {message.severity.value}\n\n"
        f"{message.body}\n\n"
        "Not investment advice."
    )


def _is_transient_notification_error(exc: BaseException) -> bool:
    return isinstance(exc, NotificationError) and exc.transient
