"""The worker loop: it runs work, survives failure, and never abandons a job."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy.orm import Session

from retailops_api.core.config import Settings
from retailops_api.domain.models.job import JobKind, JobState, ProcessingJob
from retailops_api.jobs import handlers, store
from retailops_api.jobs.types import JobRequest, PermanentJobError
from retailops_api.jobs.worker import Worker
from tests.job_support import borrowed_session_factory


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="test", auth_provider="local", auth_local_secret="x" * 40)


@pytest.fixture
def worker_factory(session: Session, settings: Settings):  # type: ignore[no-untyped-def]
    """A worker sharing the test's session, so its work is visible here."""

    def build(**kwargs: Any) -> Worker:
        return Worker(
            settings=settings,
            session_factory=borrowed_session_factory(session),
            idle_sleep_seconds=0,
            **kwargs,
        )

    return build


def _queue(session: Session, kind: JobKind = JobKind.forecast, key: str = "k") -> ProcessingJob:
    return store.enqueue(
        session,
        JobRequest(
            kind=kind,
            idempotency_key=key,
            request={"horizon": 4, "min_train_periods": 12},
            requested_by="Ana",
            requested_by_subject="subject-ana",
        ),
    )


@pytest.fixture
def stub_handler() -> Iterator[list[dict[str, Any]]]:
    """Replace the real pipeline: this is about the loop, not the work."""

    calls: list[dict[str, Any]] = []
    original = handlers.HANDLERS[JobKind.forecast]

    def _handler(session: Session, settings: Settings, job: ProcessingJob) -> dict[str, Any]:
        del session, settings
        calls.append(dict(job.request))
        return {"ran": True}

    handlers.HANDLERS[JobKind.forecast] = _handler
    yield calls
    handlers.HANDLERS[JobKind.forecast] = original


def test_a_queued_job_runs_and_records_its_result(
    session: Session, worker_factory: Any, stub_handler: list[dict[str, Any]]
) -> None:
    job = _queue(session)

    assert worker_factory().run_once() is True

    assert stub_handler == [{"horizon": 4, "min_train_periods": 12}]
    session.refresh(job)
    assert job.state == JobState.succeeded.value
    assert job.result == {"ran": True}


def test_an_empty_queue_is_not_an_error(worker_factory: Any) -> None:
    assert worker_factory().run_once() is False


def test_a_failure_is_recorded_and_the_worker_keeps_going(
    session: Session, worker_factory: Any
) -> None:
    job = _queue(session)
    original = handlers.HANDLERS[JobKind.forecast]

    def _boom(*_args: object, **_kwargs: object) -> dict[str, Any]:
        raise RuntimeError("provider is unhappy")

    handlers.HANDLERS[JobKind.forecast] = _boom
    try:
        worker = worker_factory()
        assert worker.run_once() is True
        # A retryable failure returns the job to the queue rather than losing it.
        session.refresh(job)
        assert job.state == JobState.queued.value
        assert "provider is unhappy" in (job.failure_reason or "")
        assert worker.run_once() is False
    finally:
        handlers.HANDLERS[JobKind.forecast] = original


def test_a_permanent_failure_is_not_retried(session: Session, worker_factory: Any) -> None:
    job = _queue(session)
    original = handlers.HANDLERS[JobKind.forecast]

    def _refuse(*_args: object, **_kwargs: object) -> dict[str, Any]:
        raise PermanentJobError("unknown supplier")

    handlers.HANDLERS[JobKind.forecast] = _refuse
    try:
        worker_factory().run_once()
    finally:
        handlers.HANDLERS[JobKind.forecast] = original

    session.refresh(job)
    assert job.state == JobState.failed.value
    assert job.failure_reason == "unknown supplier"
    assert job.attempts == 1


@pytest.mark.usefixtures("stub_handler")
def test_a_worker_only_takes_the_kinds_it_was_given(session: Session, worker_factory: Any) -> None:
    _queue(session, kind=JobKind.forecast)

    assert worker_factory(kinds=(JobKind.reconciliation,)).run_once() is False
    assert worker_factory(kinds=(JobKind.forecast,)).run_once() is True


def test_the_loop_stops_when_asked(
    session: Session, worker_factory: Any, stub_handler: list[dict[str, Any]]
) -> None:
    _queue(session, key="a")

    worker = worker_factory()
    processed = worker.run_forever(max_iterations=3)

    assert processed == 1
    assert len(stub_handler) == 1
