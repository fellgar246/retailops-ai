"""Operations overview, search and recent audit events."""

from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from retailops_api.forecasting.models import ForecastPoint
from retailops_api.forecasting.persist import persist_run
from tests.factories import make_reconciliation_exception, make_supplier, make_supplier_document
from tests.review_support import finding_case


def test_overview_uses_persisted_counts(api_client: TestClient, session: Session) -> None:
    persist_run(
        session,
        model_id="naive",
        generated_at=datetime(2026, 8, 30, 13, 32, tzinfo=UTC),
        cutoff=date(2025, 6, 2),
        horizon=2,
        problem_id="weekly_category_store_demand",
        predictions=(ForecastPoint("ST-001", "BEV-SOFT", date(2025, 6, 9), 1, 10.0, actual=9.0),),
        run_metadata={"overall_metrics": {"mae": 1.0, "rmse": 1.0, "wape": 0.1, "bias": 0.0}},
    )
    supplier = make_supplier(session, code="SUP-OPS")
    make_supplier_document(session, supplier, status="review_ready", storage_key="c" * 32)
    make_reconciliation_exception(session)
    finding_case(session, supplier_code="SUP-OPS-R")
    session.commit()

    response = api_client.get("/ops/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["forecasts"]["run_count"] == 1
    assert body["forecasts"]["latest"]["model_id"] == "naive"
    assert body["documents"]["awaiting_review"] == 1
    assert body["reconciliation"]["open_exceptions"] == 1
    assert body["reviews"]["open_cases"] == 1
    assert body["environment"]


def test_search_finds_documents_and_reviews(api_client: TestClient, session: Session) -> None:
    case = finding_case(session, supplier_code="SUP-FIND")
    session.commit()

    empty = api_client.get("/search", params={"q": ""})
    assert empty.status_code == 200
    assert empty.json()["documents"] == []

    found = api_client.get("/search", params={"q": "SUP-FIND"})
    assert found.status_code == 200
    assert {item["id"] for item in found.json()["reviews"]} == {case.id}
    assert found.json()["documents"]


def test_audit_lists_recent_events(api_client: TestClient, session: Session) -> None:
    case = finding_case(session, supplier_code="SUP-AUD")
    session.commit()

    response = api_client.get("/audit")
    assert response.status_code == 200
    assert response.json()["total"] >= 1
    assert any(item["review_case_id"] == case.id for item in response.json()["items"])
