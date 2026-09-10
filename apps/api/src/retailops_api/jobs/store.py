"""Persistence and controlled state transitions for jobs.

Every transition goes through here so a terminal job is never reopened and two
workers never hold the same job. The caller owns the transaction.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from retailops_api.domain.models.job import TERMINAL_STATES, JobKind, JobState, ProcessingJob
from retailops_api.jobs.types import (
    DEFAULT_LEASE_SECONDS,
    MAX_IDEMPOTENCY_KEY_LENGTH,
    JobConflictError,
    JobNotFoundError,
    JobRequest,
    JobValidationError,
    JobView,
    Lease,
)


def enqueue(session: Session, request: JobRequest, *, now: datetime | None = None) -> ProcessingJob:
    """Record a job, or return the one this key already produced.

    The uniqueness of (kind, key) is enforced by the database rather than by a
    prior read, so two simultaneous submissions cannot both create a job.
    """

    key = request.idempotency_key.strip()
    if not key:
        raise JobValidationError("an idempotency key is required")
    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise JobValidationError(
            f"the idempotency key must be at most {MAX_IDEMPOTENCY_KEY_LENGTH} characters"
        )

    moment = now or datetime.now(UTC)
    existing = find_by_key(session, request.kind, key)
    if existing is not None:
        return existing

    job = ProcessingJob(
        kind=request.kind.value,
        state=JobState.queued.value,
        idempotency_key=key,
        requested_by=request.requested_by,
        requested_by_subject=request.requested_by_subject,
        request=request.request,
        attempts=0,
        max_attempts=request.max_attempts,
        available_at=moment,
    )
    session.add(job)
    try:
        with session.begin_nested():
            session.flush()
    except IntegrityError:
        # Two submissions raced past the read above. Drop the doomed row so a
        # later flush does not raise again, and hand back the one that won.
        session.expunge(job)
        winner = find_by_key(session, request.kind, key)
        if winner is None:  # pragma: no cover - the constraint was something else
            raise
        return winner
    return job


def find_by_key(session: Session, kind: JobKind, key: str) -> ProcessingJob | None:
    return session.scalars(
        select(ProcessingJob).where(
            ProcessingJob.kind == kind.value,
            ProcessingJob.idempotency_key == key,
        )
    ).one_or_none()


def get_job(session: Session, job_id: int) -> ProcessingJob:
    job = session.get(ProcessingJob, job_id)
    if job is None:
        raise JobNotFoundError(f"job {job_id} not found")
    return job


def claim(
    session: Session,
    *,
    kinds: tuple[JobKind, ...] = (),
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    now: datetime | None = None,
) -> Lease | None:
    """Take the next claimable job, or return nothing.

    The claim is a conditional update: the row moves to ``running`` only if it
    is still ``queued``. A second worker that loses the race updates no rows
    and looks again, so the same job is never handed out twice.
    """

    moment = now or datetime.now(UTC)
    expires = moment + timedelta(seconds=lease_seconds)

    while True:
        candidate = _next_claimable(session, kinds=kinds, now=moment)
        if candidate is None:
            return None
        token = secrets.token_hex(16)
        statement = (
            update(ProcessingJob)
            .where(
                ProcessingJob.id == candidate,
                ProcessingJob.state == JobState.queued.value,
            )
            .values(
                state=JobState.running.value,
                lease_token=token,
                leased_until=expires,
                attempts=ProcessingJob.attempts + 1,
            )
            # Let the database apply the criteria. Evaluating them in Python
            # compares an aware value against whatever the driver returned,
            # which is naive on SQLite.
            .execution_options(synchronize_session=False)
        )
        outcome = cast("CursorResult[Any]", session.execute(statement))
        if outcome.rowcount:
            job = session.get(ProcessingJob, candidate, populate_existing=True)
            if job is None:  # pragma: no cover - it was claimed a moment ago
                raise JobNotFoundError(f"job {candidate} not found")
            if job.started_at is None:
                job.started_at = moment
            session.flush()
            return Lease(job_id=candidate, token=token, expires_at=expires)


def _next_claimable(session: Session, *, kinds: tuple[JobKind, ...], now: datetime) -> int | None:
    statement = select(ProcessingJob.id).where(
        ProcessingJob.state == JobState.queued.value,
        ProcessingJob.available_at <= now,
    )
    if kinds:
        statement = statement.where(ProcessingJob.kind.in_([kind.value for kind in kinds]))
    return session.scalars(statement.order_by(ProcessingJob.id.asc()).limit(1)).first()


def release_expired(session: Session, *, now: datetime | None = None) -> int:
    """Return jobs whose holder went away, so they can be run again.

    A worker that crashes mid-job leaves a lease behind. Nothing else would
    notice, and the job would sit in ``running`` forever.
    """

    moment = now or datetime.now(UTC)
    statement = (
        update(ProcessingJob)
        .where(
            ProcessingJob.state == JobState.running.value,
            ProcessingJob.leased_until.is_not(None),
            ProcessingJob.leased_until < moment,
        )
        .values(
            state=JobState.queued.value,
            lease_token=None,
            leased_until=None,
            available_at=moment,
        )
        .execution_options(synchronize_session=False)
    )
    outcome = cast("CursorResult[Any]", session.execute(statement))
    # The rows changed underneath the session; anything cached is now wrong.
    session.expire_all()
    session.flush()
    return int(outcome.rowcount or 0)


def extend(
    session: Session,
    lease: Lease,
    *,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    now: datetime | None = None,
) -> Lease:
    job = _leased(session, lease)
    expires = (now or datetime.now(UTC)) + timedelta(seconds=lease_seconds)
    job.leased_until = expires
    session.flush()
    return Lease(job_id=lease.job_id, token=lease.token, expires_at=expires)


def succeed(
    session: Session,
    lease: Lease,
    *,
    result: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> ProcessingJob:
    job = _leased(session, lease)
    job.state = JobState.succeeded.value
    job.result = result
    job.failure_reason = None
    job.finished_at = now or datetime.now(UTC)
    job.lease_token = None
    job.leased_until = None
    session.flush()
    return job


def fail(
    session: Session,
    lease: Lease,
    *,
    reason: str,
    retry: bool = True,
    retry_after_seconds: int = 30,
    now: datetime | None = None,
) -> ProcessingJob:
    """Record a failure, and decide whether the job gets another attempt."""

    job = _leased(session, lease)
    moment = now or datetime.now(UTC)
    job.failure_reason = reason
    job.lease_token = None
    job.leased_until = None
    if retry and job.attempts < job.max_attempts:
        job.state = JobState.queued.value
        job.available_at = moment + timedelta(seconds=retry_after_seconds)
    else:
        job.state = JobState.failed.value
        job.finished_at = moment
    session.flush()
    return job


def cancel(session: Session, job_id: int, *, now: datetime | None = None) -> ProcessingJob:
    job = get_job(session, job_id)
    if JobState(job.state) in TERMINAL_STATES:
        raise JobConflictError(f"job {job_id} is already {job.state}")
    job.state = JobState.cancelled.value
    job.finished_at = now or datetime.now(UTC)
    job.lease_token = None
    job.leased_until = None
    session.flush()
    return job


def _leased(session: Session, lease: Lease) -> ProcessingJob:
    job = get_job(session, lease.job_id)
    if job.lease_token != lease.token:
        raise JobConflictError(f"job {lease.job_id} is held by someone else")
    if JobState(job.state) is not JobState.running:
        raise JobConflictError(f"job {lease.job_id} is {job.state}, not running")
    return job


def job_view(job: ProcessingJob) -> JobView:
    return JobView(
        id=job.id,
        kind=JobKind(job.kind),
        state=JobState(job.state),
        requested_by=job.requested_by,
        requested_by_verified=job.requested_by_subject is not None,
        request=job.request,
        result=job.result,
        failure_reason=job.failure_reason,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )
