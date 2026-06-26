"""Tests for the read-only monitoring dashboard."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from tavan_takip.application import DashboardService
from tavan_takip.config import Settings
from tavan_takip.dashboard import create_dashboard_app
from tavan_takip.domain import IPOTrackingLifecycleState, IPOTrackingState
from tavan_takip.market import DEFAULT_MARKET_TIMEZONE
from tavan_takip.persistence import SQLiteIPOTrackingStateRepository

DASHBOARD_TIME = datetime(2026, 1, 5, 10, 30, tzinfo=DEFAULT_MARKET_TIMEZONE)


def test_dashboard_service_builds_overview_from_persisted_state(tmp_path: Path) -> None:
    repository = SQLiteIPOTrackingStateRepository(tmp_path / "dashboard.sqlite3")
    repository.save(
        IPOTrackingState(
            symbol="ALFA.IS",
            consecutive_ceiling_days=2,
            last_processed_trading_date=date(2026, 1, 5),
        )
    )
    repository.save(
        IPOTrackingState(
            symbol="BRAVO.IS",
            consecutive_ceiling_days=6,
            last_processed_trading_date=date(2026, 1, 5),
        )
    )
    repository.mark_break_alert_sent("BRAVO.IS")
    service = _make_service(
        settings=Settings(
            tracked_symbols=("ALFA.IS", "BRAVO.IS"),
            sqlite_database_path=tmp_path / "dashboard.sqlite3",
        ),
        repository=repository,
    )

    overview = service.get_overview()

    assert overview.market_session.is_open is True
    assert overview.tracked_symbol_count == 2
    assert overview.monitoring_mode_summary.early == 1
    assert overview.monitoring_mode_summary.hourly == 1
    assert overview.chart_labels == ("ALFA.IS", "BRAVO.IS")
    assert overview.chart_values == (2, 6)
    assert overview.symbols[1].alert_status == "sent"


def test_dashboard_homepage_renders_summary_and_symbols(tmp_path: Path) -> None:
    repository = SQLiteIPOTrackingStateRepository(tmp_path / "dashboard.sqlite3")
    repository.save(
        IPOTrackingState(
            symbol="ORNEK.IS",
            consecutive_ceiling_days=3,
            last_processed_trading_date=date(2026, 1, 5),
        )
    )
    client = TestClient(
        create_dashboard_app(
            dashboard_service=_make_service(
                settings=Settings(
                    tracked_symbols=("ORNEK.IS",),
                    sqlite_database_path=tmp_path / "dashboard.sqlite3",
                ),
                repository=repository,
            )
        )
    )

    response = client.get("/")

    assert response.status_code == 200
    assert "Monitoring Dashboard" in response.text
    assert "Market status" in response.text
    assert "ORNEK.IS" in response.text
    assert "Ceiling Streaks" in response.text


def test_symbols_table_partial_renders_empty_state(tmp_path: Path) -> None:
    repository = SQLiteIPOTrackingStateRepository(tmp_path / "dashboard.sqlite3")
    client = TestClient(
        create_dashboard_app(
            dashboard_service=_make_service(
                settings=Settings(
                    tracked_symbols=(),
                    sqlite_database_path=tmp_path / "dashboard.sqlite3",
                ),
                repository=repository,
            )
        )
    )

    response = client.get("/symbols/table")

    assert response.status_code == 200
    assert "No symbols configured." in response.text


def test_recent_alerts_page_renders_alert_history(tmp_path: Path) -> None:
    repository = SQLiteIPOTrackingStateRepository(tmp_path / "dashboard.sqlite3")
    repository.mark_break_alert_sent("ORNEK.IS")
    client = TestClient(
        create_dashboard_app(
            dashboard_service=_make_service(
                settings=Settings(
                    tracked_symbols=("ORNEK.IS",),
                    sqlite_database_path=tmp_path / "dashboard.sqlite3",
                ),
                repository=repository,
            )
        )
    )

    response = client.get("/alerts")

    assert response.status_code == 200
    assert "Recent Alerts" in response.text
    assert "ORNEK.IS" in response.text


def test_system_status_page_renders_runtime_status(tmp_path: Path) -> None:
    repository = SQLiteIPOTrackingStateRepository(tmp_path / "dashboard.sqlite3")
    settings = Settings(
        tracked_symbols=("ORNEK.IS",),
        sqlite_database_path=tmp_path / "dashboard.sqlite3",
        telegram_bot_token="token",
        telegram_chat_id="chat",
    )
    client = TestClient(
        create_dashboard_app(
            dashboard_service=_make_service(settings=settings, repository=repository)
        )
    )

    response = client.get("/system")

    assert response.status_code == 200
    assert "System Status" in response.text
    assert str(tmp_path / "dashboard.sqlite3") in response.text
    assert "configured" in response.text
    assert "yfinance" in response.text
    assert "not detected" in response.text


def test_dashboard_reads_broken_lifecycle_without_network(tmp_path: Path) -> None:
    repository = SQLiteIPOTrackingStateRepository(tmp_path / "dashboard.sqlite3")
    repository.save(
        IPOTrackingState(
            symbol="KIRIK.IS",
            lifecycle_state=IPOTrackingLifecycleState.CEILING_BROKEN,
            last_processed_trading_date=date(2026, 1, 5),
        )
    )
    service = _make_service(
        settings=Settings(
            tracked_symbols=("KIRIK.IS",),
            sqlite_database_path=tmp_path / "dashboard.sqlite3",
        ),
        repository=repository,
    )

    rows = service.get_symbol_rows()

    assert rows[0].lifecycle_status == IPOTrackingLifecycleState.CEILING_BROKEN.value


def _make_service(
    *,
    settings: Settings,
    repository: SQLiteIPOTrackingStateRepository,
) -> DashboardService:
    return DashboardService(
        settings=settings,
        state_repository=repository,
        alert_repository=repository,
        alert_read_repository=repository,
        now_provider=lambda: DASHBOARD_TIME,
        docker_status_provider=lambda: "not detected",
    )
