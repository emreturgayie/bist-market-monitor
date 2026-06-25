"""SQLite-backed persistence for IPO tracking state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
import sqlite3
from typing import Any

from tavan_takip.domain import IPOTrackingLifecycleState, IPOTrackingState

CURRENT_SCHEMA_VERSION = 1
VALID_LIFECYCLE_STATES = tuple(state.value for state in IPOTrackingLifecycleState)
VALID_MONITORING_MODES = ("early", "hourly")


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
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER NOT NULL CHECK (version >= 0)
                )
                """)
            current_version = _get_schema_version(connection)
            if current_version > CURRENT_SCHEMA_VERSION:
                raise RuntimeError("database schema version is newer than this application")
            if current_version < 1:
                _migrate_to_v1(connection)
                _set_schema_version(connection, 1)

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

    def has_break_alert_been_sent(self, symbol: str) -> bool:
        """Return whether a break alert has been sent for the current broken state."""
        normalized_symbol = _normalize_symbol(symbol)
        with self._connection_manager.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM break_alerts WHERE symbol = ?",
                (normalized_symbol,),
            ).fetchone()
        return row is not None

    def mark_break_alert_sent(self, symbol: str) -> None:
        """Record that a break alert was sent for the current broken state."""
        normalized_symbol = _normalize_symbol(symbol)
        with self._connection_manager.connect() as connection:
            connection.execute(
                """
                INSERT INTO break_alerts (symbol, sent_at)
                VALUES (?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    sent_at = excluded.sent_at
                """,
                (normalized_symbol, datetime.now(UTC).isoformat()),
            )

    def clear_break_alert(self, symbol: str) -> None:
        """Clear a sent break-alert marker for a symbol."""
        normalized_symbol = _normalize_symbol(symbol)
        with self._connection_manager.connect() as connection:
            connection.execute("DELETE FROM break_alerts WHERE symbol = ?", (normalized_symbol,))


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


def _get_schema_version(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    if row is None:
        return 0
    return int(row["version"])


def _set_schema_version(connection: sqlite3.Connection, version: int) -> None:
    connection.execute("DELETE FROM schema_version")
    connection.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))


def _migrate_to_v1(connection: sqlite3.Connection) -> None:
    existing_tracking_table = _table_exists(connection, "ipo_tracking_states")
    connection.execute("DROP TABLE IF EXISTS ipo_tracking_states_new")
    connection.execute(f"""
        CREATE TABLE ipo_tracking_states_new (
            symbol TEXT PRIMARY KEY CHECK (length(trim(symbol)) > 0),
            consecutive_ceiling_days INTEGER NOT NULL CHECK (consecutive_ceiling_days >= 0),
            last_processed_trading_date TEXT,
            lifecycle_state TEXT NOT NULL CHECK (lifecycle_state IN {VALID_LIFECYCLE_STATES}),
            monitoring_mode TEXT NOT NULL CHECK (monitoring_mode IN {VALID_MONITORING_MODES}),
            updated_at TEXT NOT NULL
        )
        """)
    if existing_tracking_table:
        connection.execute("""
            INSERT INTO ipo_tracking_states_new (
                symbol,
                consecutive_ceiling_days,
                last_processed_trading_date,
                lifecycle_state,
                monitoring_mode,
                updated_at
            )
            SELECT
                symbol,
                consecutive_ceiling_days,
                last_processed_trading_date,
                lifecycle_state,
                monitoring_mode,
                updated_at
            FROM ipo_tracking_states
            """)
        connection.execute("DROP TABLE ipo_tracking_states")
    connection.execute("ALTER TABLE ipo_tracking_states_new RENAME TO ipo_tracking_states")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS break_alerts (
            symbol TEXT PRIMARY KEY CHECK (length(trim(symbol)) > 0),
            sent_at TEXT NOT NULL
        )
        """)


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None
