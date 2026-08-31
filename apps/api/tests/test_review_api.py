"""HTTP review queue, decisions, audit, feedback and metrics."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from retailops_api.review.workflow import start_review
from tests.review_support import finding_case


def test_metrics_endpoint_starts_empty(api_client: TestClient) -> None:
    response = api_client.get("/reviews/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["open_cases"] == 0
    assert body["acceptance_rate"] == 0.0
    assert body["average_review_duration_seconds"] is None


def test_create_list_start_approve_and_audit(api_client: TestClient, session: Session) -> None:
    case = finding_case(session, supplier_code="SUP-HTTP")
    session.commit()

    listed = api_client.get("/reviews", params={"status": "open"})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == case.id

    started = api_client.post(f"/reviews/{case.id}/start", json={"reviewer": "alice"})
    assert started.status_code == 200
    assert started.json()["status"] == "in_review"

    approved = api_client.post(
        f"/reviews/{case.id}/approve", json={"reviewer": "alice", "comment": "ok"}
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    detail = api_client.get(f"/reviews/{case.id}")
    assert detail.status_code == 200
    assert detail.json()["decision"]["decision"] == "approved"
    assert detail.json()["snapshot"]["original_output"]["suggested_value"] == "BEV-SOFT"

    audit = api_client.get(f"/reviews/{case.id}/audit")
    assert audit.status_code == 200
    types = [item["event_type"] for item in audit.json()["items"]]
    assert "created" in types
    assert "approved" in types
    assert "status_changed" in types


def test_reject_and_correct_and_conflict(api_client: TestClient, session: Session) -> None:
    rejected = finding_case(session, supplier_code="SUP-HTTP-R")
    start_review(session, rejected.id, reviewer="alice")
    corrected = finding_case(session, supplier_code="SUP-HTTP-C")
    start_review(session, corrected.id, reviewer="alice")
    session.commit()

    missing_reason = api_client.post(
        f"/reviews/{rejected.id}/reject", json={"reviewer": "alice", "reason": ""}
    )
    assert missing_reason.status_code == 422

    reject = api_client.post(
        f"/reviews/{rejected.id}/reject",
        json={"reviewer": "alice", "reason": "wrong"},
    )
    assert reject.status_code == 200
    assert reject.json()["status"] == "rejected"

    conflict = api_client.post(f"/reviews/{rejected.id}/approve", json={"reviewer": "alice"})
    assert conflict.status_code == 409

    fix = api_client.post(
        f"/reviews/{corrected.id}/correct",
        json={"reviewer": "alice", "correction": {"suggested_value": "BEV-WATER"}},
    )
    assert fix.status_code == 200
    assert fix.json()["status"] == "corrected"

    feedback = api_client.get("/reviews/feedback")
    assert feedback.status_code == 200
    assert feedback.json()["count"] == 2
    decisions = {item["decision"] for item in feedback.json()["items"]}
    assert decisions == {"rejected", "corrected"}

    metrics = api_client.get("/reviews/metrics")
    assert metrics.json()["rejection_rate"] == 0.5
    assert metrics.json()["correction_rate"] == 0.5
    assert metrics.json()["open_cases"] == 0


def test_unknown_case_is_not_found(api_client: TestClient) -> None:
    assert api_client.get("/reviews/9999").status_code == 404
    assert api_client.post("/reviews/9999/start", json={"reviewer": "alice"}).status_code == 404
