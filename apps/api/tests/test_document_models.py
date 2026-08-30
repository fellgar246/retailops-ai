"""Supplier documents and findings: lifecycle, ownership and constraints."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from retailops_api.domain.models import DocumentFinding, SupplierDocument
from retailops_api.domain.models.document import DocumentStatus, DocumentType, FindingSeverity
from tests.factories import make_document_finding, make_supplier, make_supplier_document


def test_a_document_records_storage_and_starts_received(session: Session) -> None:
    supplier = make_supplier(session, code="SUP-BEVCO")
    document = make_supplier_document(session, supplier, filename="offer.csv")

    assert document.id is not None
    assert document.status == DocumentStatus.received.value
    assert document.document_type == DocumentType.supplier_sheet.value
    assert document.active is True
    assert document.created_at is not None
    assert document.updated_at is not None


def test_findings_carry_code_field_row_and_proposed_value(session: Session) -> None:
    supplier = make_supplier(session)
    document = make_supplier_document(session, supplier)
    finding = make_document_finding(
        session,
        document,
        code="cost_increase",
        field="cost",
        row_reference=2,
        severity=FindingSeverity.warning.value,
        message="cost rose",
        proposed_value="7.4500",
    )
    session.refresh(document)

    assert finding.document_id == document.id
    assert document.findings[0].proposed_value == "7.4500"
    assert document.findings[0].row_reference == 2


def test_deleting_a_document_removes_its_findings(session: Session) -> None:
    supplier = make_supplier(session)
    document = make_supplier_document(session, supplier)
    make_document_finding(session, document)
    session.flush()

    session.delete(document)
    session.flush()

    assert session.scalars(select(SupplierDocument)).all() == []
    assert session.scalars(select(DocumentFinding)).all() == []


def test_storage_key_is_unique(session: Session) -> None:
    supplier = make_supplier(session)
    make_supplier_document(session, supplier, storage_key="c" * 32)

    with pytest.raises(IntegrityError):
        make_supplier_document(session, supplier, filename="other.csv", storage_key="c" * 32)


def test_unknown_status_is_rejected(session: Session) -> None:
    supplier = make_supplier(session)

    with pytest.raises(IntegrityError):
        make_supplier_document(session, supplier, status="invented")


def test_unknown_severity_is_rejected(session: Session) -> None:
    supplier = make_supplier(session)
    document = make_supplier_document(session, supplier)

    with pytest.raises(IntegrityError):
        make_document_finding(session, document, severity="critical")
