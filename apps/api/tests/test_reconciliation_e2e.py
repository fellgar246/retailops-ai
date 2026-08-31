"""PO → receipt → invoice → match → AI explanation → human review → audit."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from retailops_api.db.seed import seed_reference_data
from retailops_api.demo.procurement import SCENARIOS, create_demo_procurement
from retailops_api.domain.models import ReconciliationException, ReviewAuditEvent
from retailops_api.review.mock import MockAIReviewer
from retailops_api.review.persist import create_review_case
from retailops_api.review.reconciliation import explain_exception


def test_over_invoice_reaches_audit_after_a_human_decision(
    api_client: TestClient, session: Session
) -> None:
    seed_reference_data(session)
    runs = create_demo_procurement(session)
    over = next(item for item in runs if SCENARIOS[0].po_number in item.scope_key)
    assert over.exception_count > 0

    exception = session.scalars(
        select(ReconciliationException).where(
            ReconciliationException.reconciliation_run_id == over.run_id
        )
    ).first()
    assert exception is not None
    proposed = next(item for item in over.exceptions if item.code == exception.code)
    explanation = explain_exception(
        proposed,
        MockAIReviewer(),
        invoice_number=SCENARIOS[0].invoice_number,
        case_id=f"{over.scope_key}:{exception.id}",
    )
    assert explanation.amounts_from_engine is True
    case = create_review_case(
        session, exception=exception, result=explanation.ai_result, actor="demo"
    )
    session.commit()

    listed = api_client.get("/exceptions")
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1

    detail = api_client.get(f"/reconciliations/{over.run_id}")
    assert detail.status_code == 200
    assert detail.json()["exceptions"]

    api_client.post(f"/reviews/{case.id}/start", json={"reviewer": "alice"})
    rejected = api_client.post(
        f"/reviews/{case.id}/reject",
        json={"reviewer": "alice", "reason": "invoice quantity is wrong"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    audit = api_client.get("/audit")
    assert audit.status_code == 200
    assert audit.json()["total"] >= 1
    assert session.scalar(select(ReviewAuditEvent).limit(1)) is not None
