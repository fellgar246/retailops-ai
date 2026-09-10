"""Job persistence: idempotency, mutual exclusion, leases and retries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from retailops_api.domain.models.job import JobKind, JobState
from retailops_api.jobs import store
from retailops_api.jobs.types import JobConflictError, JobRequest, JobValidationError

NOW = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)


def _request(key: str = "key-1", **overrides: object) -> JobRequest:
    values: dict[str, object] = {
        "kind": JobKind.document_intake,
        "idempotency_key": key,
        "request": {"supplier_code": "SUP-1"},
        "requested_by": "Ana",
        "requested_by_subject": "subject-ana",
    }
    values.update(overrides)
    return JobRequest(**values)  # type: ignore[arg-type]


def test_a_job_starts_queued_and_records_who_asked(session: Session) -> None:
    job = store.enqueue(session, _request(), now=NOW)

    assert job.state == JobState.queued.value
    assert job.attempts == 0
    assert job.requested_by == "Ana"
    assert store.job_view(job).requested_by_verified is True


def test_the_same_key_returns_the_original_job(session: Session) -> None:
    """A double-clicked button must not pay for the work twice."""

    first = store.enqueue(session, _request("same"), now=NOW)
    second = store.enqueue(session, _request("same"), now=NOW)

    assert second.id == first.id


def test_the_same_key_under_another_kind_is_a_different_job(session: Session) -> None:
    first = store.enqueue(session, _request("shared"), now=NOW)
    second = store.enqueue(session, _request("shared", kind=JobKind.reconciliation), now=NOW)

    assert second.id != first.id


def test_a_key_is_required(session: Session) -> None:
    with pytest.raises(JobValidationError):
        store.enqueue(session, _request("   "), now=NOW)


def test_claiming_marks_the_job_running_and_counts_the_attempt(session: Session) -> None:
    job = store.enqueue(session, _request(), now=NOW)

    lease = store.claim(session, now=NOW)

    assert lease is not None
    assert lease.job_id == job.id
    session.refresh(job)
    assert job.state == JobState.running.value
    assert job.attempts == 1
    assert job.started_at is not None


def test_two_workers_never_hold_the_same_job(session: Session) -> None:
    """The second claim must find nothing, not the same row."""

    store.enqueue(session, _request(), now=NOW)

    first = store.claim(session, now=NOW)
    second = store.claim(session, now=NOW)

    assert first is not None
    assert second is None


def test_a_worker_only_sees_the_kinds_it_handles(session: Session) -> None:
    store.enqueue(session, _request("a", kind=JobKind.forecast), now=NOW)

    assert store.claim(session, kinds=(JobKind.document_intake,), now=NOW) is None
    assert store.claim(session, kinds=(JobKind.forecast,), now=NOW) is not None


def test_an_expired_lease_returns_the_job_to_the_queue(session: Session) -> None:
    """A worker that crashes mid-job must not strand it in `running`."""

    job = store.enqueue(session, _request(), now=NOW)
    store.claim(session, lease_seconds=60, now=NOW)

    released = store.release_expired(session, now=NOW + timedelta(minutes=5))

    assert released == 1
    session.refresh(job)
    assert job.state == JobState.queued.value
    assert store.claim(session, now=NOW + timedelta(minutes=5)) is not None


def test_a_live_lease_is_left_alone(session: Session) -> None:
    store.enqueue(session, _request(), now=NOW)
    store.claim(session, lease_seconds=600, now=NOW)

    assert store.release_expired(session, now=NOW + timedelta(minutes=5)) == 0


def test_extending_a_lease_pushes_the_expiry_out(session: Session) -> None:
    store.enqueue(session, _request(), now=NOW)
    lease = store.claim(session, lease_seconds=60, now=NOW)
    assert lease is not None

    extended = store.extend(session, lease, lease_seconds=600, now=NOW)

    assert extended.expires_at > lease.expires_at


def test_success_records_what_the_job_produced(session: Session) -> None:
    job = store.enqueue(session, _request(), now=NOW)
    lease = store.claim(session, now=NOW)
    assert lease is not None

    store.succeed(session, lease, result={"document_id": 7}, now=NOW)

    session.refresh(job)
    assert job.state == JobState.succeeded.value
    assert job.result == {"document_id": 7}
    assert job.finished_at is not None
    assert job.lease_token is None


def test_a_retryable_failure_goes_back_to_the_queue(session: Session) -> None:
    job = store.enqueue(session, _request(), now=NOW)
    lease = store.claim(session, now=NOW)
    assert lease is not None

    store.fail(session, lease, reason="throttled", now=NOW)

    session.refresh(job)
    assert job.state == JobState.queued.value
    assert job.failure_reason == "throttled"
    # It waits before being offered again, so a failing provider is not hammered.
    assert store.claim(session, now=NOW) is None
    assert store.claim(session, now=NOW + timedelta(minutes=1)) is not None


def test_exhausting_the_attempts_fails_the_job_for_good(session: Session) -> None:
    job = store.enqueue(session, _request(max_attempts=2), now=NOW)
    moment = NOW
    for _ in range(2):
        lease = store.claim(session, now=moment)
        assert lease is not None
        store.fail(session, lease, reason="still broken", now=moment)
        moment += timedelta(minutes=1)

    session.refresh(job)
    assert job.state == JobState.failed.value
    assert job.attempts == 2
    assert store.claim(session, now=moment) is None


def test_a_permanent_failure_is_not_retried(session: Session) -> None:
    job = store.enqueue(session, _request(), now=NOW)
    lease = store.claim(session, now=NOW)
    assert lease is not None

    store.fail(session, lease, reason="unsupported media type", retry=False, now=NOW)

    session.refresh(job)
    assert job.state == JobState.failed.value
    assert job.attempts == 1


def test_a_stale_lease_cannot_finish_a_job(session: Session) -> None:
    """A worker whose lease expired must not overwrite whoever took over."""

    store.enqueue(session, _request(), now=NOW)
    stale = store.claim(session, lease_seconds=60, now=NOW)
    assert stale is not None
    store.release_expired(session, now=NOW + timedelta(minutes=5))
    store.claim(session, now=NOW + timedelta(minutes=5))

    with pytest.raises(JobConflictError):
        store.succeed(session, stale, result={"document_id": 1})


def test_a_terminal_job_cannot_be_cancelled(session: Session) -> None:
    job = store.enqueue(session, _request(), now=NOW)
    lease = store.claim(session, now=NOW)
    assert lease is not None
    store.succeed(session, lease, now=NOW)

    with pytest.raises(JobConflictError):
        store.cancel(session, job.id)


def test_a_queued_job_can_be_cancelled(session: Session) -> None:
    job = store.enqueue(session, _request(), now=NOW)

    store.cancel(session, job.id, now=NOW)

    session.refresh(job)
    assert job.state == JobState.cancelled.value
    assert store.claim(session, now=NOW) is None
