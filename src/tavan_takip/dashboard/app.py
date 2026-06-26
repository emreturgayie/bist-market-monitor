"""FastAPI dashboard for monitoring persisted IPO tracking state."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from tavan_takip.application import DashboardService
from tavan_takip.config import Settings, get_settings
from tavan_takip.market import MarketSessionEngine
from tavan_takip.persistence import SQLiteIPOTrackingStateRepository

PACKAGE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(PACKAGE_DIR / "templates"))


def create_dashboard_app(
    dashboard_service: DashboardService | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    """Create the FastAPI dashboard application."""
    resolved_settings = settings or get_settings()
    service = dashboard_service or _build_dashboard_service(resolved_settings)
    app = FastAPI(title="BIST Market Monitor Dashboard")
    app.mount("/static", StaticFiles(directory=str(PACKAGE_DIR / "static")), name="static")

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> HTMLResponse:
        overview = service.get_overview()
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"overview": overview},
        )

    @app.get("/symbols/table", response_class=HTMLResponse)
    def symbols_table(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="symbols_table.html",
            context={"symbols": service.get_symbol_rows()},
        )

    @app.get("/alerts", response_class=HTMLResponse)
    def recent_alerts(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="alerts.html",
            context={"view": service.get_recent_alerts()},
        )

    @app.get("/system", response_class=HTMLResponse)
    def system_status(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="system.html",
            context={"view": service.get_system_status()},
        )

    return app


def main() -> int:
    """Run the dashboard with Uvicorn."""
    settings = get_settings()
    uvicorn.run(
        "tavan_takip.dashboard.app:create_dashboard_app",
        factory=True,
        host=settings.dashboard_host,
        port=settings.dashboard_port,
    )
    return 0


def _build_dashboard_service(settings: Settings) -> DashboardService:
    repository = SQLiteIPOTrackingStateRepository(settings.sqlite_database_path)
    return DashboardService(
        settings=settings,
        state_repository=repository,
        alert_repository=repository,
        alert_read_repository=repository,
        market_session_engine=MarketSessionEngine(),
        data_provider_name=settings.data_provider.value,
    )
