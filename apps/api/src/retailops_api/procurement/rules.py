"""Quantity and price comparisons, plus the full evaluate pass.

Rules are plain functions: they take views and tolerances and return proposed
exceptions. They do not read or write the database.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal

from retailops_api.dataset.contract import quantize_money
from retailops_api.procurement.match import (
    invoices_for_order,
    match_invoice_line,
    match_receipt_line,
    receipts_for_order,
    unmatched_purchase_order_message,
)
from retailops_api.procurement.money import (
    format_money,
    format_quantity,
    format_rate,
    line_amounts,
    money_within,
    quantity_within,
)
from retailops_api.procurement.types import (
    COST_MISMATCH,
    CURRENCY_MISMATCH,
    INVOICE_WITHOUT_RECEIPT,
    LINE_TOTAL_MISMATCH,
    OVER_INVOICE,
    OVER_RECEIPT,
    SEVERITY_BY_CODE,
    SHORT_RECEIPT,
    UNDER_INVOICE,
    UNEXPECTED_TAX,
    UNMATCHED_LINE,
    UNMATCHED_PURCHASE_ORDER,
    GoodsReceiptLineView,
    IdentityIndex,
    ProposedException,
    PurchaseOrderLineView,
    PurchaseOrderView,
    ReconciliationDraft,
    ReconciliationTolerances,
    SelectedRecords,
    SupplierInvoiceLineView,
    SupplierInvoiceView,
)


def evaluate(
    records: SelectedRecords,
    index: IdentityIndex,
    tolerances: ReconciliationTolerances | None = None,
) -> ReconciliationDraft:
    settings = tolerances or ReconciliationTolerances()
    exceptions: list[ProposedException] = []

    if not records.purchase_orders:
        for invoice in records.invoices:
            exceptions.append(_unmatched_order(invoice))
            for line in invoice.lines:
                exceptions.extend(check_line_total_invoice(invoice, line, settings))
                exceptions.append(
                    _exception(
                        UNMATCHED_LINE,
                        message=f"invoice line {line.line_number} has no purchase order to match",
                        expected="purchase_order_line",
                        actual="none",
                        impact=quantize_money(line.line_total),
                        invoice=invoice,
                        invoice_line=line,
                        product_id=line.product_id,
                    )
                )
        return _draft(records, settings, exceptions)

    for order in records.purchase_orders:
        order_invoices = invoices_for_order(records.invoices, order)
        order_receipts = receipts_for_order(records.receipts, order)
        for invoice in order_invoices:
            if invoice.currency != order.currency:
                exceptions.append(_currency_mismatch(order, invoice, settings))
            for line in invoice.lines:
                exceptions.extend(check_line_total_invoice(invoice, line, settings))

        receipt_by_line: dict[int, list[tuple[int, GoodsReceiptLineView]]] = defaultdict(list)
        invoice_by_line: dict[int, list[tuple[SupplierInvoiceView, SupplierInvoiceLineView]]] = (
            defaultdict(list)
        )

        for receipt in order_receipts:
            for receipt_line in receipt.lines:
                matched = match_receipt_line(receipt_line, order)
                if matched.issue_code:
                    exceptions.append(
                        _exception(
                            matched.issue_code,
                            message=matched.issue_message or "",
                            expected="purchase_order_line",
                            actual="none",
                            impact=Decimal("0"),
                            order=order,
                            receipt_id=receipt.id,
                            receipt_line=receipt_line,
                            product_id=matched.product_id or receipt_line.product_id,
                        )
                    )
                    continue
                assert matched.po_line is not None
                receipt_by_line[matched.po_line.id].append((receipt.id, receipt_line))

        for invoice in order_invoices:
            for invoice_line in invoice.lines:
                matched = match_invoice_line(invoice_line, order, index)
                if matched.issue_code:
                    exceptions.append(
                        _exception(
                            matched.issue_code,
                            message=matched.issue_message or "",
                            expected="purchase_order_line",
                            actual="none",
                            impact=quantize_money(invoice_line.line_total),
                            order=order,
                            invoice=invoice,
                            invoice_line=invoice_line,
                            product_id=matched.product_id or invoice_line.product_id,
                        )
                    )
                    continue
                assert matched.po_line is not None
                invoice_by_line[matched.po_line.id].append((invoice, invoice_line))
                exceptions.extend(
                    check_price(order, matched.po_line, invoice, invoice_line, settings)
                )

        for po_line in order.lines:
            exceptions.extend(check_line_total_order(order, po_line, settings))
            receipts = receipt_by_line.get(po_line.id, [])
            invoices = invoice_by_line.get(po_line.id, [])
            exceptions.extend(check_quantities(order, po_line, receipts, invoices, settings))

    return _draft(records, settings, exceptions)


def check_quantities(
    order: PurchaseOrderView,
    po_line: PurchaseOrderLineView,
    receipts: Sequence[tuple[int, GoodsReceiptLineView]],
    invoices: Sequence[tuple[SupplierInvoiceView, SupplierInvoiceLineView]],
    tolerances: ReconciliationTolerances,
) -> list[ProposedException]:
    ordered = po_line.ordered_quantity
    received = sum(line.received_quantity for _receipt_id, line in receipts)
    invoiced = sum(line.invoiced_quantity for _invoice, line in invoices)
    receipt_id = receipts[0][0] if len(receipts) == 1 else None
    invoice = invoices[0][0] if invoices else None
    invoice_line = invoices[0][1] if len(invoices) == 1 else None
    unit = _invoice_unit_cost(invoices, po_line.unit_cost)
    found: list[ProposedException] = []

    if not quantity_within(ordered, received, tolerances.quantity_tolerance):
        if received < ordered:
            found.append(
                _exception(
                    SHORT_RECEIPT,
                    message=f"received {received} of {ordered} ordered",
                    expected=format_quantity(ordered),
                    actual=format_quantity(received),
                    impact=quantize_money(Decimal(received - ordered) * po_line.unit_cost),
                    order=order,
                    po_line=po_line,
                    receipt_id=receipt_id,
                    invoice=invoice,
                    invoice_line=invoice_line,
                    product_id=po_line.product_id,
                )
            )
        else:
            found.append(
                _exception(
                    OVER_RECEIPT,
                    message=f"received {received} of {ordered} ordered",
                    expected=format_quantity(ordered),
                    actual=format_quantity(received),
                    impact=quantize_money(Decimal(received - ordered) * po_line.unit_cost),
                    order=order,
                    po_line=po_line,
                    receipt_id=receipt_id,
                    invoice=invoice,
                    invoice_line=invoice_line,
                    product_id=po_line.product_id,
                )
            )

    if invoiced > 0 and received == 0:
        if not quantity_within(0, invoiced, tolerances.quantity_tolerance):
            found.append(
                _exception(
                    INVOICE_WITHOUT_RECEIPT,
                    message=f"invoiced {invoiced} with no receipt",
                    expected=format_quantity(0),
                    actual=format_quantity(invoiced),
                    impact=quantize_money(Decimal(invoiced) * unit),
                    order=order,
                    po_line=po_line,
                    invoice=invoice,
                    invoice_line=invoice_line,
                    product_id=po_line.product_id,
                )
            )
        return found

    if not quantity_within(received, invoiced, tolerances.quantity_tolerance):
        if invoiced > received:
            found.append(
                _exception(
                    OVER_INVOICE,
                    message=f"invoiced {invoiced} against {received} received",
                    expected=format_quantity(received),
                    actual=format_quantity(invoiced),
                    impact=quantize_money(Decimal(invoiced - received) * unit),
                    order=order,
                    po_line=po_line,
                    receipt_id=receipt_id,
                    invoice=invoice,
                    invoice_line=invoice_line,
                    product_id=po_line.product_id,
                )
            )
        elif invoiced < received:
            found.append(
                _exception(
                    UNDER_INVOICE,
                    message=f"invoiced {invoiced} against {received} received",
                    expected=format_quantity(received),
                    actual=format_quantity(invoiced),
                    impact=quantize_money(Decimal(invoiced - received) * unit),
                    order=order,
                    po_line=po_line,
                    receipt_id=receipt_id,
                    invoice=invoice,
                    invoice_line=invoice_line,
                    product_id=po_line.product_id,
                )
            )
    return found


def check_price(
    order: PurchaseOrderView,
    po_line: PurchaseOrderLineView,
    invoice: SupplierInvoiceView,
    line: SupplierInvoiceLineView,
    tolerances: ReconciliationTolerances,
) -> list[ProposedException]:
    found: list[ProposedException] = []
    if not money_within(
        po_line.unit_cost,
        line.unit_cost,
        monetary_tolerance=tolerances.monetary_tolerance,
        percent_tolerance=tolerances.price_percent_tolerance,
    ):
        found.append(
            _exception(
                COST_MISMATCH,
                message=(
                    f"invoice unit cost {format_money(line.unit_cost)} differs from "
                    f"PO {format_money(po_line.unit_cost)}"
                ),
                expected=format_money(po_line.unit_cost),
                actual=format_money(line.unit_cost),
                impact=quantize_money(
                    Decimal(line.invoiced_quantity) * (line.unit_cost - po_line.unit_cost)
                ),
                order=order,
                po_line=po_line,
                invoice=invoice,
                invoice_line=line,
                product_id=po_line.product_id,
            )
        )
    if not money_within(
        po_line.tax_rate,
        line.tax_rate,
        monetary_tolerance=tolerances.monetary_tolerance,
        percent_tolerance=tolerances.price_percent_tolerance,
    ):
        _extended, _, _ = line_amounts(line.invoiced_quantity, line.unit_cost, Decimal("0"))
        impact = quantize_money(_extended * (line.tax_rate - po_line.tax_rate) / Decimal("100"))
        found.append(
            _exception(
                UNEXPECTED_TAX,
                message=(
                    f"invoice tax rate {format_rate(line.tax_rate)} differs from "
                    f"PO {format_rate(po_line.tax_rate)}"
                ),
                expected=format_rate(po_line.tax_rate),
                actual=format_rate(line.tax_rate),
                impact=impact,
                order=order,
                po_line=po_line,
                invoice=invoice,
                invoice_line=line,
                product_id=po_line.product_id,
            )
        )
    return found


def check_line_total_invoice(
    invoice: SupplierInvoiceView,
    line: SupplierInvoiceLineView,
    tolerances: ReconciliationTolerances,
) -> list[ProposedException]:
    _extended, _tax, expected = line_amounts(line.invoiced_quantity, line.unit_cost, line.tax_rate)
    if money_within(
        expected,
        line.line_total,
        monetary_tolerance=tolerances.monetary_tolerance,
        percent_tolerance=tolerances.price_percent_tolerance,
    ):
        return []
    return [
        _exception(
            LINE_TOTAL_MISMATCH,
            message=(
                f"line total {format_money(line.line_total)} differs from "
                f"computed {format_money(expected)}"
            ),
            expected=format_money(expected),
            actual=format_money(line.line_total),
            impact=quantize_money(line.line_total - expected),
            invoice=invoice,
            invoice_line=line,
            product_id=line.product_id,
        )
    ]


def check_line_total_order(
    order: PurchaseOrderView,
    line: PurchaseOrderLineView,
    tolerances: ReconciliationTolerances,
) -> list[ProposedException]:
    _extended, _tax, expected = line_amounts(line.ordered_quantity, line.unit_cost, line.tax_rate)
    if money_within(
        expected,
        line.line_total,
        monetary_tolerance=tolerances.monetary_tolerance,
        percent_tolerance=tolerances.price_percent_tolerance,
    ):
        return []
    return [
        _exception(
            LINE_TOTAL_MISMATCH,
            message=(
                f"line total {format_money(line.line_total)} differs from "
                f"computed {format_money(expected)}"
            ),
            expected=format_money(expected),
            actual=format_money(line.line_total),
            impact=quantize_money(line.line_total - expected),
            order=order,
            po_line=line,
            product_id=line.product_id,
        )
    ]


def _currency_mismatch(
    order: PurchaseOrderView,
    invoice: SupplierInvoiceView,
    tolerances: ReconciliationTolerances,
) -> ProposedException:
    # Currency is never absorbed by a monetary tolerance.
    del tolerances
    impact = sum((line.line_total for line in invoice.lines), Decimal("0"))
    return _exception(
        CURRENCY_MISMATCH,
        message=f"invoice currency {invoice.currency} differs from PO {order.currency}",
        expected=order.currency,
        actual=invoice.currency,
        impact=quantize_money(impact),
        order=order,
        invoice=invoice,
    )


def _unmatched_order(invoice: SupplierInvoiceView) -> ProposedException:
    impact = sum((line.line_total for line in invoice.lines), Decimal("0"))
    return _exception(
        UNMATCHED_PURCHASE_ORDER,
        message=unmatched_purchase_order_message(invoice),
        expected="purchase_order",
        actual="none",
        impact=quantize_money(impact),
        invoice=invoice,
    )


def _invoice_unit_cost(
    invoices: Sequence[tuple[SupplierInvoiceView, SupplierInvoiceLineView]],
    fallback: Decimal,
) -> Decimal:
    invoiced = sum(line.invoiced_quantity for _invoice, line in invoices)
    if invoiced == 0:
        return fallback
    value = sum(
        (Decimal(line.invoiced_quantity) * line.unit_cost for _invoice, line in invoices),
        Decimal("0"),
    )
    return quantize_money(value / Decimal(invoiced))


def _exception(
    code: str,
    *,
    message: str,
    expected: str,
    actual: str,
    impact: Decimal,
    order: PurchaseOrderView | None = None,
    po_line: PurchaseOrderLineView | None = None,
    receipt_id: int | None = None,
    receipt_line: GoodsReceiptLineView | None = None,
    invoice: SupplierInvoiceView | None = None,
    invoice_line: SupplierInvoiceLineView | None = None,
    product_id: int | None = None,
) -> ProposedException:
    return ProposedException(
        code=code,
        severity=SEVERITY_BY_CODE[code],
        message=message,
        expected_value=expected,
        actual_value=actual,
        financial_impact=quantize_money(impact),
        purchase_order_id=order.id if order else None,
        purchase_order_line_id=po_line.id if po_line else None,
        goods_receipt_id=receipt_id,
        goods_receipt_line_id=receipt_line.id if receipt_line else None,
        supplier_invoice_id=invoice.id if invoice else None,
        supplier_invoice_line_id=invoice_line.id if invoice_line else None,
        product_id=product_id,
    )


def _draft(
    records: SelectedRecords,
    tolerances: ReconciliationTolerances,
    exceptions: list[ProposedException],
) -> ReconciliationDraft:
    ordered = _sorted(exceptions)
    return ReconciliationDraft(
        exceptions=tuple(ordered),
        purchase_order_ids=tuple(order.id for order in records.purchase_orders),
        goods_receipt_ids=tuple(receipt.id for receipt in records.receipts),
        supplier_invoice_ids=tuple(invoice.id for invoice in records.invoices),
        tolerances=tolerances,
    )


def _sorted(exceptions: Sequence[ProposedException]) -> list[ProposedException]:
    return sorted(
        exceptions,
        key=lambda item: (
            item.code,
            item.purchase_order_line_id or 0,
            item.supplier_invoice_line_id or 0,
            item.goods_receipt_line_id or 0,
            item.message,
        ),
    )
