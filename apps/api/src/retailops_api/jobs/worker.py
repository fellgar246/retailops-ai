"""Run queued work until told to stop.

One job at a time. Concurrency comes from running more workers, not from
threads here: a job holds a database session and calls providers that are
already rate limited, and a single-purpose loop is far easier to reason about
when something goes wrong at three in the morning.

A failure marks the job and continues. A crash leaves a lease that expires, and
the job is offered again.
"""

from __future__ import annotations

import logging
import signal
import time
from collections.abc import Callable
from types import FrameType

from sqlalchemy.orm import Session

from retailops_api.core.adapters import job_queue_for
from retailops_api.core.config import Settings, get_settings
from retailops_api.db.session import get_session_factory
from retailops_api.domain.models.job import JobKind
from retailops_api.jobs import store
from retailops_api.jobs.handlers import handler_for
from retailops_api.jobs.types import (
    Lease,
    PermanentJobError,
)

logger = logging.getLogger("retailops.worker")

#: How long to wait when there was nothing to do. A worker that finds an empty
#: queue must idle cheaply rather than poll tightly.
IDLE_SLEEP_SECONDS = 2.0


class Worker:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        kinds: tuple[JobKind, ...] = (),
        session_factory: Callable[[], Session] | None = None,
        idle_sleep_seconds: float = IDLE_SLEEP_SECONDS,
    ) -> None:
        self._settings = settings or get_settings()
        self._kinds = kinds
        self._session_factory = session_factory or get_session_factory()
        self._idle_sleep = idle_sleep_seconds
        self._stopping = False

    def stop(self) -> None:
        """Ask the loop to finish the current job and exit."""
        self._stopping = True

    def run_forever(self, *, max_iterations: int | None = None) -> int:
        """Process jobs until stopped. Returns how many were run."""

        processed = 0
        iterations = 0
        while not self._stopping:
            if max_iterations is not None and iterations >= max_iterations:
                break
            iterations += 1
            if self.run_once():
                processed += 1
            elif not self._stopping:
                time.sleep(self._idle_sleep)
        return processed

    def run_once(self) -> bool:
        """Claim and run a single job. Returns whether one was found."""

        with self._session_factory() as session:
            lease = job_queue_for(self._settings, session).lease(kinds=self._kinds)
            session.commit()
            if lease is None:
                return False

        succeeded = self._execute(lease)

        # Settle the delivery after the outcome is on the row, so a hosted
        # queue never deletes a message for work that was not recorded.
        with self._session_factory() as session:
            try:
                job_queue_for(self._settings, session).release(lease, succeeded=succeeded)
                session.commit()
            except Exception:  # pragma: no cover - the row already holds the truth
                session.rollback()
                logger.exception("could not settle the delivery of job %s", lease.job_id)
        return True

    def _execute(self, lease: Lease) -> bool:
        """Run the job. Returns whether it succeeded."""

        with self._session_factory() as session:
            try:
                job = store.get_job(session, lease.job_id)
                kind = JobKind(job.kind)
                logger.info("job %s (%s) started", job.id, kind.value)
                result = handler_for(kind)(session, self._settings, job)
            except PermanentJobError as error:
                session.rollback()
                self._record_failure(lease, str(error), retry=False)
                return False
            except Exception as error:
                session.rollback()
                self._record_failure(lease, f"{type(error).__name__}: {error}", retry=True)
                return False

            try:
                store.succeed(session, lease, result=result)
                session.commit()
                logger.info("job %s succeeded", lease.job_id)
                return True
            except Exception:
                session.rollback()
                raise

    def _record_failure(self, lease: Lease, reason: str, *, retry: bool) -> None:
        """Record the outcome in its own transaction.

        The work's transaction was rolled back, so this must not ride on it or
        the failure would be lost along with the partial work.
        """

        with self._session_factory() as session:
            try:
                job = store.fail(session, lease, reason=reason, retry=retry)
                session.commit()
                logger.warning("job %s failed (%s): %s", lease.job_id, job.state, reason)
            except Exception:  # pragma: no cover - nothing left to do but say so
                session.rollback()
                logger.exception("could not record the failure of job %s", lease.job_id)


def install_signal_handlers(worker: Worker) -> None:
    """Finish the current job, then stop, rather than abandoning a lease."""

    def _handle(signum: int, frame: FrameType | None) -> None:
        del signum, frame
        logger.info("stopping after the current job")
        worker.stop()

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)
