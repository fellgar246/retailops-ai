"""Visible, recoverable failures on the local stack."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from retailops_api.db.seed import seed_reference_data
from retailops_api.demo.sales import seed_and_ingest_sales
from retailops_api.documents.process import process_document
from retailops_api.documents.storage import LocalDocumentStorage
from retailops_api.forecasting.artifact import load_artifact
from retailops_api.review.mock import MockAIReviewer, MockBehavior
from retailops_api.review.supplier import review_from_process_result
from tests.demo_support import load_demo


def test_database_health_reports_when_the_server_is_unreachable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "retailops_api.api.routes.health.check_database_connection",
        lambda: False,
    )
    response = client.get("/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "degraded", "database": "unavailable"}


def test_a_malformed_supplier_file_is_stored_with_parse_findings(
    session: Session, tmp_path: Path
) -> None:
    seed_reference_data(session)
    result = process_document(
        session,
        LocalDocumentStorage(tmp_path / "documents"),
        supplier_code="SUP-BEVCO",
        filename="broken.csv",
        data=b"this is not a supplier offer sheet",
    )
    assert result.status == "parse_failed"
    assert result.findings
    assert result.document_id > 0


def test_a_mock_reviewer_failure_leaves_deterministic_findings(
    session: Session, tmp_path: Path
) -> None:
    seed_reference_data(session)
    processed = process_document(
        session,
        LocalDocumentStorage(tmp_path / "documents"),
        supplier_code="SUP-BEVCO",
        filename="demo-cost-increase.csv",
        data=(
            b"supplier_sku,ean,description,category,cost,vat,"
            b"case_pack,minimum_order_quantity,lead_time_days\n"
            b"BC-COLA-355,7501000110018,Cola Classic 355ml Can,BEV-SOFT,9.0000,16,24,2,3\n"
        ),
    )
    assert processed.findings
    outcome = review_from_process_result(
        processed, MockAIReviewer(default_behavior=MockBehavior.provider_failure)
    )
    assert outcome.ai_result is None
    assert outcome.source_of_truth == processed.findings
    assert outcome.routing.status.value == "failed_safe"


def test_approving_an_open_case_is_rejected(
    api_client: TestClient, session: Session, tmp_path: Path
) -> None:
    report = load_demo(session, tmp_path)
    session.commit()
    case_id = report.review_case_ids[0]
    opened = api_client.get(f"/reviews/{case_id}")
    assert opened.json()["status"] == "open"
    response = api_client.post(
        f"/reviews/{case_id}/approve", json={"reviewer": "alice", "comment": "too soon"}
    )
    assert response.status_code == 409
    assert api_client.get(f"/reviews/{case_id}").json()["status"] == "open"


def test_re_ingesting_sales_counts_duplicates_instead_of_failing(
    session: Session, tmp_path: Path
) -> None:
    _, _, first = seed_and_ingest_sales(session, preset="tiny", output=tmp_path / "synthetic")
    _, _, second = seed_and_ingest_sales(session, preset="tiny", output=tmp_path / "synthetic")
    assert first.rows_accepted > 0
    assert second.duplicate_count == first.rows_accepted
    assert second.rows_rejected == 0


def test_an_incomplete_model_package_is_refused(tmp_path: Path) -> None:
    empty = tmp_path / "missing-artifact"
    empty.mkdir()
    with pytest.raises(FileNotFoundError, match="incomplete model artifact"):
        load_artifact(empty)
