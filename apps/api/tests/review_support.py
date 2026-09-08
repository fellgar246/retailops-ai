"""Shared builders for human-review tests."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from retailops_api.domain.models.review import ReviewCase
from retailops_api.identity.types import Principal, Role
from retailops_api.review.mock import canned_output
from retailops_api.review.persist import create_review_case
from retailops_api.review.schemas import parse_review_result
from retailops_api.review.types import ReviewType
from tests.factories import (
    make_document_finding,
    make_reconciliation_exception,
    make_supplier,
    make_supplier_document,
    make_supplier_invoice,
)


def person(name: str, *, role: Role = Role.reviewer) -> Principal:
    """A verified principal standing in for a signed-in operator."""

    return Principal(
        subject=f"subject-{name}",
        display_name=name,
        email=f"{name}@example.test",
        roles=frozenset({role}),
    )


def finding_case(
    session: Session, *, supplier_code: str = "SUP-REV-1", **result_overrides: Any
) -> ReviewCase:
    supplier = make_supplier(session, code=supplier_code)
    document = make_supplier_document(session, supplier, storage_key=supplier_code.ljust(32, "0"))
    finding = make_document_finding(session, document)
    result = parse_review_result(canned_output(ReviewType.category_suggestion, **result_overrides))
    return create_review_case(session, finding=finding, result=result)


def exception_case(
    session: Session,
    *,
    supplier_code: str = "SUP-REV-X",
    financial_impact: Decimal = Decimal("14.9000"),
    **result_overrides: Any,
) -> ReviewCase:
    supplier = make_supplier(session, code=supplier_code)
    invoice = make_supplier_invoice(session, supplier, invoice_number=f"INV-{supplier_code}")
    exception = make_reconciliation_exception(
        session, supplier_invoice=invoice, financial_impact=financial_impact
    )
    payload = canned_output(ReviewType.reconciliation_explanation, **result_overrides)
    return create_review_case(session, exception=exception, result=parse_review_result(payload))
