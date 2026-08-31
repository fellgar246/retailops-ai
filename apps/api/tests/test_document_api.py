"""HTTP supplier-document list and detail."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from retailops_api.api.routes.documents import get_document_storage
from retailops_api.db.seed import seed_reference_data
from retailops_api.documents.process import process_document
from retailops_api.documents.storage import LocalDocumentStorage
from tests.factories import make_document_finding, make_supplier, make_supplier_document

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "supplier_documents"


def test_list_documents_includes_severity(api_client: TestClient, session: Session) -> None:
    supplier = make_supplier(session, code="SUP-DOC")
    document = make_supplier_document(
        session, supplier, filename="offer.csv", status="review_ready", storage_key="d" * 32
    )
    make_document_finding(session, document, severity="error")
    make_document_finding(
        session, document, code="cost_increase", field="cost", severity="warning", message="up"
    )
    session.commit()

    listed = api_client.get("/documents")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    item = listed.json()["items"][0]
    assert item["filename"] == "offer.csv"
    assert item["supplier_code"] == "SUP-DOC"
    assert item["finding_count"] == 2
    assert item["severity_summary"]["error"] == 1
    assert item["severity_summary"]["warning"] == 1


def test_document_detail_includes_findings_and_rows(
    api_client: TestClient, app: FastAPI, session: Session, tmp_path: Path
) -> None:
    seed_reference_data(session)
    storage = LocalDocumentStorage(tmp_path)
    result = process_document(
        session,
        storage,
        supplier_code="SUP-BEVCO",
        filename="valid.csv",
        data=(FIXTURES / "valid.csv").read_bytes(),
    )
    session.commit()
    app.dependency_overrides[get_document_storage] = lambda: storage

    detail = api_client.get(f"/documents/{result.document_id}")
    app.dependency_overrides.pop(get_document_storage, None)
    assert detail.status_code == 200
    body = detail.json()
    assert body["rows_available"] is True
    assert len(body["rows"]) == 2
    assert body["rows"][0]["provenance"] == "extracted"
    assert all(item["provenance"] == "rule" for item in body["findings"])


def test_unknown_document_is_not_found(api_client: TestClient) -> None:
    assert api_client.get("/documents/9999").status_code == 404
