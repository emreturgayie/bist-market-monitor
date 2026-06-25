"""Application configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and optional .env files."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TAVAN_TAKIP_",
        extra="ignore",
    )

    tracked_symbols: tuple[str, ...] = Field(default_factory=tuple)
    yfinance_retry_attempts: int = Field(default=3, ge=1)
    yfinance_retry_wait_seconds: float = Field(default=1.0, ge=0)
    sqlite_database_path: Path = Path("tavan_takip.sqlite3")

    @field_validator("tracked_symbols", mode="before")
    @classmethod
    def parse_tracked_symbols(cls, value: object) -> object:
        """Support comma-separated symbols in addition to native list values."""
        if isinstance(value, str):
            return tuple(symbol.strip().upper() for symbol in value.split(",") if symbol.strip())
        if isinstance(value, list | tuple | set):
            return tuple(str(symbol).strip().upper() for symbol in value if str(symbol).strip())
        return value


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
