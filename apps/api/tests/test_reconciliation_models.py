"""Reconciliation runs and exceptions: versioning, ownership and resolution."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from retailops_api.domain.models import ReconciliationException, ReconciliationRun
from retailops_api.domain.models.reconciliation import ExceptionResolution, ExceptionSeverity

GENERATED = datetime(2026, 8, 30, 16, 0, tzinfo=UTC)


def _add_run(session: Session, **overrides: object) -> ReconciliationRun:
    values: dict[str, Any] = {
        "scope_key": "po:SUP-BEVCO:PO-1001",
        "version": 1,
        "input_fingerprint": "a" * 64,
        "generated_at": GENERATED,
        "purchase_order_count": 1,
        "goods_receipt_count": 1,
        "supplier_invoice_count": 1,
        "exception_count": 0,
        "error_count": 0,
        "warning_count": 0,
        "info_count": 0,
        "total_financial_impact": Decimal("0.0000"),
        "tolerances": {
            "quantity_tolerance": 0,
            "monetary_tolerance": "0.0000",
            "price_percent_tolerance": "0.0000",
        },
    }
    values.update(overrides)
    run = ReconciliationRun(**values)
    session.add(run)
    session.flush()
    return run


def test_a_run_records_scope_version_and_summary(session: Session) -> None:
    run = _add_run(session, exception_count=2, error_count=1, warning_count=1)
    session.refresh(run)

    assert run.id is not None
    assert run.version == 1
    assert run.scope_key == "po:SUP-BEVCO:PO-1001"
    assert run.created_at is not None
    assert run.tolerances["quantity_tolerance"] == 0


def test_scope_and_version_are_unique(session: Session) -> None:
    _add_run(session, version=1)
    _add_run(session, version=2)

    with pytest.raises(IntegrityError):
        _add_run(session, version=1)


def test_an_exception_carries_code_values_impact_and_resolution(session: Session) -> None:
    run = _add_run(session, exception_count=1, error_count=1)
    row = ReconciliationException(
        reconciliation_run_id=run.id,
        code="over_invoice",
        severity=ExceptionSeverity.error.value,
        expected_value="10",
        actual_value="12",
        financial_impact=Decimal("14.9000"),
        message="invoiced 12 against 10 received",
    )
    session.add(row)
    session.flush()
    session.refresh(row)

    assert row.resolution_status == ExceptionResolution.open.value
    assert row.financial_impact == Decimal("14.9000")
    assert row.active is True
    assert row.updated_at is not None


def test_deleting_a_run_removes_its_exceptions(session: Session) -> None:
    run = _add_run(session, exception_count=1, error_count=1)
    session.add(
        ReconciliationException(
            reconciliation_run_id=run.id,
            code="short_receipt",
            severity=ExceptionSeverity.warning.value,
            expected_value="10",
            actual_value="8",
            financial_impact=Decimal("-14.9000"),
            message="received 8 of 10 ordered",
        )
    )
    session.flush()

    session.delete(run)
    session.flush()

    assert session.query(ReconciliationRun).count() == 0
    assert session.query(ReconciliationException).count() == 0


def test_unknown_severity_is_rejected(session: Session) -> None:
    run = _add_run(session)

    session.add(
        ReconciliationException(
            reconciliation_run_id=run.id,
            code="over_invoice",
            severity="critical",
            expected_value="1",
            actual_value="2",
            financial_impact=Decimal("0"),
            message="no",
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_version_must_be_at_least_one(session: Session) -> None:
    with pytest.raises(IntegrityError):
        _add_run(session, version=0)
