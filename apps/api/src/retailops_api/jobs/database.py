"""Queue backed by the job table itself.

Claiming is a conditional update, so two workers cannot take the same row.
There is nothing to keep in sync, because the table both delivers and records.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from retailops_api.domain.models.job import JobKind, ProcessingJob
from retailops_api.jobs import store
from retailops_api.jobs.types import DEFAULT_LEASE_SECONDS, JobRequest, Lease


class DatabaseJobQueue:
    def __init__(self, session: Session, *, lease_seconds: int = DEFAULT_LEASE_SECONDS) -> None:
        self._session = session
        self._lease_seconds = lease_seconds

    @property
    def provider_id(self) -> str:
        return "database"

    def enqueue(self, request: JobRequest) -> ProcessingJob:
        return store.enqueue(self._session, request)

    def lease(self, *, kinds: tuple[JobKind, ...] = ()) -> Lease | None:
        # A holder that went away must not strand its job in `running`.
        store.release_expired(self._session)
        return store.claim(self._session, kinds=kinds, lease_seconds=self._lease_seconds)

    def extend(self, lease: Lease) -> Lease:
        return store.extend(self._session, lease, lease_seconds=self._lease_seconds)

    def release(self, lease: Lease, *, succeeded: bool) -> None:
        # The outcome is already on the row, so there is no message to settle.
        # A hosted queue needs this call; this one does not.
        del lease, succeeded
