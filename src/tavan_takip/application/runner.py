"""Long-running production monitoring runner."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
import logging
from threading import Event
from typing import Protocol

from tavan_takip.application.monitoring import MonitoringRunResult
from tavan_takip.domain import IPOTrackingConfig, IPOTrackingState
from tavan_takip.market import DEFAULT_MARKET_TIMEZONE
from tavan_takip.persistence import (
    IPOTrackingStateRepository,
    RunnerStatusRecord,
    RunnerStatusRepository,
)
from tavan_takip.scheduler import MonitoringSchedulePolicy, NextRunDecision

DEFAULT_IDLE_SLEEP_SECONDS = 60.0
MINIMUM_SLEEP_SECONDS = 1.0

logger = logging.getLogger(__name__)

NowProvider = Callable[[], datetime]
SleepFunction = Callable[[float], None]


class ProductionRunnerLifecycleStatus(StrEnum):
    """Persisted lifecycle status for the production runner."""

    RUNNING = "running"
    IDLE = "idle"
    STOPPED = "stopped"
    ERROR = "error"


class RunnerOrchestrator(Protocol):
    """Protocol for the monitoring orchestrator used by the runner."""

    def run(
        self,
        *,
        checked_at: datetime,
        configs: Sequence[IPOTrackingConfig],
    ) -> MonitoringRunResult:
        """Execute one monitoring run."""


class RunnerSchedulePolicy(Protocol):
    """Protocol for schedule decisions used by the runner."""

    def decide(
        self,
        *,
        state: IPOTrackingState,
        checked_at: datetime,
        last_run_at: datetime | None = None,
    ) -> NextRunDecision:
        """Return the next monitoring decision for one tracked state."""


@dataclass(frozen=True, slots=True)
class ProductionRunnerIterationResult:
    """Result of one production runner loop iteration."""

    checked_at: datetime
    due_symbols: tuple[str, ...]
    next_run_at: datetime
    sleep_seconds: float
    monitoring_result: MonitoringRunResult | None = None
    error_message: str | None = None


class ProductionRunner:
    """Run monitoring continuously using the existing scheduler and orchestrator."""

    def __init__(
        self,
        *,
        configs: Sequence[IPOTrackingConfig],
        orchestrator: RunnerOrchestrator,
        schedule_policy: RunnerSchedulePolicy | None,
        state_repository: IPOTrackingStateRepository,
        runner_status_repository: RunnerStatusRepository,
        now_provider: NowProvider | None = None,
        sleep_function: SleepFunction | None = None,
    ) -> None:
        self._configs = tuple(configs)
        self._orchestrator = orchestrator
        self._schedule_policy = schedule_policy or MonitoringSchedulePolicy()
        self._state_repository = state_repository
        self._runner_status_repository = runner_status_repository
        self._now_provider = now_provider or _default_now
        self._sleep_function = sleep_function
        self._last_run_at_by_symbol: dict[str, datetime] = {}
        self._stop_event = Event()

    def request_stop(self) -> None:
        """Ask the runner to stop after the current loop iteration."""
        self._stop_event.set()

    def run_forever(self, *, max_iterations: int | None = None) -> None:
        """Run monitoring until stopped or interrupted."""
        if max_iterations is not None and max_iterations < 1:
            raise ValueError("max_iterations must be greater than zero")

        started_at = self._now_provider()
        self._save_status(
            ProductionRunnerLifecycleStatus.RUNNING,
            updated_at=started_at,
            last_started_at=started_at,
            clear_error=True,
        )
        logger.info(
            "production_runner_started",
            extra={"configured_symbols": len(self._configs)},
        )

        iterations = 0
        try:
            while not self._stop_event.is_set():
                iteration_result = self.run_once()
                iterations += 1
                if max_iterations is not None and iterations >= max_iterations:
                    break
                self._sleep(iteration_result.sleep_seconds)
        except KeyboardInterrupt:
            logger.info("production_runner_interrupt_received")
        finally:
            stopped_at = self._now_provider()
            self._save_status(
                ProductionRunnerLifecycleStatus.STOPPED,
                updated_at=stopped_at,
                last_shutdown_at=stopped_at,
            )
            logger.info("production_runner_stopped")

    def _sleep(self, seconds: float) -> None:
        if self._sleep_function is not None:
            self._sleep_function(seconds)
            return
        self._stop_event.wait(seconds)

    def run_once(self) -> ProductionRunnerIterationResult:
        """Execute one scheduler-aware runner iteration."""
        checked_at = self._now_provider()
        if not self._configs:
            next_run_at = checked_at + timedelta(seconds=DEFAULT_IDLE_SLEEP_SECONDS)
            self._save_status(
                ProductionRunnerLifecycleStatus.IDLE,
                updated_at=checked_at,
                clear_error=True,
            )
            logger.warning("production_runner_no_symbols_configured")
            return ProductionRunnerIterationResult(
                checked_at=checked_at,
                due_symbols=(),
                next_run_at=next_run_at,
                sleep_seconds=DEFAULT_IDLE_SLEEP_SECONDS,
            )

        decisions = self._decide(checked_at)
        due_configs = _due_configs(self._configs, decisions)
        if not due_configs:
            next_run_at = _earliest_next_run(decisions, checked_at)
            sleep_seconds = _sleep_seconds_until(checked_at, next_run_at)
            self._save_status(
                ProductionRunnerLifecycleStatus.RUNNING,
                updated_at=checked_at,
                clear_error=True,
            )
            logger.info(
                "production_runner_waiting",
                extra={
                    "next_run_at": next_run_at.isoformat(),
                    "sleep_seconds": sleep_seconds,
                },
            )
            return ProductionRunnerIterationResult(
                checked_at=checked_at,
                due_symbols=(),
                next_run_at=next_run_at,
                sleep_seconds=sleep_seconds,
            )

        due_symbols = tuple(config.symbol for config in due_configs)
        try:
            monitoring_result = self._orchestrator.run(
                checked_at=checked_at,
                configs=due_configs,
            )
        except Exception as exc:
            next_run_at = _earliest_next_run(decisions, checked_at)
            sleep_seconds = _sleep_seconds_until(checked_at, next_run_at)
            error_message = str(exc)
            self._save_status(
                ProductionRunnerLifecycleStatus.ERROR,
                updated_at=checked_at,
                last_error=error_message,
            )
            logger.exception(
                "production_runner_iteration_failed",
                extra={"due_symbols": due_symbols},
            )
            return ProductionRunnerIterationResult(
                checked_at=checked_at,
                due_symbols=due_symbols,
                next_run_at=next_run_at,
                sleep_seconds=sleep_seconds,
                error_message=error_message,
            )

        for symbol in due_symbols:
            self._last_run_at_by_symbol[symbol] = checked_at
        self._save_status(
            ProductionRunnerLifecycleStatus.RUNNING,
            updated_at=checked_at,
            last_execution_at=checked_at,
            clear_error=True,
        )
        logger.info(
            "production_runner_iteration_completed",
            extra={"due_symbols": due_symbols},
        )

        next_decisions = self._decide(checked_at)
        next_run_at = _earliest_next_run(next_decisions, checked_at)
        return ProductionRunnerIterationResult(
            checked_at=checked_at,
            due_symbols=due_symbols,
            next_run_at=next_run_at,
            sleep_seconds=_sleep_seconds_until(checked_at, next_run_at),
            monitoring_result=monitoring_result,
        )

    def _decide(self, checked_at: datetime) -> tuple[NextRunDecision, ...]:
        decisions: list[NextRunDecision] = []
        for config in self._configs:
            state = self._state_repository.get_or_create(config.symbol)
            decisions.append(
                self._schedule_policy.decide(
                    state=state,
                    checked_at=checked_at,
                    last_run_at=self._last_run_at_by_symbol.get(config.symbol),
                )
            )
        return tuple(decisions)

    def _save_status(
        self,
        status: ProductionRunnerLifecycleStatus,
        *,
        updated_at: datetime,
        last_started_at: datetime | None = None,
        last_execution_at: datetime | None = None,
        last_shutdown_at: datetime | None = None,
        last_error: str | None = None,
        clear_error: bool = False,
    ) -> None:
        previous = self._runner_status_repository.load_runner_status()
        self._runner_status_repository.save_runner_status(
            RunnerStatusRecord(
                status=status.value,
                last_started_at=last_started_at
                or (previous.last_started_at if previous is not None else None),
                last_execution_at=last_execution_at
                or (previous.last_execution_at if previous is not None else None),
                last_shutdown_at=last_shutdown_at
                or (previous.last_shutdown_at if previous is not None else None),
                last_error=(
                    None
                    if clear_error
                    else (
                        last_error
                        if last_error is not None
                        else (previous.last_error if previous is not None else None)
                    )
                ),
                updated_at=updated_at,
            )
        )


def _default_now() -> datetime:
    return datetime.now(DEFAULT_MARKET_TIMEZONE)


def _due_configs(
    configs: tuple[IPOTrackingConfig, ...],
    decisions: tuple[NextRunDecision, ...],
) -> tuple[IPOTrackingConfig, ...]:
    due_symbols = {decision.symbol for decision in decisions if decision.should_run_now}
    return tuple(config for config in configs if config.symbol in due_symbols)


def _earliest_next_run(
    decisions: tuple[NextRunDecision, ...],
    fallback_time: datetime,
) -> datetime:
    if not decisions:
        return fallback_time + timedelta(seconds=DEFAULT_IDLE_SLEEP_SECONDS)
    return min(decision.next_run_at for decision in decisions)


def _sleep_seconds_until(checked_at: datetime, next_run_at: datetime) -> float:
    seconds = (next_run_at - checked_at).total_seconds()
    return max(seconds, MINIMUM_SLEEP_SECONDS)
