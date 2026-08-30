from collections.abc import Sequence
from decimal import Decimal

from retailops_api.procurement.money import line_amounts
from retailops_api.procurement.rules import (
    check_line_total_invoice,
    check_price,
    check_quantities,
)
from retailops_api.procurement.types import (
    COST_MISMATCH,
    INVOICE_WITHOUT_RECEIPT,
    LINE_TOTAL_MISMATCH,
    OVER_INVOICE,
    OVER_RECEIPT,
    SHORT_RECEIPT,
    UNDER_INVOICE,
    UNEXPECTED_TAX,
    GoodsReceiptLineView,
    ProposedException,
    PurchaseOrderLineView,
    PurchaseOrderView,
    ReconciliationTolerances,
    SupplierInvoiceLineView,
    SupplierInvoiceView,
)

COST = Decimal("7.4500")
TAX = Decimal("16.0000")


def _order_line(quantity: int = 10, unit_cost: Decimal = COST) -> PurchaseOrderLineView:
    _ext, tax_amount, total = line_amounts(quantity, unit_cost, TAX)
    return PurchaseOrderLineView(
        id=1,
        line_number=1,
        product_id=100,
        ordered_quantity=quantity,
        unit_cost=unit_cost,
        tax_rate=TAX,
        tax_amount=tax_amount,
        line_total=total,
    )


def _order(line: PurchaseOrderLineView) -> PurchaseOrderView:
    return PurchaseOrderView(
        id=1,
        number="PO-1",
        supplier_id=10,
        store_id=20,
        currency="MXN",
        status="open",
        lines=(line,),
    )


def _receipt(quantity: int) -> list[tuple[int, GoodsReceiptLineView]]:
    return [
        (
            2,
            GoodsReceiptLineView(
                id=3,
                goods_receipt_id=2,
                line_number=1,
                product_id=100,
                purchase_order_line_id=1,
                received_quantity=quantity,
            ),
        )
    ]


def _invoice_line(
    quantity: int, unit_cost: Decimal = COST, tax_rate: Decimal = TAX
) -> tuple[SupplierInvoiceView, SupplierInvoiceLineView]:
    _ext, tax_amount, total = line_amounts(quantity, unit_cost, tax_rate)
    invoice = SupplierInvoiceView(
        id=5,
        number="INV-1",
        supplier_id=10,
        purchase_order_id=1,
        po_number="PO-1",
        currency="MXN",
        status="received",
        lines=(),
    )
    line = SupplierInvoiceLineView(
        id=6,
        supplier_invoice_id=5,
        line_number=1,
        product_id=100,
        supplier_sku=None,
        ean=None,
        invoiced_quantity=quantity,
        unit_cost=unit_cost,
        tax_rate=tax_rate,
        tax_amount=tax_amount,
        line_total=total,
    )
    return invoice, line


def _codes(exceptions: Sequence[ProposedException]) -> set[str]:
    return {item.code for item in exceptions}


def test_short_receipt_when_received_is_below_ordered() -> None:
    po_line = _order_line(10)
    invoice, line = _invoice_line(6)
    found = check_quantities(
        _order(po_line), po_line, _receipt(6), [(invoice, line)], ReconciliationTolerances()
    )

    assert _codes(found) == {SHORT_RECEIPT}
    short = next(item for item in found if item.code == SHORT_RECEIPT)
    assert short.expected_value == "10"
    assert short.actual_value == "6"
    assert short.financial_impact == Decimal("-29.8000")


def test_over_receipt_when_received_exceeds_ordered() -> None:
    po_line = _order_line(10)
    invoice, line = _invoice_line(12)
    found = check_quantities(
        _order(po_line), po_line, _receipt(12), [(invoice, line)], ReconciliationTolerances()
    )

    assert OVER_RECEIPT in _codes(found)


def test_over_invoice_compares_invoiced_to_received() -> None:
    po_line = _order_line(10)
    invoice, line = _invoice_line(12)
    found = check_quantities(
        _order(po_line), po_line, _receipt(10), [(invoice, line)], ReconciliationTolerances()
    )

    assert _codes(found) == {OVER_INVOICE}
    assert found[0].financial_impact == Decimal("14.9000")


def test_under_invoice_when_invoiced_is_below_received() -> None:
    po_line = _order_line(10)
    invoice, line = _invoice_line(8)
    found = check_quantities(
        _order(po_line), po_line, _receipt(10), [(invoice, line)], ReconciliationTolerances()
    )

    assert _codes(found) == {UNDER_INVOICE}


def test_invoice_without_receipt_when_nothing_arrived() -> None:
    po_line = _order_line(10)
    invoice, line = _invoice_line(10)
    found = check_quantities(
        _order(po_line), po_line, [], [(invoice, line)], ReconciliationTolerances()
    )

    assert INVOICE_WITHOUT_RECEIPT in _codes(found)
    assert SHORT_RECEIPT in _codes(found)


def test_quantity_tolerance_absorbs_a_one_unit_gap() -> None:
    po_line = _order_line(10)
    invoice, line = _invoice_line(10)
    found = check_quantities(
        _order(po_line),
        po_line,
        _receipt(9),
        [(invoice, line)],
        ReconciliationTolerances(quantity_tolerance=1),
    )

    assert _codes(found) == set()


def test_quantity_tolerance_still_fails_beyond_the_band() -> None:
    po_line = _order_line(10)
    found = check_quantities(
        _order(po_line),
        po_line,
        _receipt(8),
        [],
        ReconciliationTolerances(quantity_tolerance=1),
    )

    assert SHORT_RECEIPT in _codes(found)


def test_cost_mismatch_uses_decimal_arithmetic() -> None:
    po_line = _order_line(10, COST)
    invoice, line = _invoice_line(10, Decimal("8.0000"))
    found = check_price(_order(po_line), po_line, invoice, line, ReconciliationTolerances())

    assert COST_MISMATCH in _codes(found)
    mismatch = next(item for item in found if item.code == COST_MISMATCH)
    assert mismatch.financial_impact == Decimal("5.5000")


def test_monetary_tolerance_passes_a_small_cost_gap() -> None:
    po_line = _order_line(10, COST)
    invoice, line = _invoice_line(10, Decimal("7.4550"))
    found = check_price(
        _order(po_line),
        po_line,
        invoice,
        line,
        ReconciliationTolerances(monetary_tolerance=Decimal("0.0100")),
    )

    assert COST_MISMATCH not in _codes(found)


def test_percent_tolerance_passes_a_one_percent_cost_gap() -> None:
    po_line = _order_line(10, Decimal("10.0000"))
    invoice, line = _invoice_line(10, Decimal("10.1000"))
    found = check_price(
        _order(po_line),
        po_line,
        invoice,
        line,
        ReconciliationTolerances(price_percent_tolerance=Decimal("1.0000")),
    )

    assert COST_MISMATCH not in _codes(found)


def test_unexpected_tax_when_rates_differ() -> None:
    po_line = _order_line(10)
    invoice, line = _invoice_line(10, COST, Decimal("8.0000"))
    found = check_price(_order(po_line), po_line, invoice, line, ReconciliationTolerances())

    assert UNEXPECTED_TAX in _codes(found)


def test_line_total_mismatch_when_the_stored_total_is_wrong() -> None:
    invoice, line = _invoice_line(10)
    broken = SupplierInvoiceLineView(**{**line.__dict__, "line_total": Decimal("1.0000")})
    found = check_line_total_invoice(invoice, broken, ReconciliationTolerances())

    assert _codes(found) == {LINE_TOTAL_MISMATCH}
