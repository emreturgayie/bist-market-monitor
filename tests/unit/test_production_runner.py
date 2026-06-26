"""Tests for the long-running production monitoring runner."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest

from tavan_takip.application import (
    MonitoringRunResult,
    MonitoringRunStatus,
    ProductionRunner,
    ProductionRunnerLifecycleStatus,
)
from tavan_takip.domain import IPOTrackingConfig, IPOTrackingState
from tavan_takip.market import DEFAULT_MARKET_TIMEZONE, MarketSessionEngine
from tavan_takip.persistence import RunnerStatusRecord
from tavan_takip.scheduler import NextRunDecision, ScheduleDecisionReason, ScheduleMode

RUNNER_TIME = datetime(2026, 1, 5, 10, 30, tzinfo=DEFAULT_MARKET_TIMEZONE)


class FakeStateRepository:
    """In-memory state and runner-status repository for runner tests."""

    def __init__(self, states: dict[str, IPOTrackingState] | None = None) -> None:
        self._states = states or {}
        self.runner_status: RunnerStatusRecord | None = None

    def save(self, state: IPOTrackingState) -> None:
        self._states[state.symbol] = state

    def load(self, symbol: str) -> IPOTrackingState | None:
        return self._states.get(symbol.strip().upper())

    def get_or_create(self, symbol: str) -> IPOTrackingState:
        normalized_symbol = symbol.strip().upper()
        state = self._states.get(normalized_symbol)
        if state is None:
            state = IPOTrackingState(symbol=normalized_symbol)
            self._states[normalized_symbol] = state
        return state

    def load_all(self) -> dict[str, IPOTrackingState]:
        return dict(self._states)

    def save_runner_status(self, status: RunnerStatusRecord) -> None:
        self.runner_status = status

    def load_runner_status(self) -> RunnerStatusRecord | None:
        return self.runner_status


@dataclass(slots=True)
class FakeOrchestrator:
    """Orchestrator fake that records calls and can fail once."""

    fail_once: bool = False
    calls: list[tuple[datetime, tuple[str, ...]]] | None = None

    def __post_init__(self) -> None:
        self.calls = []

    def run(
        self,
        *,
        checked_at: datetime,
        configs: Sequence[IPOTrackingConfig],
    ) -> MonitoringRunResult:
        if self.calls is None:
            raise AssertionError("calls list is not initialized")
        symbols = tuple(config.symbol for config in configs)
        self.calls.append((checked_at, symbols))
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("transient provider outage")
        return MonitoringRunResult(
            status=MonitoringRunStatus.COMPLETED,
            market_session=MarketSessionEngine().evaluate(checked_at),
            symbol_results=(),
            missing_symbols=(),
        )


class DueOnceSchedulePolicy:
    """Schedule policy fake that is due until a symbol has a last run timestamp."""

    def decide(
        self,
        *,
        state: IPOTrackingState,
        checked_at: datetime,
        last_run_at: datetime | None = None,
    ) -> NextRunDecision:
        if last_run_at is None:
            return _decision(
                state=state,
                checked_at=checked_at,
                next_run_at=checked_at,
                should_run_now=True,
            )
        return _decision(
            state=state,
            checked_at=checked_at,
            next_run_at=checked_at + timedelta(minutes=30),
            should_run_now=False,
        )


class WaitingSchedulePolicy:
    """Schedule policy fake that always waits for a future run."""

    def decide(
        self,
        *,
        state: IPOTrackingState,
        checked_at: datetime,
        last_run_at: datetime | None = None,
    ) -> NextRunDecision:
        return _decision(
            state=state,
            checked_at=checked_at,
            next_run_at=checked_at + timedelta(minutes=15),
            should_run_now=False,
            reason=ScheduleDecisionReason.WAITING_FOR_NEXT_WINDOW,
        )


def test_runner_executes_due_symbols_and_records_execution() -> None:
    repository = FakeStateRepository()
    orchestrator = FakeOrchestrator()
    runner = _make_runner(
        repository=repository,
        orchestrator=orchestrator,
        schedule_policy=DueOnceSchedulePolicy(),
    )

    result = runner.run_once()

    assert result.due_symbols == ("ORNEK.IS",)
    assert result.sleep_seconds == 30 * 60
    assert orchestrator.calls == [(RUNNER_TIME, ("ORNEK.IS",))]
    assert repository.runner_status is not None
    assert repository.runner_status.status == ProductionRunnerLifecycleStatus.RUNNING.value
    assert repository.runner_status.last_execution_at == RUNNER_TIME


def test_runner_waits_until_next_scheduled_run_when_nothing_is_due() -> None:
    repository = FakeStateRepository()
    orchestrator = FakeOrchestrator()
    runner = _make_runner(
        repository=repository,
        orchestrator=orchestrator,
        schedule_policy=WaitingSchedulePolicy(),
    )

    result = runner.run_once()

    assert result.due_symbols == ()
    assert result.next_run_at == RUNNER_TIME + timedelta(minutes=15)
    assert result.sleep_seconds == 15 * 60
    assert orchestrator.calls == []


def test_runner_handles_iteration_error_and_can_continue() -> None:
    repository = FakeStateRepository()
    orchestrator = FakeOrchestrator(fail_once=True)
    runner = _make_runner(
        repository=repository,
        orchestrator=orchestrator,
        schedule_policy=DueOnceSchedulePolicy(),
    )

    first_result = runner.run_once()
    assert repository.runner_status is not None
    assert repository.runner_status.status == ProductionRunnerLifecycleStatus.ERROR.value

    second_result = runner.run_once()

    assert first_result.error_message == "transient provider outage"
    assert repository.runner_status is not None
    assert repository.runner_status.status == ProductionRunnerLifecycleStatus.RUNNING.value
    assert second_result.monitoring_result is not None
    assert second_result.error_message is None


def test_runner_idle_when_no_symbols_are_configured() -> None:
    repository = FakeStateRepository()
    runner = ProductionRunner(
        configs=(),
        orchestrator=FakeOrchestrator(),
        schedule_policy=WaitingSchedulePolicy(),
        state_repository=repository,
        runner_status_repository=repository,
        now_provider=lambda: RUNNER_TIME,
        sleep_function=lambda _: None,
    )

    result = runner.run_once()

    assert result.due_symbols == ()
    assert result.sleep_seconds == 60
    assert repository.runner_status is not None
    assert repository.runner_status.status == ProductionRunnerLifecycleStatus.IDLE.value


def test_runner_stops_cleanly_on_keyboard_interrupt_without_real_sleep() -> None:
    repository = FakeStateRepository()

    def interrupting_sleep(_: float) -> None:
        raise KeyboardInterrupt

    runner = _make_runner(
        repository=repository,
        orchestrator=FakeOrchestrator(),
        schedule_policy=WaitingSchedulePolicy(),
        sleep_function=interrupting_sleep,
    )

    runner.run_forever()

    assert repository.runner_status is not None
    assert repository.runner_status.status == ProductionRunnerLifecycleStatus.STOPPED.value
    assert repository.runner_status.last_shutdown_at == RUNNER_TIME


def test_runner_rejects_invalid_max_iterations() -> None:
    runner = _make_runner(
        repository=FakeStateRepository(),
        orchestrator=FakeOrchestrator(),
        schedule_policy=WaitingSchedulePolicy(),
    )

    with pytest.raises(ValueError, match="max_iterations"):
        runner.run_forever(max_iterations=0)


def _make_runner(
    *,
    repository: FakeStateRepository,
    orchestrator: FakeOrchestrator,
    schedule_policy: DueOnceSchedulePolicy | WaitingSchedulePolicy,
    sleep_function: Callable[[float], None] | None = None,
) -> ProductionRunner:
    return ProductionRunner(
        configs=(IPOTrackingConfig(symbol="ORNEK.IS"),),
        orchestrator=orchestrator,
        schedule_policy=schedule_policy,
        state_repository=repository,
        runner_status_repository=repository,
        now_provider=lambda: RUNNER_TIME,
        sleep_function=sleep_function or (lambda _: None),
    )


def _decision(
    *,
    state: IPOTrackingState,
    checked_at: datetime,
    next_run_at: datetime,
    should_run_now: bool,
    reason: ScheduleDecisionReason = ScheduleDecisionReason.DUE_IN_CURRENT_WINDOW,
) -> NextRunDecision:
    return NextRunDecision(
        symbol=state.symbol,
        schedule_mode=ScheduleMode.EARLY,
        reason=reason,
        checked_at=checked_at,
        next_run_at=next_run_at,
        should_run_now=should_run_now,
    )
