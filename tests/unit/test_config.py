"""Tests for application settings."""

from tavan_takip.config import Settings


def test_settings_use_safe_defaults() -> None:
    settings = Settings()

    assert settings.tracked_symbols == ()
    assert settings.yfinance_retry_attempts == 3
    assert settings.yfinance_retry_wait_seconds == 1.0


def test_settings_parse_comma_separated_symbols() -> None:
    settings = Settings.model_validate({"tracked_symbols": " bist100.is, thyao.is "})

    assert settings.tracked_symbols == ("BIST100.IS", "THYAO.IS")
