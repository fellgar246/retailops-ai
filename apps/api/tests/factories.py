"""Minimal builders so each test states only the fields it cares about."""

from decimal import Decimal

from sqlalchemy.orm import Session

from retailops_api.domain.models import (
    Category,
    DocumentFinding,
    Product,
    Store,
    Supplier,
    SupplierDocument,
    SupplierProduct,
)
from retailops_api.domain.models.document import DocumentStatus, DocumentType, FindingSeverity


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
