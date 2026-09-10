"""The hosted queue adapter, against a stub. It never touches a live queue."""

from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy.orm import Session

from retailops_api.domain.models.job import JobKind, JobState
from retailops_api.jobs import store
from retailops_api.jobs.sqs import SqsJobQueue
from retailops_api.jobs.types import JobConfigError, JobRequest

QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/000000000000/retailops-documents"


class FakeSqs:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.deleted: list[str] = []
        self.visibility: list[dict[str, Any]] = []
        self._inbox: list[dict[str, Any]] = []

    def send_message(self, **kwargs: Any) -> dict[str, Any]:
        self.sent.append(kwargs)
        self._inbox.append({"Body": kwargs["MessageBody"], "ReceiptHandle": f"r{len(self.sent)}"})
        return {}

    def receive_message(self, **_kwargs: Any) -> dict[str, Any]:
        if not self._inbox:
            return {}
        return {"Messages": [self._inbox.pop(0)]}

    def delete_message(self, **kwargs: Any) -> dict[str, Any]:
        self.deleted.append(kwargs["ReceiptHandle"])
        return {}

    def change_message_visibility(self, **kwargs: Any) -> dict[str, Any]:
        self.visibility.append(kwargs)
        return {}


@pytest.fixture
def client() -> FakeSqs:
    return FakeSqs()


@pytest.fixture
def queue(session: Session, client: FakeSqs) -> SqsJobQueue:
    return SqsJobQueue(session, client, queue_url=QUEUE_URL)


def _request(key: str = "k") -> JobRequest:
    return JobRequest(
        kind=JobKind.document_intake,
        idempotency_key=key,
        request={"supplier_code": "SUP-1"},
        requested_by="Ana",
        requested_by_subject="subject-ana",
    )


def test_a_queue_url_is_required(session: Session, client: FakeSqs) -> None:
    with pytest.raises(JobConfigError):
        SqsJobQueue(session, client, queue_url="  ")


def test_enqueuing_records_the_job_and_announces_it(queue: SqsJobQueue, client: FakeSqs) -> None:
    job = queue.enqueue(_request())

    assert job.state == JobState.queued.value
    assert len(client.sent) == 1
    assert json.loads(client.sent[0]["MessageBody"])["job_id"] == job.id


def test_a_repeated_request_is_not_announced_twice(queue: SqsJobQueue, client: FakeSqs) -> None:
    """The same key returns the existing job; a message is already in flight."""

    queue.enqueue(_request("same"))
    queue.enqueue(_request("same"))

    assert len(client.sent) == 1


def test_leasing_claims_the_job_the_message_names(queue: SqsJobQueue) -> None:
    job = queue.enqueue(_request())

    lease = queue.lease()

    assert lease is not None
    assert lease.job_id == job.id


def test_a_message_for_a_finished_job_is_discarded(
    queue: SqsJobQueue, client: FakeSqs, session: Session
) -> None:
    """At-least-once delivery is safe because the row decides, not the message."""

    job = queue.enqueue(_request())
    lease = store.claim(session, lease_seconds=60)
    assert lease is not None
    store.succeed(session, lease, result={"document_id": 1})

    assert queue.lease() is None
    assert client.deleted == ["r1"]
    session.refresh(job)
    assert job.state == JobState.succeeded.value


def test_a_message_for_an_unknown_job_is_discarded(queue: SqsJobQueue, client: FakeSqs) -> None:
    client.send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps({"job_id": 4242}))

    assert queue.lease() is None
    assert client.deleted


def test_a_malformed_message_is_discarded(queue: SqsJobQueue, client: FakeSqs) -> None:
    client.send_message(QueueUrl=QUEUE_URL, MessageBody="not json")

    assert queue.lease() is None
    assert client.deleted


def test_a_successful_release_deletes_the_message(
    queue: SqsJobQueue, client: FakeSqs, session: Session
) -> None:
    queue.enqueue(_request())
    lease = queue.lease()
    assert lease is not None
    store.succeed(session, lease, result={})

    queue.release(lease, succeeded=True)

    assert client.deleted == ["r1"]


def test_a_retryable_failure_is_announced_again(
    queue: SqsJobQueue, client: FakeSqs, session: Session
) -> None:
    """The row asked for a wait, so the message is re-sent with that delay
    rather than left to the visibility timeout."""

    queue.enqueue(_request())
    lease = queue.lease()
    assert lease is not None
    store.fail(session, lease, reason="throttled", retry=True)

    queue.release(lease, succeeded=False)

    assert client.deleted == ["r1"]
    assert len(client.sent) == 2
    assert client.sent[1]["DelaySeconds"] >= 0


def test_an_exhausted_job_is_not_announced_again(
    queue: SqsJobQueue, client: FakeSqs, session: Session
) -> None:
    queue.enqueue(_request())
    lease = queue.lease()
    assert lease is not None
    store.fail(session, lease, reason="broken", retry=False)

    queue.release(lease, succeeded=False)

    assert len(client.sent) == 1


def test_extending_pushes_both_the_message_and_the_row(queue: SqsJobQueue, client: FakeSqs) -> None:
    queue.enqueue(_request())
    lease = queue.lease()
    assert lease is not None

    extended = queue.extend(lease)

    assert client.visibility
    assert extended.expires_at >= lease.expires_at


# --------------------------------------------------------------------------- #
# Provider selection
# --------------------------------------------------------------------------- #


def test_the_database_queue_is_the_default(session: Session) -> None:
    from retailops_api.core.adapters import job_queue_for
    from retailops_api.core.config import Settings
    from retailops_api.jobs.database import DatabaseJobQueue

    assert isinstance(job_queue_for(Settings(), session), DatabaseJobQueue)


def test_the_hosted_queue_requires_a_url(session: Session) -> None:
    from retailops_api.core.adapters import job_queue_for
    from retailops_api.core.config import Settings

    with pytest.raises(JobConfigError, match="JOBS_QUEUE_URL"):
        job_queue_for(Settings(job_queue_provider="sqs"), session)


def test_the_hosted_queue_never_falls_back_to_the_database(
    session: Session, client: FakeSqs
) -> None:
    """A deployment that names a hosted queue must not silently use the table."""

    from retailops_api.core.adapters import job_queue_for
    from retailops_api.core.config import Settings

    queue = job_queue_for(
        Settings(job_queue_provider="sqs", jobs_queue_url=QUEUE_URL), session, sqs=client
    )

    assert isinstance(queue, SqsJobQueue)


def test_aws_feature_flags_do_not_select_a_queue(session: Session) -> None:
    from retailops_api.core.adapters import job_queue_for
    from retailops_api.core.config import Settings
    from retailops_api.jobs.database import DatabaseJobQueue

    settings = Settings(aws_enabled=True, aws_use_s3_storage=True)

    assert isinstance(job_queue_for(settings, session), DatabaseJobQueue)


def test_the_job_the_message_names_is_the_one_that_runs(
    queue: SqsJobQueue, session: Session
) -> None:
    """With several jobs waiting, taking whichever is next would run the wrong
    one and leave the delivered job untouched."""

    older = store.enqueue(session, _request("older"))
    delivered = queue.enqueue(_request("delivered"))

    lease = queue.lease()

    assert lease is not None
    assert lease.job_id == delivered.id
    session.refresh(older)
    assert older.state == JobState.queued.value


def test_a_message_for_a_job_someone_else_took_is_left_alone(
    queue: SqsJobQueue, client: FakeSqs, session: Session
) -> None:
    job = queue.enqueue(_request())
    store.claim_job(session, job.id)

    assert queue.lease() is None
    # Not deleted: nobody has finished the work yet.
    assert client.deleted == []


def test_a_redelivered_job_whose_holder_went_away_can_run_again(
    queue: SqsJobQueue, client: FakeSqs, session: Session
) -> None:
    """SQS redelivers, but the row must also stop refusing the claim.

    Otherwise a worker that crashed leaves the job unrunnable for good, even
    though its message keeps coming back.
    """

    from datetime import UTC, datetime, timedelta

    job = queue.enqueue(_request())
    lease = queue.lease()
    assert lease is not None

    # The holder disappears; the lease lapses and the message reappears.
    session.refresh(job)
    job.leased_until = datetime.now(UTC) - timedelta(minutes=10)
    session.flush()
    client.send_message(
        QueueUrl=QUEUE_URL, MessageBody=json.dumps({"job_id": job.id, "kind": job.kind})
    )

    retried = queue.lease()

    assert retried is not None
    assert retried.job_id == job.id
    session.refresh(job)
    assert job.attempts == 2
