"""HTTP reconciliation runs and exceptions."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import (
    make_purchase_order,
    make_reconciliation_exception,
    make_reconciliation_run,
    make_store,
    make_supplier,
    make_supplier_invoice,
)


def test_list_runs_and_exceptions(api_client: TestClient, session: Session) -> None:
    supplier = make_supplier(session, code="SUP-REC")
    store = make_store(session, code="ST-REC")
    order = make_purchase_order(session, supplier, store, po_number="PO-REC")
    invoice = make_supplier_invoice(
        session, supplier, invoice_number="INV-REC", purchase_order=order
    )
    run = make_reconciliation_run(session, scope_key="po:SUP-REC:PO-REC")
    exception = make_reconciliation_exception(
        session, run, supplier_invoice=invoice, purchase_order=order
    )
    session.commit()

    listed = api_client.get("/reconciliations")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["scope_key"] == "po:SUP-REC:PO-REC"
    assert listed.json()["items"][0]["open_exception_count"] == 1

    detail = api_client.get(f"/reconciliations/{run.id}")
    assert detail.status_code == 200
    assert detail.json()["tolerances"]["quantity_tolerance"] == 0
    row = detail.json()["exceptions"][0]
    assert row["id"] == exception.id
    assert row["purchase_order"]["number"] == "PO-REC"
    assert row["supplier_invoice"]["number"] == "INV-REC"
    assert row["provenance"] == "rule"

    exceptions = api_client.get("/exceptions", params={"severity": "error"})
    assert exceptions.status_code == 200
    assert exceptions.json()["total"] == 1


def test_unknown_reconciliation_is_not_found(api_client: TestClient) -> None:
    assert api_client.get("/reconciliations/9999").status_code == 404
