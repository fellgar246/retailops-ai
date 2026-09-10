"""Provider-neutral job queue.

A queue delivers work. It never decides what happened: the job row is the
record of truth for state, so a message that disagrees with it is discarded.

The database implementation needs no broker and no cloud, which is what local
development, the demo and the test suite use.
"""

from __future__ import annotations

from typing import Protocol

from retailops_api.domain.models.job import JobKind, ProcessingJob
from retailops_api.jobs.types import JobRequest, Lease


class JobQueue(Protocol):
    """Delivery of queued work. Implementations must not assume a vendor."""

    @property
    def provider_id(self) -> str: ...

    def enqueue(self, request: JobRequest) -> ProcessingJob:
        """Record the job, or return the one this key already produced."""
        ...

    def lease(self, *, kinds: tuple[JobKind, ...] = ()) -> Lease | None:
        """Claim the next job, or return nothing."""
        ...

    def extend(self, lease: Lease) -> Lease:
        """Keep a claim alive while the work is still running."""
        ...

    def release(self, lease: Lease, *, succeeded: bool) -> None:
        """Give the claim back. The caller has already recorded the outcome."""
        ...
