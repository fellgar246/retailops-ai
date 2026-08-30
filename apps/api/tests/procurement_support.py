"""Builders for three-way match tests."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from retailops_api.domain.models import (
    GoodsReceipt,
    Product,
    PurchaseOrder,
    Store,
    Supplier,
    SupplierInvoice,
)
from tests.factories import (
    make_goods_receipt,
    make_goods_receipt_line,
    make_product,
    make_purchase_order,
    make_purchase_order_line,
    make_store,
    make_supplier,
    make_supplier_invoice,
    make_supplier_invoice_line,
    make_supplier_product,
)


@dataclass
class ThreeWay:
    supplier: Supplier
    store: Store
    product: Product
    order: PurchaseOrder
    receipt: GoodsReceipt | None
    invoice: SupplierInvoice | None


def build_three_way(
    session: Session,
    *,
    ordered: int = 10,
    received: int | None = 10,
    invoiced: int | None = 10,
    po_cost: Decimal = Decimal("7.4500"),
    invoice_cost: Decimal | None = None,
    tax_rate: Decimal = Decimal("16.0000"),
    invoice_tax_rate: Decimal | None = None,
    currency: str = "MXN",
    invoice_currency: str | None = None,
    po_number: str = "PO-1001",
    receipt_number: str = "GR-1001",
    invoice_number: str = "INV-1001",
    supplier_sku: str | None = "BC-COLA-355",
    ean: str | None = "7501000110018",
    product_sku: str = "SKU-1001",
) -> ThreeWay:
    supplier = make_supplier(session, code="SUP-BEVCO")
    store = make_store(session, code="ST-001")
    product = make_product(session, sku=product_sku, ean=ean)
    if supplier_sku is not None:
        make_supplier_product(session, supplier, product, cost=po_cost, supplier_sku=supplier_sku)
    order = make_purchase_order(session, supplier, store, po_number=po_number, currency=currency)
    po_line = make_purchase_order_line(
        session, order, product, ordered_quantity=ordered, unit_cost=po_cost, tax_rate=tax_rate
    )
    receipt: GoodsReceipt | None = None
    if received is not None:
        receipt = make_goods_receipt(
            session, supplier, receipt_number=receipt_number, purchase_order=order
        )
        make_goods_receipt_line(
            session,
            receipt,
            product,
            received_quantity=received,
            purchase_order_line=po_line,
        )
    invoice: SupplierInvoice | None = None
    if invoiced is not None:
        invoice = make_supplier_invoice(
            session,
            supplier,
            invoice_number=invoice_number,
            purchase_order=order,
            currency=invoice_currency or currency,
        )
        make_supplier_invoice_line(
            session,
            invoice,
            product=product,
            supplier_sku=supplier_sku,
            ean=ean,
            invoiced_quantity=invoiced,
            unit_cost=invoice_cost if invoice_cost is not None else po_cost,
            tax_rate=invoice_tax_rate if invoice_tax_rate is not None else tax_rate,
        )
    return ThreeWay(
        supplier=supplier,
        store=store,
        product=product,
        order=order,
        receipt=receipt,
        invoice=invoice,
    )
