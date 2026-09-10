"""Upload to findings, through the queue, with nothing mocked but the clock."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from retailops_api.api.deps import get_db
from retailops_api.core.config import Settings
from retailops_api.documents.query import get_document, list_documents
from retailops_api.documents.storage import LocalDocumentStorage
from retailops_api.domain.models.job import JobKind, JobState
from retailops_api.jobs import store
from retailops_api.jobs.worker import Worker
from retailops_api.main import create_app
from tests.factories import make_supplier
from tests.job_support import borrowed_session_factory

SHEET = Path("tests/fixtures/supplier_documents/valid.csv").read_bytes()
INVALID = Path("tests/fixtures/supplier_documents/invalid_ean.csv").read_bytes()


@pytest.fixture
def shared_settings(settings: Settings, tmp_path: Path) -> Settings:
    """One storage root for the API and the worker.

    They do not share a filesystem once deployed, which is why object storage
    is mandatory there; here a shared directory stands in for it.
    """

    return settings.model_copy(update={"document_storage_root": str(tmp_path)})


@pytest.fixture
def app(shared_settings: Settings) -> FastAPI:
    return create_app(shared_settings)


@pytest.fixture
def api_client(app: FastAPI, session: Session, reviewer_token: str):  # type: ignore[no-untyped-def]
    def _override():  # type: ignore[no-untyped-def]
        yield session
        session.commit()

    app.dependency_overrides[get_db] = _override
    with TestClient(app, headers={"Authorization": f"Bearer {reviewer_token}"}) as client:
        yield client
    app.dependency_overrides.clear()


def _worker(session: Session, settings: Settings) -> Worker:
    return Worker(
        settings=settings,
        session_factory=borrowed_session_factory(session),
        idle_sleep_seconds=0,
    )


def test_an_uploaded_sheet_reaches_findings_through_the_queue(
    api_client: TestClient, session: Session, shared_settings: Settings, tmp_path: Path
) -> None:
    make_supplier(session, code="SUP-E2E")

    accepted = api_client.post(
        "/documents",
        data={"supplier": "SUP-E2E"},
        files={"file": ("offer.csv", io.BytesIO(SHEET), "text/csv")},
    )
    assert accepted.status_code == 202
    job_id = accepted.json()["id"]

    _worker(session, shared_settings).run_once()

    job = store.get_job(session, job_id)
    assert job.state == JobState.succeeded.value, job.failure_reason
    assert job.result is not None
    document_id = job.result["document_id"]

    document = get_document(session, document_id, LocalDocumentStorage(tmp_path))
    assert document is not None
    assert document["status"] in {"validated", "review_ready"}
    assert list_documents(session, limit=10, offset=0)["total"] == 1


def test_a_sheet_with_problems_still_finishes_and_reports_them(
    api_client: TestClient, session: Session, shared_settings: Settings
) -> None:
    """A document the rules reject is a successful job with findings, not a
    failed job: the pipeline did its work and reached a verdict."""

    make_supplier(session, code="SUP-E2E")

    accepted = api_client.post(
        "/documents",
        data={"supplier": "SUP-E2E"},
        files={"file": ("bad.csv", io.BytesIO(INVALID), "text/csv")},
    )
    _worker(session, shared_settings).run_once()

    job = store.get_job(session, accepted.json()["id"])
    assert job.state == JobState.succeeded.value
    assert job.result is not None
    assert job.result["finding_count"] >= 1


def test_a_job_for_a_supplier_that_disappeared_fails_permanently(
    api_client: TestClient, session: Session, shared_settings: Settings
) -> None:
    from retailops_api.domain.models.supplier import Supplier

    supplier = make_supplier(session, code="SUP-GONE")
    accepted = api_client.post(
        "/documents",
        data={"supplier": "SUP-GONE"},
        files={"file": ("offer.csv", io.BytesIO(SHEET), "text/csv")},
    )
    session.query(Supplier).filter(Supplier.id == supplier.id).delete()
    session.flush()

    _worker(session, shared_settings).run_once()

    job = store.get_job(session, accepted.json()["id"])
    assert job.state == JobState.failed.value
    assert job.attempts == 1
    assert "SUP-GONE" in (job.failure_reason or "")


def test_the_console_can_follow_a_job_to_its_result(
    api_client: TestClient, session: Session, shared_settings: Settings
) -> None:
    make_supplier(session, code="SUP-E2E")
    job_id = api_client.post(
        "/documents",
        data={"supplier": "SUP-E2E"},
        files={"file": ("offer.csv", io.BytesIO(SHEET), "text/csv")},
    ).json()["id"]

    queued = api_client.get(f"/jobs/{job_id}").json()
    assert queued["state"] == JobState.queued.value

    _worker(session, shared_settings).run_once()

    settled = api_client.get(f"/jobs/{job_id}").json()
    assert settled["state"] == JobState.succeeded.value
    assert settled["kind"] == JobKind.document_intake.value
    assert settled["result"]["document_id"]
