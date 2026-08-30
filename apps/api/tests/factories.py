"""Minimal builders so each test states only the fields it cares about."""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from retailops_api.domain.models import (
    Category,
    DocumentFinding,
    GoodsReceipt,
    GoodsReceiptLine,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    Store,
    Supplier,
    SupplierDocument,
    SupplierInvoice,
    SupplierInvoiceLine,
    SupplierProduct,
)
from retailops_api.domain.models.document import DocumentStatus, DocumentType, FindingSeverity
from retailops_api.domain.models.goods_receipt import GoodsReceiptStatus
from retailops_api.domain.models.purchase_order import PurchaseOrderStatus
from retailops_api.domain.models.supplier_invoice import SupplierInvoiceStatus
from retailops_api.procurement.money import line_amounts


def make_category(
    session: Session,
    code: str = "CAT",
    name: str = "Category",
    parent: Category | None = None,
    active: bool = True,
) -> Category:
    category = Category(code=code, name=name, parent=parent, active=active)
    session.add(category)
    session.flush()
    return category


def make_product(
    session: Session,
    sku: str = "SKU-1",
    name: str = "Product",
    category: Category | None = None,
    ean: str | None = None,
    description: str | None = None,
    active: bool = True,
) -> Product:
    if category is None:
        category = make_category(session, code=f"CAT-FOR-{sku}")
    product = Product(
        sku=sku,
        name=name,
        category=category,
        ean=ean,
        description=description,
        active=active,
    )
    session.add(product)
    session.flush()
    return product


def make_supplier(
    session: Session,
    code: str = "SUP-1",
    name: str = "Supplier",
    tax_id: str | None = None,
    active: bool = True,
) -> Supplier:
    supplier = Supplier(code=code, name=name, tax_id=tax_id, active=active)
    session.add(supplier)
    session.flush()
    return supplier


def make_store(
    session: Session,
    code: str = "ST-1",
    name: str = "Store",
    region: str = "Central",
    store_type: str = "supermarket",
    active: bool = True,
) -> Store:
    store = Store(code=code, name=name, region=region, store_type=store_type, active=active)
    session.add(store)
    session.flush()
    return store


def make_supplier_product(
    session: Session,
    supplier: Supplier,
    product: Product,
    cost: Decimal = Decimal("10.0000"),
    case_pack: int = 12,
    minimum_order_quantity: int = 1,
    lead_time_days: int = 3,
    supplier_sku: str | None = None,
) -> SupplierProduct:
    link = SupplierProduct(
        supplier_id=supplier.id,
        product_id=product.id,
        cost=cost,
        case_pack=case_pack,
        minimum_order_quantity=minimum_order_quantity,
        lead_time_days=lead_time_days,
        supplier_sku=supplier_sku,
    )
    session.add(link)
    session.flush()
    return link


def make_supplier_document(
    session: Session,
    supplier: Supplier,
    *,
    filename: str = "offer.csv",
    media_type: str = "text/csv",
    storage_key: str = "a" * 32,
    checksum: str = "b" * 64,
    document_type: str = DocumentType.supplier_sheet.value,
    status: str = DocumentStatus.received.value,
) -> SupplierDocument:
    document = SupplierDocument(
        supplier_id=supplier.id,
        filename=filename,
        media_type=media_type,
        storage_key=storage_key,
        checksum=checksum,
        document_type=document_type,
        status=status,
    )
    session.add(document)
    session.flush()
    return document


def make_document_finding(
    session: Session,
    document: SupplierDocument,
    *,
    code: str = "required_field",
    field: str | None = "description",
    row_reference: int | None = 2,
    severity: str = FindingSeverity.error.value,
    message: str = "description is required",
    proposed_value: str | None = None,
) -> DocumentFinding:
    finding = DocumentFinding(
        document_id=document.id,
        code=code,
        field=field,
        row_reference=row_reference,
        severity=severity,
        message=message,
        proposed_value=proposed_value,
    )
    session.add(finding)
    session.flush()
    return finding


def _referenced_po_number(
    purchase_order: PurchaseOrder | None, po_number: str | None
) -> str | None:
    if po_number is not None:
        return po_number
    if purchase_order is not None:
        return purchase_order.po_number
    return None


def make_purchase_order(
    session: Session,
    supplier: Supplier,
    store: Store,
    *,
    po_number: str = "PO-1001",
    order_date: date = date(2026, 3, 1),
    expected_date: date | None = date(2026, 3, 8),
    currency: str = "MXN",
    status: str = PurchaseOrderStatus.open.value,
) -> PurchaseOrder:
    order = PurchaseOrder(
        supplier_id=supplier.id,
        store_id=store.id,
        po_number=po_number,
        order_date=order_date,
        expected_date=expected_date,
        currency=currency,
        status=status,
    )
    session.add(order)
    session.flush()
    return order


def make_purchase_order_line(
    session: Session,
    order: PurchaseOrder,
    product: Product,
    *,
    line_number: int | None = None,
    ordered_quantity: int = 10,
    unit_cost: Decimal = Decimal("7.4500"),
    tax_rate: Decimal = Decimal("16.0000"),
    tax_amount: Decimal | None = None,
    line_total: Decimal | None = None,
) -> PurchaseOrderLine:
    computed_tax, computed_total = line_amounts(ordered_quantity, unit_cost, tax_rate)[1:]
    if line_number is None:
        session.refresh(order, attribute_names=["lines"])
        line_number = len(order.lines) + 1
    line = PurchaseOrderLine(
        product_id=product.id,
        line_number=line_number,
        ordered_quantity=ordered_quantity,
        unit_cost=unit_cost,
        tax_rate=tax_rate,
        tax_amount=computed_tax if tax_amount is None else tax_amount,
        line_total=computed_total if line_total is None else line_total,
    )
    order.lines.append(line)
    session.flush()
    return line


def make_goods_receipt(
    session: Session,
    supplier: Supplier,
    *,
    receipt_number: str = "GR-1001",
    received_date: date = date(2026, 3, 5),
    purchase_order: PurchaseOrder | None = None,
    po_number: str | None = None,
    status: str = GoodsReceiptStatus.posted.value,
) -> GoodsReceipt:
    receipt = GoodsReceipt(
        supplier_id=supplier.id,
        purchase_order_id=purchase_order.id if purchase_order is not None else None,
        receipt_number=receipt_number,
        po_number=_referenced_po_number(purchase_order, po_number),
        received_date=received_date,
        status=status,
    )
    session.add(receipt)
    session.flush()
    return receipt


def make_goods_receipt_line(
    session: Session,
    receipt: GoodsReceipt,
    product: Product,
    *,
    line_number: int | None = None,
    received_quantity: int = 10,
    purchase_order_line: PurchaseOrderLine | None = None,
) -> GoodsReceiptLine:
    if line_number is None:
        session.refresh(receipt, attribute_names=["lines"])
        line_number = len(receipt.lines) + 1
    line = GoodsReceiptLine(
        product_id=product.id,
        purchase_order_line_id=purchase_order_line.id if purchase_order_line is not None else None,
        line_number=line_number,
        received_quantity=received_quantity,
    )
    receipt.lines.append(line)
    session.flush()
    return line


def make_supplier_invoice(
    session: Session,
    supplier: Supplier,
    *,
    invoice_number: str = "INV-1001",
    invoice_date: date = date(2026, 3, 6),
    purchase_order: PurchaseOrder | None = None,
    po_number: str | None = None,
    currency: str = "MXN",
    status: str = SupplierInvoiceStatus.received.value,
) -> SupplierInvoice:
    invoice = SupplierInvoice(
        supplier_id=supplier.id,
        purchase_order_id=purchase_order.id if purchase_order is not None else None,
        invoice_number=invoice_number,
        po_number=_referenced_po_number(purchase_order, po_number),
        invoice_date=invoice_date,
        currency=currency,
        status=status,
    )
    session.add(invoice)
    session.flush()
    return invoice


def make_supplier_invoice_line(
    session: Session,
    invoice: SupplierInvoice,
    *,
    line_number: int | None = None,
    product: Product | None = None,
    supplier_sku: str | None = None,
    ean: str | None = None,
    invoiced_quantity: int = 10,
    unit_cost: Decimal = Decimal("7.4500"),
    tax_rate: Decimal = Decimal("16.0000"),
    tax_amount: Decimal | None = None,
    line_total: Decimal | None = None,
) -> SupplierInvoiceLine:
    computed_tax, computed_total = line_amounts(invoiced_quantity, unit_cost, tax_rate)[1:]
    if line_number is None:
        session.refresh(invoice, attribute_names=["lines"])
        line_number = len(invoice.lines) + 1
    line = SupplierInvoiceLine(
        product_id=product.id if product is not None else None,
        line_number=line_number,
        supplier_sku=supplier_sku,
        ean=ean,
        invoiced_quantity=invoiced_quantity,
        unit_cost=unit_cost,
        tax_rate=tax_rate,
        tax_amount=computed_tax if tax_amount is None else tax_amount,
        line_total=computed_total if line_total is None else line_total,
    )
    invoice.lines.append(line)
    session.flush()
    return line
