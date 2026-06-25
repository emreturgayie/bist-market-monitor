"""SQLite-backed persistence for IPO tracking state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
import sqlite3
from typing import Any

from tavan_takip.domain import IPOTrackingLifecycleState, IPOTrackingState


@dataclass(frozen=True, slots=True)
class SQLiteConnectionManager:
    """Create SQLite connections for a local database path."""

    database_path: Path

    def connect(self) -> sqlite3.Connection:
        """Return a configured SQLite connection."""
        if str(self.database_path) != ":memory:":
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection


class SQLiteIPOTrackingStateRepository:
    """SQLite implementation of IPO tracking state persistence."""

    def __init__(self, database_path: Path | str) -> None:
        self._connection_manager = SQLiteConnectionManager(Path(database_path))
        self.initialize()

    def initialize(self) -> None:
        """Create required tables when they do not already exist."""
        with self._connection_manager.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS ipo_tracking_states (
                    symbol TEXT PRIMARY KEY,
                    consecutive_ceiling_days INTEGER NOT NULL,
                    last_processed_trading_date TEXT,
                    lifecycle_state TEXT NOT NULL,
                    monitoring_mode TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)

    def save(self, state: IPOTrackingState) -> None:
        """Persist a tracking state, updating the row when it already exists."""
        payload = serialize_tracking_state(state)
        with self._connection_manager.connect() as connection:
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
                VALUES (
                    :symbol,
                    :consecutive_ceiling_days,
                    :last_processed_trading_date,
                    :lifecycle_state,
                    :monitoring_mode,
                    :updated_at
                )
                ON CONFLICT(symbol) DO UPDATE SET
                    consecutive_ceiling_days = excluded.consecutive_ceiling_days,
                    last_processed_trading_date = excluded.last_processed_trading_date,
                    lifecycle_state = excluded.lifecycle_state,
                    monitoring_mode = excluded.monitoring_mode,
                    updated_at = excluded.updated_at
                """,
                payload,
            )

    def load(self, symbol: str) -> IPOTrackingState | None:
        """Load a tracking state by symbol, or return None when it is missing."""
        normalized_symbol = _normalize_symbol(symbol)
        with self._connection_manager.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    symbol,
                    consecutive_ceiling_days,
                    last_processed_trading_date,
                    lifecycle_state
                FROM ipo_tracking_states
                WHERE symbol = ?
                """,
                (normalized_symbol,),
            ).fetchone()
        if row is None:
            return None
        return deserialize_tracking_state(row)

    def get_or_create(self, symbol: str) -> IPOTrackingState:
        """Load a tracking state or return a default state when it is missing."""
        existing_state = self.load(symbol)
        if existing_state is not None:
            return existing_state
        return IPOTrackingState(symbol=symbol)

    def load_all(self) -> dict[str, IPOTrackingState]:
        """Load all persisted tracking states keyed by symbol."""
        with self._connection_manager.connect() as connection:
            rows = connection.execute("""
                SELECT
                    symbol,
                    consecutive_ceiling_days,
                    last_processed_trading_date,
                    lifecycle_state
                FROM ipo_tracking_states
                ORDER BY symbol
                """).fetchall()
        states = [deserialize_tracking_state(row) for row in rows]
        return {state.symbol: state for state in states}


def serialize_tracking_state(state: IPOTrackingState) -> dict[str, Any]:
    """Serialize a domain tracking state for SQLite storage."""
    return {
        "symbol": state.symbol,
        "consecutive_ceiling_days": state.consecutive_ceiling_days,
        "last_processed_trading_date": (
            state.last_processed_trading_date.isoformat()
            if state.last_processed_trading_date is not None
            else None
        ),
        "lifecycle_state": state.lifecycle_state.value,
        "monitoring_mode": state.monitoring_mode.value,
        "updated_at": datetime.now(UTC).isoformat(),
    }


def deserialize_tracking_state(row: sqlite3.Row) -> IPOTrackingState:
    """Deserialize a SQLite row into a domain tracking state."""
    last_processed_value = row["last_processed_trading_date"]
    return IPOTrackingState(
        symbol=str(row["symbol"]),
        consecutive_ceiling_days=int(row["consecutive_ceiling_days"]),
        last_processed_trading_date=(
            date.fromisoformat(str(last_processed_value))
            if last_processed_value is not None
            else None
        ),
        lifecycle_state=IPOTrackingLifecycleState(str(row["lifecycle_state"])),
    )


def _normalize_symbol(symbol: str) -> str:
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol must not be blank")
    return normalized_symbol
