"""Tests for SQLite IPO tracking state persistence."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sqlite3

from tavan_takip.domain import IPOTrackingLifecycleState, IPOTrackingState, MonitoringMode
from tavan_takip.persistence import (
    SQLiteIPOTrackingStateRepository,
    serialize_tracking_state,
)


def test_save_and_load_state(tmp_path: Path) -> None:
    repository = SQLiteIPOTrackingStateRepository(tmp_path / "tracking.sqlite3")
    state = IPOTrackingState(
        symbol="ORNEK.IS",
        consecutive_ceiling_days=3,
        last_processed_trading_date=date(2026, 1, 5),
    )

    repository.save(state)

    loaded_state = repository.load("ornek.is")
    assert loaded_state == state


def test_update_existing_state(tmp_path: Path) -> None:
    repository = SQLiteIPOTrackingStateRepository(tmp_path / "tracking.sqlite3")
    repository.save(
        IPOTrackingState(
            symbol="ORNEK.IS",
            consecutive_ceiling_days=1,
            last_processed_trading_date=date(2026, 1, 5),
        )
    )
    updated_state = IPOTrackingState(
        symbol="ORNEK.IS",
        consecutive_ceiling_days=2,
        last_processed_trading_date=date(2026, 1, 6),
    )

    repository.save(updated_state)

    assert repository.load("ORNEK.IS") == updated_state


def test_missing_state_returns_default_from_get_or_create(tmp_path: Path) -> None:
    repository = SQLiteIPOTrackingStateRepository(tmp_path / "tracking.sqlite3")

    assert repository.load("ORNEK.IS") is None
    assert repository.get_or_create(" ornek.is ") == IPOTrackingState(symbol="ORNEK.IS")


def test_load_all_states(tmp_path: Path) -> None:
    repository = SQLiteIPOTrackingStateRepository(tmp_path / "tracking.sqlite3")
    alfa_state = IPOTrackingState(symbol="ALFA.IS", consecutive_ceiling_days=1)
    bravo_state = IPOTrackingState(symbol="BRAVO.IS", consecutive_ceiling_days=6)
    repository.save(bravo_state)
    repository.save(alfa_state)

    states = repository.load_all()

    assert states == {
        "ALFA.IS": alfa_state,
        "BRAVO.IS": bravo_state,
    }
    assert states["BRAVO.IS"].monitoring_mode == MonitoringMode.HOURLY


def test_persistence_survives_new_repository_instance(tmp_path: Path) -> None:
    database_path = tmp_path / "tracking.sqlite3"
    first_repository = SQLiteIPOTrackingStateRepository(database_path)
    state = IPOTrackingState(
        symbol="ORNEK.IS",
        consecutive_ceiling_days=0,
        last_processed_trading_date=date(2026, 1, 7),
        lifecycle_state=IPOTrackingLifecycleState.CEILING_BROKEN,
    )
    first_repository.save(state)

    second_repository = SQLiteIPOTrackingStateRepository(database_path)

    assert second_repository.load("ORNEK.IS") == state


def test_serialized_state_includes_updated_timestamp_and_monitoring_mode() -> None:
    state = IPOTrackingState(symbol="ORNEK.IS", consecutive_ceiling_days=6)

    payload = serialize_tracking_state(state)

    assert payload["symbol"] == "ORNEK.IS"
    assert payload["monitoring_mode"] == MonitoringMode.HOURLY.value
    assert isinstance(payload["updated_at"], str)


def test_sqlite_row_stores_required_columns(tmp_path: Path) -> None:
    database_path = tmp_path / "tracking.sqlite3"
    repository = SQLiteIPOTrackingStateRepository(database_path)
    state = IPOTrackingState(
        symbol="ORNEK.IS",
        consecutive_ceiling_days=4,
        last_processed_trading_date=date(2026, 1, 8),
    )

    repository.save(state)

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT
                symbol,
                consecutive_ceiling_days,
                last_processed_trading_date,
                lifecycle_state,
                monitoring_mode,
                updated_at
            FROM ipo_tracking_states
            WHERE symbol = ?
            """,
            ("ORNEK.IS",),
        ).fetchone()

    assert row == (
        "ORNEK.IS",
        4,
        "2026-01-08",
        IPOTrackingLifecycleState.MONITORING.value,
        MonitoringMode.EARLY.value,
        row[5],
    )
    assert isinstance(row[5], str)
