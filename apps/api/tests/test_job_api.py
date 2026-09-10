"""Starting work from the API: authorization, validation and idempotency."""

from __future__ import annotations

import io

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from retailops_api.domain.models.job import JobKind, JobState
from tests.factories import make_supplier

VALID_SHEET = b"sku,description,unit_cost,currency\nSKU-1,Widget,1.50,EUR\n"


def _upload(
    client: TestClient, *, supplier: str = "SUP-JOB", data: bytes = VALID_SHEET, name: str = "s.csv"
) -> httpx.Response:
    response: httpx.Response = client.post(
        "/documents",
        data={"supplier": supplier},
        files={"file": (name, io.BytesIO(data), "text/csv")},
    )
    return response


def test_an_upload_is_accepted_and_returns_a_queued_job(
    api_client: TestClient, session: Session
) -> None:
    make_supplier(session, code="SUP-JOB")

    response = _upload(api_client)

    assert response.status_code == 202
    body = response.json()
    assert body["kind"] == JobKind.document_intake.value
    assert body["state"] == JobState.queued.value
    assert body["requested_by_verified"] is True
    assert body["request"]["supplier_code"] == "SUP-JOB"


def test_the_same_file_twice_returns_the_same_job(api_client: TestClient, session: Session) -> None:
    """A double-clicked button must not cost two document analyses."""

    make_supplier(session, code="SUP-JOB")

    first = _upload(api_client).json()
    second = _upload(api_client).json()

    assert second["id"] == first["id"]


def test_a_viewer_may_not_upload(viewer_client: TestClient, session: Session) -> None:
    make_supplier(session, code="SUP-JOB")

    assert _upload(viewer_client).status_code == 403


def test_an_unknown_supplier_is_refused(api_client: TestClient) -> None:
    assert _upload(api_client, supplier="SUP-NOPE").status_code == 404


def test_an_unsupported_file_is_refused_before_it_is_stored(
    api_client: TestClient, session: Session
) -> None:
    """The declared content type is not trusted; the filename decides.

    Otherwise a caller could label anything `text/csv` and have it stored
    before the parser ever looked at it.
    """

    make_supplier(session, code="SUP-JOB")

    response = _upload(api_client, data=b"whatever", name="notes.txt")

    assert response.status_code == 415
    assert api_client.get("/jobs").json()["total"] == 0


def test_an_empty_upload_is_refused(api_client: TestClient, session: Session) -> None:
    make_supplier(session, code="SUP-JOB")

    assert _upload(api_client, data=b"").status_code == 400


def test_a_reconciliation_can_be_started(api_client: TestClient, session: Session) -> None:
    make_supplier(session, code="SUP-JOB")

    response = api_client.post("/reconciliations", json={"supplier": "SUP-JOB", "invoice": "INV-1"})

    assert response.status_code == 202
    assert response.json()["kind"] == JobKind.reconciliation.value


def test_a_reconciliation_needs_a_document_to_match(
    api_client: TestClient, session: Session
) -> None:
    make_supplier(session, code="SUP-JOB")

    response = api_client.post("/reconciliations", json={"supplier": "SUP-JOB"})

    assert response.status_code == 400


def test_a_viewer_may_not_start_a_reconciliation(
    viewer_client: TestClient, session: Session
) -> None:
    make_supplier(session, code="SUP-JOB")

    response = viewer_client.post(
        "/reconciliations", json={"supplier": "SUP-JOB", "invoice": "INV-1"}
    )

    assert response.status_code == 403


def test_a_forecast_can_be_started(api_client: TestClient) -> None:
    response = api_client.post("/forecasts", json={"horizon": 4, "min_train_periods": 12})

    assert response.status_code == 202
    assert response.json()["kind"] == JobKind.forecast.value


def test_a_forecast_request_is_bounded(api_client: TestClient) -> None:
    """One trigger must not be able to occupy a worker indefinitely."""

    assert api_client.post("/forecasts", json={"horizon": 500}).status_code == 422


def test_jobs_are_listed_newest_first(api_client: TestClient, session: Session) -> None:
    make_supplier(session, code="SUP-JOB")
    _upload(api_client)
    api_client.post("/forecasts", json={})

    body = api_client.get("/jobs").json()

    assert body["total"] == 2
    assert body["items"][0]["kind"] == JobKind.forecast.value


def test_jobs_can_be_filtered_by_kind_and_state(api_client: TestClient, session: Session) -> None:
    make_supplier(session, code="SUP-JOB")
    _upload(api_client)
    api_client.post("/forecasts", json={})

    only = api_client.get("/jobs", params={"kind": "forecast"}).json()
    queued = api_client.get("/jobs", params={"state": "queued"}).json()

    assert only["total"] == 1
    assert queued["total"] == 2


def test_a_viewer_may_read_jobs(viewer_client: TestClient, api_client: TestClient) -> None:
    api_client.post("/forecasts", json={})

    assert viewer_client.get("/jobs").status_code == 200


def test_an_unknown_job_is_not_found(api_client: TestClient) -> None:
    assert api_client.get("/jobs/999999").status_code == 404
