"""Purchase orders, receipts and invoices used by the local demo."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from retailops_api.domain.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    Store,
    Supplier,
    SupplierInvoice,
    SupplierInvoiceLine,
)
from retailops_api.domain.models.goods_receipt import GoodsReceiptStatus
from retailops_api.domain.models.purchase_order import PurchaseOrderStatus
from retailops_api.domain.models.supplier_invoice import SupplierInvoiceStatus
from retailops_api.domain.repositories import (
    get_product_by_sku,
    get_store_by_code,
    get_supplier_by_code,
)
from retailops_api.procurement.money import line_amounts
from retailops_api.procurement.orchestrate import reconcile
from retailops_api.procurement.types import ReconciliationResult, ReconciliationScope

DEMO_SUPPLIER = "SUP-BEVCO"
DEMO_STORE = "ST-001"
DEMO_SKU = "SKU-1001"
DEMO_SUPPLIER_SKU = "BC-COLA-355"
DEMO_EAN = "7501000110018"
PO_COST = Decimal("7.4500")
TAX = Decimal("16.0000")


@dataclass(frozen=True)
class DemoScenario:
    po_number: str
    receipt_number: str
    invoice_number: str
    ordered: int
    received: int
    invoiced: int
    invoice_cost: Decimal


SCENARIOS: tuple[DemoScenario, ...] = (
    DemoScenario(
        po_number="PO-DEMO-OVER",
        receipt_number="GR-DEMO-OVER",
        invoice_number="INV-DEMO-OVER",
        ordered=10,
        received=10,
        invoiced=12,
        invoice_cost=PO_COST,
    ),
    DemoScenario(
        po_number="PO-DEMO-COST",
        receipt_number="GR-DEMO-COST",
        invoice_number="INV-DEMO-COST",
        ordered=10,
        received=10,
        invoiced=10,
        invoice_cost=Decimal("8.0000"),
    ),
)


def create_demo_procurement(session: Session) -> list[ReconciliationResult]:
    """Create the demo three-way matches and persist reconciliation runs."""

    supplier = _require(get_supplier_by_code(session, DEMO_SUPPLIER), DEMO_SUPPLIER)
    store = _require(get_store_by_code(session, DEMO_STORE), DEMO_STORE)
    product = _require(get_product_by_sku(session, DEMO_SKU), DEMO_SKU)
    results: list[ReconciliationResult] = []
    for scenario in SCENARIOS:
        _ensure_documents(session, supplier, store, product, scenario)
        results.append(
            reconcile(
                session,
                ReconciliationScope(
                    supplier_code=DEMO_SUPPLIER, invoice_number=scenario.invoice_number
                ),
            )
        )
    session.flush()
    return results


def _ensure_documents(
    session: Session,
    supplier: Supplier,
    store: Store,
    product: Product,
    scenario: DemoScenario,
) -> None:
    order = session.scalar(
        select(PurchaseOrder).where(
            PurchaseOrder.supplier_id == supplier.id,
            PurchaseOrder.po_number == scenario.po_number,
        )
    )
    if order is not None:
        return
    order = PurchaseOrder(
        supplier_id=supplier.id,
        store_id=store.id,
        po_number=scenario.po_number,
        order_date=date(2026, 3, 1),
        expected_date=date(2026, 3, 8),
        currency="MXN",
        status=PurchaseOrderStatus.open.value,
    )
    session.add(order)
    session.flush()
    tax, total = line_amounts(scenario.ordered, PO_COST, TAX)[1:]
    line = PurchaseOrderLine(
        product_id=product.id,
        line_number=1,
        ordered_quantity=scenario.ordered,
        unit_cost=PO_COST,
        tax_rate=TAX,
        tax_amount=tax,
        line_total=total,
    )
    order.lines.append(line)
    session.flush()

    receipt = GoodsReceipt(
        supplier_id=supplier.id,
        purchase_order_id=order.id,
        receipt_number=scenario.receipt_number,
        po_number=scenario.po_number,
        received_date=date(2026, 3, 5),
        status=GoodsReceiptStatus.posted.value,
    )
    session.add(receipt)
    session.flush()
    receipt.lines.append(
        GoodsReceiptLine(
            product_id=product.id,
            purchase_order_line_id=line.id,
            line_number=1,
            received_quantity=scenario.received,
        )
    )

    invoice_tax, invoice_total = line_amounts(scenario.invoiced, scenario.invoice_cost, TAX)[1:]
    invoice = SupplierInvoice(
        supplier_id=supplier.id,
        purchase_order_id=order.id,
        invoice_number=scenario.invoice_number,
        po_number=scenario.po_number,
        invoice_date=date(2026, 3, 6),
        currency="MXN",
        status=SupplierInvoiceStatus.received.value,
    )
    session.add(invoice)
    session.flush()
    invoice.lines.append(
        SupplierInvoiceLine(
            product_id=product.id,
            line_number=1,
            supplier_sku=DEMO_SUPPLIER_SKU,
            ean=DEMO_EAN,
            invoiced_quantity=scenario.invoiced,
            unit_cost=scenario.invoice_cost,
            tax_rate=TAX,
            tax_amount=invoice_tax,
            line_total=invoice_total,
        )
    )
    session.flush()


def _require[T](value: T | None, code: str) -> T:
    if value is None:
        raise ValueError(f"demo catalog is missing {code}")
    return value
