"""Application configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from enum import StrEnum

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DataProviderName(StrEnum):
    """Supported market data provider adapters."""

    YFINANCE = "yfinance"
    ALGOLAB_MOCK = "algolab_mock"


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and optional .env files."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TAVAN_TAKIP_",
        extra="ignore",
    )

    tracked_symbols: tuple[str, ...] = Field(default_factory=tuple)
    data_provider: DataProviderName = DataProviderName.YFINANCE
    yfinance_retry_attempts: int = Field(default=3, ge=1)
    yfinance_retry_wait_seconds: float = Field(default=1.0, ge=0)
    sqlite_database_path: Path = Path("tavan_takip.sqlite3")
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    telegram_retry_attempts: int = Field(default=3, ge=1)
    telegram_retry_wait_seconds: float = Field(default=1.0, ge=0)
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = Field(default=8000, ge=1, le=65535)

    @field_validator("tracked_symbols", mode="before")
    @classmethod
    def parse_tracked_symbols(cls, value: object) -> object:
        """Support comma-separated symbols in addition to native list values."""
        if isinstance(value, str):
            return tuple(symbol.strip().upper() for symbol in value.split(",") if symbol.strip())
        if isinstance(value, list | tuple | set):
            return tuple(str(symbol).strip().upper() for symbol in value if str(symbol).strip())
        return value

    @field_validator("data_provider", mode="before")
    @classmethod
    def parse_data_provider(cls, value: object) -> object:
        """Normalize and validate the configured data provider name."""
        if isinstance(value, DataProviderName):
            return value
        if isinstance(value, str):
            normalized_value = value.strip().lower()
            supported_values = {provider.value for provider in DataProviderName}
            if normalized_value in supported_values:
                return normalized_value
        expected_values = ", ".join(provider.value for provider in DataProviderName)
        raise ValueError(f"unsupported data_provider; expected one of: {expected_values}")


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
