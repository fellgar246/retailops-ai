"""End-to-end three-way match scenarios against the persisted documents."""

from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from retailops_api.domain.models import ReconciliationRun
from retailops_api.procurement.orchestrate import reconcile
from retailops_api.procurement.types import (
    AMBIGUOUS_LINE,
    COST_MISMATCH,
    CURRENCY_MISMATCH,
    INVOICE_WITHOUT_RECEIPT,
    OVER_INVOICE,
    SHORT_RECEIPT,
    UNMATCHED_LINE,
    UNMATCHED_PURCHASE_ORDER,
    ReconciliationError,
    ReconciliationResult,
    ReconciliationScope,
    ReconciliationTolerances,
)
from tests.factories import (
    make_product,
    make_purchase_order,
    make_purchase_order_line,
    make_store,
    make_supplier,
    make_supplier_invoice,
    make_supplier_invoice_line,
)
from tests.procurement_support import build_three_way


def _run(session: Session, invoice_number: str = "INV-1001") -> ReconciliationResult:
    return reconcile(
        session,
        ReconciliationScope(supplier_code="SUP-BEVCO", invoice_number=invoice_number),
    )


def test_perfect_three_way_match_has_no_exceptions(session: Session) -> None:
    build_three_way(session, ordered=10, received=10, invoiced=10)
    result = _run(session)

    assert result.exception_count == 0
    assert result.version == 1
    assert result.reused is False
    assert session.query(ReconciliationRun).count() == 1


def test_partial_delivery_is_a_short_receipt(session: Session) -> None:
    build_three_way(session, ordered=100, received=40, invoiced=40)
    result = _run(session)

    assert SHORT_RECEIPT in {item.code for item in result.exceptions}
    assert OVER_INVOICE not in {item.code for item in result.exceptions}


def test_over_invoice_quantifies_the_extra_units(session: Session) -> None:
    build_three_way(session, ordered=10, received=10, invoiced=12)
    result = _run(session)

    over = next(item for item in result.exceptions if item.code == OVER_INVOICE)
    assert over.expected_value == "10"
    assert over.actual_value == "12"
    assert over.financial_impact == Decimal("14.9000")


def test_price_mismatch_is_a_cost_exception(session: Session) -> None:
    build_three_way(
        session,
        ordered=10,
        received=10,
        invoiced=10,
        po_cost=Decimal("7.4500"),
        invoice_cost=Decimal("8.0000"),
    )
    result = _run(session)

    assert COST_MISMATCH in {item.code for item in result.exceptions}


def test_missing_receipt_flags_the_invoice(session: Session) -> None:
    build_three_way(session, ordered=10, received=None, invoiced=10)
    result = _run(session)

    assert INVOICE_WITHOUT_RECEIPT in {item.code for item in result.exceptions}


def test_duplicate_invoice_number_is_rejected(session: Session) -> None:
    fixture = build_three_way(session)

    with pytest.raises(IntegrityError):
        make_supplier_invoice(session, fixture.supplier, invoice_number="INV-1001")


def test_unmatched_line_does_not_guess(session: Session) -> None:
    fixture = build_three_way(session, invoiced=None)
    invoice = make_supplier_invoice(
        session, fixture.supplier, invoice_number="INV-1001", purchase_order=fixture.order
    )
    make_supplier_invoice_line(
        session,
        invoice,
        product=None,
        supplier_sku="UNKNOWN-SKU",
        invoiced_quantity=10,
        unit_cost=Decimal("7.4500"),
        tax_rate=Decimal("16.0000"),
    )
    result = _run(session)

    assert UNMATCHED_LINE in {item.code for item in result.exceptions}


def test_ambiguous_product_on_the_order_is_not_guessed(session: Session) -> None:
    supplier = make_supplier(session, code="SUP-BEVCO")
    store = make_store(session, code="ST-001")
    product = make_product(session, sku="SKU-1001", ean="7501000110018")
    order = make_purchase_order(session, supplier, store, po_number="PO-1001")
    make_purchase_order_line(session, order, product, line_number=1, ordered_quantity=10)
    make_purchase_order_line(session, order, product, line_number=2, ordered_quantity=5)
    invoice = make_supplier_invoice(
        session, supplier, invoice_number="INV-1001", purchase_order=order
    )
    make_supplier_invoice_line(session, invoice, product=product, invoiced_quantity=10)
    result = _run(session)

    assert AMBIGUOUS_LINE in {item.code for item in result.exceptions}


def test_tolerance_pass_writes_no_quantity_exception(session: Session) -> None:
    build_three_way(session, ordered=10, received=9, invoiced=9)
    result = reconcile(
        session,
        ReconciliationScope(supplier_code="SUP-BEVCO", invoice_number="INV-1001"),
        tolerances=ReconciliationTolerances(quantity_tolerance=1),
    )

    assert SHORT_RECEIPT not in {item.code for item in result.exceptions}


def test_tolerance_fail_keeps_the_quantity_exception(session: Session) -> None:
    build_three_way(session, ordered=10, received=8, invoiced=8)
    result = reconcile(
        session,
        ReconciliationScope(supplier_code="SUP-BEVCO", invoice_number="INV-1001"),
        tolerances=ReconciliationTolerances(quantity_tolerance=1),
    )

    assert SHORT_RECEIPT in {item.code for item in result.exceptions}


def test_currency_mismatch_is_never_tolerated(session: Session) -> None:
    build_three_way(session, invoice_currency="USD")
    result = _run(session)

    assert CURRENCY_MISMATCH in {item.code for item in result.exceptions}


def test_invoice_without_a_purchase_order_is_unmatched(session: Session) -> None:
    supplier = make_supplier(session, code="SUP-BEVCO")
    invoice = make_supplier_invoice(session, supplier, invoice_number="INV-9", po_number=None)
    make_supplier_invoice_line(
        session, invoice, invoiced_quantity=3, unit_cost=Decimal("1.0000"), tax_rate=Decimal("0")
    )
    result = reconcile(
        session, ReconciliationScope(supplier_code="SUP-BEVCO", invoice_number="INV-9")
    )

    assert UNMATCHED_PURCHASE_ORDER in {item.code for item in result.exceptions}


def test_a_second_call_with_the_same_inputs_reuses_the_run(session: Session) -> None:
    build_three_way(session)
    first = _run(session)
    second = _run(session)

    assert second.reused is True
    assert second.run_id == first.run_id
    assert second.version == 1
    assert session.query(ReconciliationRun).count() == 1


def test_a_changed_quantity_writes_the_next_version(session: Session) -> None:
    fixture = build_three_way(session, received=10, invoiced=10)
    first = _run(session)
    assert fixture.receipt is not None
    fixture.receipt.lines[0].received_quantity = 7
    session.flush()
    second = _run(session)

    assert second.reused is False
    assert second.version == 2
    assert second.run_id != first.run_id
    assert session.query(ReconciliationRun).count() == 2
    assert SHORT_RECEIPT in {item.code for item in second.exceptions}


def test_unknown_supplier_does_not_write_a_run(session: Session) -> None:
    with pytest.raises(ReconciliationError, match="unknown supplier"):
        reconcile(session, ReconciliationScope(supplier_code="SUP-NOPE", invoice_number="INV-1"))

    assert session.query(ReconciliationRun).count() == 0


def test_reconciling_by_purchase_order_number(session: Session) -> None:
    build_three_way(session, ordered=10, received=10, invoiced=12)
    result = reconcile(session, ReconciliationScope(supplier_code="SUP-BEVCO", po_number="PO-1001"))

    assert OVER_INVOICE in {item.code for item in result.exceptions}
    assert result.scope_key == "po:SUP-BEVCO:PO-1001"
