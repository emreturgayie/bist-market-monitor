"""Tests for SQLite IPO tracking state persistence."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sqlite3

import pytest

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


def test_schema_version_is_initialized(tmp_path: Path) -> None:
    database_path = tmp_path / "tracking.sqlite3"

    SQLiteIPOTrackingStateRepository(database_path)

    with sqlite3.connect(database_path) as connection:
        version = connection.execute("SELECT version FROM schema_version").fetchone()[0]

    assert version == 1


def test_tracking_state_constraints_are_enforced(tmp_path: Path) -> None:
    database_path = tmp_path / "tracking.sqlite3"
    SQLiteIPOTrackingStateRepository(database_path)

    with sqlite3.connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO ipo_tracking_states (
                    symbol,
                    consecutive_ceiling_days,
                    lifecycle_state,
                    monitoring_mode,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                ("BAD.IS", -1, "monitoring", "early", "2026-01-01T00:00:00+00:00"),
            )


def test_legacy_database_is_migrated_to_versioned_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute("""
            CREATE TABLE ipo_tracking_states (
                symbol TEXT PRIMARY KEY,
                consecutive_ceiling_days INTEGER NOT NULL,
                last_processed_trading_date TEXT,
                lifecycle_state TEXT NOT NULL,
                monitoring_mode TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """)
        connection.execute(
            """
            INSERT INTO ipo_tracking_states (
                symbol,
                consecutive_ceiling_days,
                last_processed_trading_date,
                lifecycle_state,
                monitoring_mode,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "ORNEK.IS",
                2,
                "2026-01-05",
                IPOTrackingLifecycleState.MONITORING.value,
                MonitoringMode.EARLY.value,
                "2026-01-05T12:00:00+00:00",
            ),
        )

    repository = SQLiteIPOTrackingStateRepository(database_path)

    assert repository.load("ORNEK.IS") == IPOTrackingState(
        symbol="ORNEK.IS",
        consecutive_ceiling_days=2,
        last_processed_trading_date=date(2026, 1, 5),
    )
    with sqlite3.connect(database_path) as connection:
        version = connection.execute("SELECT version FROM schema_version").fetchone()[0]
        break_alert_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'break_alerts'"
        ).fetchone()
    assert version == 1
    assert break_alert_table is not None


def test_break_alert_dedupe_state_can_be_marked_and_cleared(tmp_path: Path) -> None:
    repository = SQLiteIPOTrackingStateRepository(tmp_path / "tracking.sqlite3")

    assert repository.has_break_alert_been_sent("ORNEK.IS") is False

    repository.mark_break_alert_sent(" ornek.is ")

    assert repository.has_break_alert_been_sent("ORNEK.IS") is True

    repository.clear_break_alert("ORNEK.IS")

    assert repository.has_break_alert_been_sent("ORNEK.IS") is False
