"""Production runner entry point for continuous monitoring."""

from __future__ import annotations

import logging
import signal
from types import FrameType

from tavan_takip.application import MonitoringOrchestrator, ProductionRunner
from tavan_takip.config import Settings, get_settings
from tavan_takip.data_providers import create_data_provider
from tavan_takip.domain import IPOTrackingConfig
from tavan_takip.notifications import TelegramNotifier
from tavan_takip.persistence import SQLiteIPOTrackingStateRepository
from tavan_takip.scheduler import MonitoringSchedulePolicy


def main() -> int:
    """Run the long-running production monitoring service."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    runner = build_production_runner(get_settings())
    _install_signal_handlers(runner)
    runner.run_forever()
    return 0


def build_production_runner(settings: Settings) -> ProductionRunner:
    """Build a production runner from runtime settings."""
    repository = SQLiteIPOTrackingStateRepository(settings.sqlite_database_path)
    notifier = None
    if settings.telegram_bot_token and settings.telegram_chat_id:
        notifier = TelegramNotifier(
            bot_token=settings.telegram_bot_token,
            chat_id=settings.telegram_chat_id,
            retry_attempts=settings.telegram_retry_attempts,
            retry_wait_seconds=settings.telegram_retry_wait_seconds,
        )
    orchestrator = MonitoringOrchestrator(
        data_provider=create_data_provider(settings),
        state_repository=repository,
        alert_repository=repository,
        notifier=notifier,
    )
    return ProductionRunner(
        configs=tuple(IPOTrackingConfig(symbol=symbol) for symbol in settings.tracked_symbols),
        orchestrator=orchestrator,
        schedule_policy=MonitoringSchedulePolicy(),
        state_repository=repository,
        runner_status_repository=repository,
    )


def _install_signal_handlers(runner: ProductionRunner) -> None:
    def request_stop(signum: int, _frame: FrameType | None) -> None:
        logging.getLogger(__name__).info(
            "production_runner_stop_signal_received",
            extra={"signal": signum},
        )
        runner.request_stop()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)


if __name__ == "__main__":
    raise SystemExit(main())
