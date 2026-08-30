"""Load a reconciliation scope from the database into in-memory views."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from retailops_api.domain.models import (
    GoodsReceipt,
    Product,
    PurchaseOrder,
    SupplierInvoice,
    SupplierProduct,
)
from retailops_api.domain.models.goods_receipt import GoodsReceiptStatus
from retailops_api.domain.models.purchase_order import PurchaseOrderStatus
from retailops_api.domain.models.supplier_invoice import SupplierInvoiceStatus
from retailops_api.domain.repositories import get_supplier_by_code
from retailops_api.procurement.types import (
    GoodsReceiptLineView,
    GoodsReceiptView,
    IdentityIndex,
    PurchaseOrderLineView,
    PurchaseOrderView,
    ReconciliationError,
    ReconciliationScope,
    SelectedRecords,
    SupplierInvoiceLineView,
    SupplierInvoiceView,
)


def load_scope(session: Session, scope: ReconciliationScope) -> SelectedRecords:
    supplier = get_supplier_by_code(session, scope.supplier_code)
    if supplier is None:
        raise ReconciliationError(f"unknown supplier {scope.supplier_code!r}")

    invoice: SupplierInvoice | None = None
    order: PurchaseOrder | None = None

    if scope.invoice_number:
        invoice = _invoice_by_number(session, supplier.id, scope.invoice_number)
        if invoice is None:
            raise ReconciliationError(
                f"unknown invoice {scope.invoice_number!r} for supplier {scope.supplier_code!r}"
            )
        if invoice.status == SupplierInvoiceStatus.cancelled.value:
            raise ReconciliationError(f"invoice {scope.invoice_number!r} is cancelled")
        order = _order_for_invoice(session, invoice)

    if scope.po_number:
        named = _order_by_number(session, supplier.id, scope.po_number)
        if named is None:
            raise ReconciliationError(
                f"unknown purchase order {scope.po_number!r} for supplier {scope.supplier_code!r}"
            )
        if named.status == PurchaseOrderStatus.cancelled.value:
            raise ReconciliationError(f"purchase order {scope.po_number!r} is cancelled")
        if order is not None and named.id != order.id:
            raise ReconciliationError(
                "invoice and purchase order arguments resolve to different orders"
            )
        order = named

    orders = (order,) if order is not None else ()
    invoices = _invoices_for(session, supplier.id, order, invoice)
    receipts = _receipts_for(session, supplier.id, order)
    return SelectedRecords(
        supplier_code=scope.supplier_code,
        supplier_id=supplier.id,
        purchase_orders=tuple(_order_view(item) for item in orders),
        receipts=tuple(_receipt_view(item) for item in receipts),
        invoices=tuple(_invoice_view(item) for item in invoices),
    )


def load_identity_index(session: Session, *, supplier_id: int) -> IdentityIndex:
    by_ean = {
        row.ean: row.id
        for row in session.scalars(select(Product).where(Product.active.is_(True))).all()
        if row.ean
    }
    grouped: dict[str, list[int]] = defaultdict(list)
    terms = session.scalars(
        select(SupplierProduct).where(
            SupplierProduct.active.is_(True),
            SupplierProduct.supplier_id == supplier_id,
        )
    ).all()
    for term in terms:
        if term.supplier_sku:
            grouped[term.supplier_sku].append(term.product_id)
    return IdentityIndex(
        product_ids_by_ean=by_ean,
        product_ids_by_supplier_sku={key: tuple(ids) for key, ids in grouped.items()},
    )


def scope_key_for(records: SelectedRecords, scope: ReconciliationScope) -> str:
    if records.purchase_orders:
        return f"po:{records.supplier_code}:{records.purchase_orders[0].number}"
    if scope.invoice_number:
        return f"invoice:{records.supplier_code}:{scope.invoice_number}"
    return f"po:{scope.supplier_code}:{scope.po_number}"


def _invoice_by_number(
    session: Session, supplier_id: int, invoice_number: str
) -> SupplierInvoice | None:
    return session.scalar(
        select(SupplierInvoice)
        .options(selectinload(SupplierInvoice.lines))
        .where(
            SupplierInvoice.supplier_id == supplier_id,
            SupplierInvoice.invoice_number == invoice_number,
        )
    )


def _order_by_number(session: Session, supplier_id: int, po_number: str) -> PurchaseOrder | None:
    return session.scalar(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.lines))
        .where(PurchaseOrder.supplier_id == supplier_id, PurchaseOrder.po_number == po_number)
    )


def _order_for_invoice(session: Session, invoice: SupplierInvoice) -> PurchaseOrder | None:
    if invoice.purchase_order_id is not None:
        order = session.scalar(
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.lines))
            .where(PurchaseOrder.id == invoice.purchase_order_id)
        )
        if order is None or order.status == PurchaseOrderStatus.cancelled.value:
            return None
        return order
    if invoice.po_number:
        order = _order_by_number(session, invoice.supplier_id, invoice.po_number)
        if order is None or order.status == PurchaseOrderStatus.cancelled.value:
            return None
        return order
    return None


def _invoices_for(
    session: Session,
    supplier_id: int,
    order: PurchaseOrder | None,
    seed: SupplierInvoice | None,
) -> list[SupplierInvoice]:
    if order is None:
        return [seed] if seed is not None else []
    rows = session.scalars(
        select(SupplierInvoice)
        .options(selectinload(SupplierInvoice.lines))
        .where(
            SupplierInvoice.supplier_id == supplier_id,
            SupplierInvoice.status != SupplierInvoiceStatus.cancelled.value,
            or_(
                SupplierInvoice.purchase_order_id == order.id,
                SupplierInvoice.po_number == order.po_number,
            ),
        )
        .order_by(SupplierInvoice.id)
    ).all()
    return list(rows)


def _receipts_for(
    session: Session, supplier_id: int, order: PurchaseOrder | None
) -> list[GoodsReceipt]:
    if order is None:
        return []
    return list(
        session.scalars(
            select(GoodsReceipt)
            .options(selectinload(GoodsReceipt.lines))
            .where(
                GoodsReceipt.supplier_id == supplier_id,
                GoodsReceipt.status != GoodsReceiptStatus.cancelled.value,
                or_(
                    GoodsReceipt.purchase_order_id == order.id,
                    GoodsReceipt.po_number == order.po_number,
                ),
            )
            .order_by(GoodsReceipt.id)
        ).all()
    )


def _order_view(order: PurchaseOrder) -> PurchaseOrderView:
    return PurchaseOrderView(
        id=order.id,
        number=order.po_number,
        supplier_id=order.supplier_id,
        store_id=order.store_id,
        currency=order.currency,
        status=order.status,
        lines=tuple(
            PurchaseOrderLineView(
                id=line.id,
                line_number=line.line_number,
                product_id=line.product_id,
                ordered_quantity=line.ordered_quantity,
                unit_cost=line.unit_cost,
                tax_rate=line.tax_rate,
                tax_amount=line.tax_amount,
                line_total=line.line_total,
            )
            for line in order.lines
        ),
    )


def _receipt_view(receipt: GoodsReceipt) -> GoodsReceiptView:
    return GoodsReceiptView(
        id=receipt.id,
        number=receipt.receipt_number,
        supplier_id=receipt.supplier_id,
        purchase_order_id=receipt.purchase_order_id,
        po_number=receipt.po_number,
        status=receipt.status,
        lines=tuple(
            GoodsReceiptLineView(
                id=line.id,
                goods_receipt_id=receipt.id,
                line_number=line.line_number,
                product_id=line.product_id,
                purchase_order_line_id=line.purchase_order_line_id,
                received_quantity=line.received_quantity,
            )
            for line in receipt.lines
        ),
    )


def _invoice_view(invoice: SupplierInvoice) -> SupplierInvoiceView:
    return SupplierInvoiceView(
        id=invoice.id,
        number=invoice.invoice_number,
        supplier_id=invoice.supplier_id,
        purchase_order_id=invoice.purchase_order_id,
        po_number=invoice.po_number,
        currency=invoice.currency,
        status=invoice.status,
        lines=tuple(
            SupplierInvoiceLineView(
                id=line.id,
                supplier_invoice_id=invoice.id,
                line_number=line.line_number,
                product_id=line.product_id,
                supplier_sku=line.supplier_sku,
                ean=line.ean,
                invoiced_quantity=line.invoiced_quantity,
                unit_cost=line.unit_cost,
                tax_rate=line.tax_rate,
                tax_amount=line.tax_amount,
                line_total=line.line_total,
            )
            for line in invoice.lines
        ),
    )
