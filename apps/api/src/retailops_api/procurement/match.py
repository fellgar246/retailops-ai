"""Deterministic identity matching for purchase-order, receipt and invoice lines.

Order of strategies, first to last:

1. exact supplier + purchase-order number (header)
2. exact product identity
3. supplier SKU on that supplier's terms
4. EAN on the catalog, when the barcode is present and unique

A strategy that finds nothing is skipped. Two strategies that find *different*
products, or one strategy that finds more than one line, produce an ambiguous
match. Nothing is guessed.
"""

from __future__ import annotations

from dataclasses import dataclass

from retailops_api.procurement.types import (
    AMBIGUOUS_LINE,
    UNMATCHED_LINE,
    UNMATCHED_PURCHASE_ORDER,
    GoodsReceiptLineView,
    GoodsReceiptView,
    IdentityIndex,
    PurchaseOrderLineView,
    PurchaseOrderView,
    SupplierInvoiceLineView,
    SupplierInvoiceView,
)


@dataclass(frozen=True)
class LineMatch:
    po_line: PurchaseOrderLineView | None
    product_id: int | None
    issue_code: str | None
    issue_message: str | None


def belongs_to_order(
    po_number: str | None, purchase_order_id: int | None, order: PurchaseOrderView
) -> bool:
    if purchase_order_id is not None:
        return purchase_order_id == order.id
    if po_number:
        return po_number == order.number
    return False


def invoices_for_order(
    invoices: tuple[SupplierInvoiceView, ...], order: PurchaseOrderView
) -> tuple[SupplierInvoiceView, ...]:
    return tuple(
        invoice
        for invoice in invoices
        if belongs_to_order(invoice.po_number, invoice.purchase_order_id, order)
    )


def receipts_for_order(
    receipts: tuple[GoodsReceiptView, ...], order: PurchaseOrderView
) -> tuple[GoodsReceiptView, ...]:
    return tuple(
        receipt
        for receipt in receipts
        if belongs_to_order(receipt.po_number, receipt.purchase_order_id, order)
    )


def unmatched_purchase_order_message(invoice: SupplierInvoiceView) -> str:
    if invoice.po_number:
        return (
            f"invoice {invoice.number} cites purchase order {invoice.po_number} "
            "which was not found for this supplier"
        )
    return f"invoice {invoice.number} has no purchase order"


def match_receipt_line(line: GoodsReceiptLineView, order: PurchaseOrderView) -> LineMatch:
    if line.purchase_order_line_id is not None:
        found = [item for item in order.lines if item.id == line.purchase_order_line_id]
        if len(found) == 1:
            return LineMatch(found[0], found[0].product_id, None, None)
        return LineMatch(
            None,
            line.product_id,
            UNMATCHED_LINE,
            (
                f"receipt line {line.line_number} cites a purchase order line "
                f"that is not on {order.number}"
            ),
        )
    return _po_lines_for_product(
        order,
        line.product_id,
        role="receipt",
        line_number=line.line_number,
    )


def match_invoice_line(
    line: SupplierInvoiceLineView,
    order: PurchaseOrderView,
    index: IdentityIndex,
) -> LineMatch:
    product_id, issue = resolve_invoice_product(line, index)
    if issue is not None:
        return issue
    if product_id is None:
        return LineMatch(
            None,
            None,
            UNMATCHED_LINE,
            f"invoice line {line.line_number} has no product, supplier SKU or EAN that resolves",
        )
    return _po_lines_for_product(
        order,
        product_id,
        role="invoice",
        line_number=line.line_number,
    )


def resolve_invoice_product(
    line: SupplierInvoiceLineView, index: IdentityIndex
) -> tuple[int | None, LineMatch | None]:
    """Return ``(product_id, None)`` or ``(None, ambiguous LineMatch)``."""
    found: list[tuple[str, int]] = []
    if line.product_id is not None:
        found.append(("product", line.product_id))
    if line.supplier_sku:
        mapped = index.product_ids_for_supplier_sku(line.supplier_sku)
        if len(mapped) > 1:
            return None, LineMatch(
                None,
                None,
                AMBIGUOUS_LINE,
                (
                    f"invoice line {line.line_number} supplier SKU {line.supplier_sku!r} "
                    "maps to more than one product"
                ),
            )
        if len(mapped) == 1:
            found.append(("supplier_sku", mapped[0]))
    if line.ean:
        ean_product = index.product_id_for_ean(line.ean)
        if ean_product is not None:
            found.append(("ean", ean_product))
    products = {product_id for _strategy, product_id in found}
    if len(products) > 1:
        listed = ", ".join(sorted({f"{strategy}={product_id}" for strategy, product_id in found}))
        return None, LineMatch(
            None,
            None,
            AMBIGUOUS_LINE,
            f"invoice line {line.line_number} resolved to different products ({listed})",
        )
    if not products:
        return None, None
    return products.pop(), None


def _po_lines_for_product(
    order: PurchaseOrderView,
    product_id: int,
    *,
    role: str,
    line_number: int,
) -> LineMatch:
    found = [item for item in order.lines if item.product_id == product_id]
    if len(found) == 1:
        return LineMatch(found[0], product_id, None, None)
    if len(found) > 1:
        return LineMatch(
            None,
            product_id,
            AMBIGUOUS_LINE,
            (
                f"{role} line {line_number} matches {len(found)} lines of "
                f"product {product_id} on {order.number}"
            ),
        )
    return LineMatch(
        None,
        product_id,
        UNMATCHED_LINE,
        f"{role} line {line_number} does not match a line on purchase order {order.number}",
    )


# Imported by evaluate() so a missing PO still has a stable code.
__all__ = [
    "AMBIGUOUS_LINE",
    "UNMATCHED_LINE",
    "UNMATCHED_PURCHASE_ORDER",
    "LineMatch",
    "belongs_to_order",
    "invoices_for_order",
    "match_invoice_line",
    "match_receipt_line",
    "receipts_for_order",
    "resolve_invoice_product",
    "unmatched_purchase_order_message",
]
