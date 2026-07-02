"""Tests for application settings."""

from typing import Any, cast

import pytest
from pydantic import ValidationError

from tavan_takip.config import DataProviderName, Settings


def test_settings_use_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable_name in (
        "TAVAN_TAKIP_TRACKED_SYMBOLS",
        "TAVAN_TAKIP_DATA_PROVIDER",
        "TAVAN_TAKIP_YFINANCE_RETRY_ATTEMPTS",
        "TAVAN_TAKIP_YFINANCE_RETRY_WAIT_SECONDS",
        "TAVAN_TAKIP_DASHBOARD_HOST",
        "TAVAN_TAKIP_DASHBOARD_PORT",
    ):
        monkeypatch.delenv(variable_name, raising=False)

    settings = Settings(**cast(dict[str, Any], {"_env_file": None}))

    assert settings.tracked_symbols == ()
    assert settings.data_provider == DataProviderName.YFINANCE
    assert settings.yfinance_retry_attempts == 3
    assert settings.yfinance_retry_wait_seconds == 1.0
    assert settings.dashboard_host == "127.0.0.1"
    assert settings.dashboard_port == 8000


def test_settings_parse_comma_separated_symbols() -> None:
    settings = Settings.model_validate({"tracked_symbols": " bist100.is, thyao.is "})

    assert settings.tracked_symbols == ("BIST100.IS", "THYAO.IS")


def test_settings_parse_data_provider_case_insensitively() -> None:
    settings = Settings.model_validate({"data_provider": " ALGOLAB_MOCK "})

    assert settings.data_provider == DataProviderName.ALGOLAB_MOCK


def test_settings_reject_invalid_data_provider() -> None:
    with pytest.raises(ValidationError, match="unsupported data_provider"):
        Settings.model_validate({"data_provider": "unknown"})
