"""Shared shapes for asynchronous work.

The job row owns the state. These are the values that move between the API,
the queue and the worker.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from retailops_api.domain.models.job import JobKind, JobState

#: How long a worker may hold a job before its lease expires and the job is
#: offered again. Longer than the slowest provider call the worker makes.
DEFAULT_LEASE_SECONDS = 300
DEFAULT_MAX_ATTEMPTS = 3
MAX_IDEMPOTENCY_KEY_LENGTH = 128


class JobError(Exception):
    """Base class for job failures."""


class JobConfigError(JobError):
    """Queue configuration is missing or inconsistent."""


class JobValidationError(JobError):
    """The request cannot be turned into a job."""


class JobNotFoundError(JobError):
    """No such job."""


class JobConflictError(JobError):
    """The job is not in a state that allows this transition."""


class RetryableJobError(JobError):
    """A handler failed in a way worth retrying, unless attempts run out."""


class PermanentJobError(JobError):
    """A handler failed in a way that retrying cannot fix."""


@dataclass(frozen=True)
class JobRequest:
    """What an operator asked for."""

    kind: JobKind
    idempotency_key: str
    request: dict[str, Any]
    requested_by: str
    requested_by_subject: str | None
    max_attempts: int = DEFAULT_MAX_ATTEMPTS


@dataclass(frozen=True)
class JobView:
    """A job as the API and the console see it."""

    id: int
    kind: JobKind
    state: JobState
    requested_by: str
    requested_by_verified: bool
    request: dict[str, Any]
    result: dict[str, Any] | None
    failure_reason: str | None
    attempts: int
    max_attempts: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "state": self.state.value,
            "requested_by": self.requested_by,
            "requested_by_verified": self.requested_by_verified,
            "request": self.request,
            "result": self.result,
            "failure_reason": self.failure_reason,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "created_at": _iso(self.created_at),
            "started_at": _iso(self.started_at),
            "finished_at": _iso(self.finished_at),
        }


@dataclass(frozen=True)
class Lease:
    """A claim on a job. The token proves the holder still owns it."""

    job_id: int
    token: str
    expires_at: datetime


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()
