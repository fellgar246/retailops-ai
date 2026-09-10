"""Queue backed by SQS.

The message carries the job identifier and nothing else. The job row remains
the record of truth, so a message describing a job that is already terminal is
deleted rather than run again — which is what makes at-least-once delivery
safe here.

Exhausted messages reach the dead-letter queue through the redrive policy on
the queue itself, so nothing here has to count attempts twice.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from retailops_api.domain.models.job import TERMINAL_STATES, JobKind, JobState, ProcessingJob
from retailops_api.jobs import store
from retailops_api.jobs.types import (
    DEFAULT_LEASE_SECONDS,
    JobConfigError,
    JobNotFoundError,
    JobRequest,
    Lease,
)


class SqsJobQueue:
    """Deliver jobs through SQS while the table records what happened."""

    def __init__(
        self,
        session: Session,
        client: Any,
        *,
        queue_url: str,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
    ) -> None:
        if not queue_url.strip():
            raise JobConfigError("a queue URL is required when the hosted queue is selected")
        self._session = session
        self._client = client
        self._queue_url = queue_url
        self._lease_seconds = lease_seconds
        # Per instance: a shared map would hand one queue another's receipts.
        self._receipts: dict[int, str] = {}

    @property
    def provider_id(self) -> str:
        return "sqs"

    def enqueue(self, request: JobRequest) -> ProcessingJob:
        job, created = store.enqueue_job(self._session, request)
        # Only announce a job this call created. An existing one already has a
        # message in flight, and a second would be run twice.
        if created:
            self._client.send_message(
                QueueUrl=self._queue_url,
                MessageBody=json.dumps({"job_id": job.id, "kind": job.kind}),
            )
        return job

    def lease(self, *, kinds: tuple[JobKind, ...] = ()) -> Lease | None:
        response = self._client.receive_message(
            QueueUrl=self._queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=10,
            VisibilityTimeout=self._lease_seconds,
        )
        for message in response.get("Messages", []):
            receipt = message.get("ReceiptHandle", "")
            job_id = _job_id(message)
            if job_id is None:
                self._delete(receipt)
                continue
            try:
                job = store.get_job(self._session, job_id)
            except JobNotFoundError:
                self._delete(receipt)
                continue
            if JobState(job.state) in TERMINAL_STATES:
                # Delivered again after the work was already finished.
                self._delete(receipt)
                continue
            if kinds and JobKind(job.kind) not in kinds:
                # Another worker handles this kind; let the message reappear.
                continue
            claimed = store.claim(self._session, kinds=kinds, lease_seconds=self._lease_seconds)
            if claimed is None or claimed.job_id != job_id:
                continue
            self._receipts[claimed.job_id] = receipt
            return claimed
        return None

    def extend(self, lease: Lease) -> Lease:
        receipt = self._receipts.get(lease.job_id)
        if receipt:
            self._client.change_message_visibility(
                QueueUrl=self._queue_url,
                ReceiptHandle=receipt,
                VisibilityTimeout=self._lease_seconds,
            )
        return store.extend(self._session, lease, lease_seconds=self._lease_seconds)

    def release(self, lease: Lease, *, succeeded: bool) -> None:
        """Settle the message.

        A finished job's message is deleted whatever the outcome, because the
        row already says what happened. A job that will be retried is announced
        again rather than left to the visibility timeout, so the wait the row
        asked for is the wait that actually happens.
        """

        receipt = self._receipts.pop(lease.job_id, None)
        if receipt:
            self._delete(receipt)
        if succeeded:
            return
        job = store.get_job(self._session, lease.job_id)
        if JobState(job.state) is JobState.queued:
            self._client.send_message(
                QueueUrl=self._queue_url,
                MessageBody=json.dumps({"job_id": job.id, "kind": job.kind}),
                DelaySeconds=min(900, max(0, _delay_for(job))),
            )

    def _delete(self, receipt: str) -> None:
        if receipt:
            self._client.delete_message(QueueUrl=self._queue_url, ReceiptHandle=receipt)


def _job_id(message: dict[str, Any]) -> int | None:
    try:
        payload = json.loads(message.get("Body", "{}"))
        return int(payload["job_id"])
    except (ValueError, KeyError, TypeError):
        return None


def _delay_for(job: ProcessingJob) -> int:
    from datetime import UTC, datetime

    available = job.available_at
    if available.tzinfo is None:
        available = available.replace(tzinfo=UTC)
    return int((available - datetime.now(UTC)).total_seconds())
