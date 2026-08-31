"""Supplier sheet → storage → parse → findings → mock AI → review → API → audit."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from retailops_api.db.seed import seed_reference_data
from retailops_api.demo.sheets import COST_INCREASE
from retailops_api.documents.process import process_document
from retailops_api.documents.storage import LocalDocumentStorage
from retailops_api.domain.models import DocumentFinding, ReviewAuditEvent
from retailops_api.review.mock import MockAIReviewer
from retailops_api.review.persist import create_review_case
from retailops_api.review.supplier import review_from_process_result


def test_supplier_sheet_reaches_a_recorded_human_decision(
    api_client: TestClient, session: Session, tmp_path: Path
) -> None:
    seed_reference_data(session)
    storage = LocalDocumentStorage(tmp_path / "documents")
    processed = process_document(
        session,
        storage,
        supplier_code=COST_INCREASE.supplier_code,
        filename=COST_INCREASE.filename,
        data=COST_INCREASE.body.encode("utf-8"),
    )
    assert processed.status in {"review_ready", "parse_failed"}
    assert processed.findings
    assert (tmp_path / "documents").exists()

    semantic = review_from_process_result(processed, MockAIReviewer())
    assert semantic.source_of_truth == processed.findings
    finding = session.scalars(
        select(DocumentFinding).where(DocumentFinding.document_id == processed.document_id)
    ).first()
    assert finding is not None
    case = create_review_case(session, finding=finding, result=semantic.ai_result, actor="demo")
    session.commit()

    started = api_client.post(f"/reviews/{case.id}/start", json={"reviewer": "alice"})
    assert started.status_code == 200
    assert started.json()["status"] == "in_review"

    approved = api_client.post(
        f"/reviews/{case.id}/approve", json={"reviewer": "alice", "comment": "cost noted"}
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    detail = api_client.get(f"/reviews/{case.id}")
    assert detail.status_code == 200
    assert detail.json()["decision"]["decision"] == "approved"
    assert detail.json()["snapshot"] is not None

    audit = api_client.get(f"/reviews/{case.id}/audit")
    types = [item["event_type"] for item in audit.json()["items"]]
    assert "created" in types
    assert "approved" in types

    feedback = api_client.get("/reviews/feedback")
    assert feedback.json()["count"] == 1
    assert feedback.json()["items"][0]["decision"] == "approved"

    assert session.scalar(select(ReviewAuditEvent).limit(1)) is not None
