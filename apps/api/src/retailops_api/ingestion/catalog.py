"""Idempotent catalog ingestion.

Rows are identified by business code. A second run with the same payload
creates nothing new; a second run with an edited name updates the existing
row in place. The caller owns the transaction: this module never commits, so
a failure leaves the session uncommitted and the caller can roll back.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from retailops_api.dataset.contract import Catalog
from retailops_api.domain.models import Category, Product, Store, Supplier, SupplierProduct


class CatalogIngestionError(RuntimeError):
    """Raised when the catalog payload is internally inconsistent."""


@dataclass
class EntityResult:
    """How many rows a single entity's sync created or changed."""

    created: int = 0
    updated: int = 0
    unchanged: int = 0

    def record(self, *, created: bool, changed: bool) -> None:
        if created:
            self.created += 1
        elif changed:
            self.updated += 1
        else:
            self.unchanged += 1


@dataclass
class CatalogIngestionResult:
    categories: EntityResult = field(default_factory=EntityResult)
    products: EntityResult = field(default_factory=EntityResult)
    suppliers: EntityResult = field(default_factory=EntityResult)
    supplier_products: EntityResult = field(default_factory=EntityResult)
    stores: EntityResult = field(default_factory=EntityResult)

    @property
    def created(self) -> int:
        return sum(result.created for result in self._results)

    @property
    def updated(self) -> int:
        return sum(result.updated for result in self._results)

    @property
    def _results(self) -> tuple[EntityResult, ...]:
        return (
            self.categories,
            self.products,
            self.suppliers,
            self.supplier_products,
            self.stores,
        )

    def format_report(self) -> str:
        lines = [
            f"{label:<18} created={result.created:<4} "
            f"updated={result.updated:<4} unchanged={result.unchanged}"
            for label, result in (
                ("categories", self.categories),
                ("products", self.products),
                ("suppliers", self.suppliers),
                ("supplier_products", self.supplier_products),
                ("stores", self.stores),
            )
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict[str, dict[str, int]]:
        return {
            label: {
                "created": result.created,
                "updated": result.updated,
                "unchanged": result.unchanged,
            }
            for label, result in (
                ("categories", self.categories),
                ("products", self.products),
                ("suppliers", self.suppliers),
                ("supplier_products", self.supplier_products),
                ("stores", self.stores),
            )
        }


def ingest_catalog(session: Session, catalog: Catalog) -> CatalogIngestionResult:
    """Bring the database in line with ``catalog``.

    Does not commit; the caller owns the transaction. Any
    :class:`CatalogIngestionError` is raised before the function returns, so
    the caller can roll the whole catalog write back.
    """
    result = CatalogIngestionResult()
    result.categories = _sync_categories(session, catalog)
    result.stores = _sync_stores(session, catalog)
    result.suppliers = _sync_suppliers(session, catalog)
    result.products = _sync_products(session, catalog)
    result.supplier_products = _sync_supplier_products(session, catalog)
    return result


def _apply(instance: object, values: dict[str, object]) -> bool:
    """Assign only the attributes that differ, and report whether any did.

    Assigning an identical value would still mark the row dirty and bump
    ``updated_at``, which would make a no-op re-ingest look like a change.
    """
    changed = False
    for attribute, value in values.items():
        if getattr(instance, attribute) != value:
            setattr(instance, attribute, value)
            changed = True
    return changed


def _sync_categories(session: Session, catalog: Catalog) -> EntityResult:
    result = EntityResult()
    existing = {category.code: category for category in session.scalars(select(Category))}

    # Every node has to exist as an object before parents can be wired, so the
    # payload does not need to be in topological order.
    new_codes = set()
    for row in catalog.categories:
        if row.code not in existing:
            category = Category(code=row.code)
            session.add(category)
            existing[row.code] = category
            new_codes.add(row.code)

    for row in catalog.categories:
        if row.parent_code:
            parent = existing.get(row.parent_code)
            if parent is None:
                raise CatalogIngestionError(
                    f"Category {row.code!r} references unknown parent {row.parent_code!r}."
                )
        else:
            parent = None
        changed = _apply(
            existing[row.code],
            {"name": row.name, "parent": parent, "active": row.active},
        )
        result.record(created=row.code in new_codes, changed=changed)

    session.flush()
    return result


def _sync_stores(session: Session, catalog: Catalog) -> EntityResult:
    result = EntityResult()
    existing = {store.code: store for store in session.scalars(select(Store))}

    for row in catalog.stores:
        store = existing.get(row.code)
        is_new = store is None
        if store is None:
            store = Store(code=row.code)
            session.add(store)
        changed = _apply(
            store,
            {
                "name": row.name,
                "region": row.region,
                "store_type": row.store_type,
                "active": row.active,
            },
        )
        result.record(created=is_new, changed=changed)

    session.flush()
    return result


def _sync_suppliers(session: Session, catalog: Catalog) -> EntityResult:
    result = EntityResult()
    existing = {supplier.code: supplier for supplier in session.scalars(select(Supplier))}

    for row in catalog.suppliers:
        supplier = existing.get(row.code)
        is_new = supplier is None
        if supplier is None:
            supplier = Supplier(code=row.code)
            session.add(supplier)
        changed = _apply(supplier, {"name": row.name, "tax_id": row.tax_id, "active": row.active})
        result.record(created=is_new, changed=changed)

    session.flush()
    return result


def _sync_products(session: Session, catalog: Catalog) -> EntityResult:
    result = EntityResult()
    categories = {category.code: category for category in session.scalars(select(Category))}
    existing = {product.sku: product for product in session.scalars(select(Product))}

    for row in catalog.products:
        category = categories.get(row.category_code)
        if category is None:
            raise CatalogIngestionError(
                f"Product {row.sku!r} references unknown category {row.category_code!r}."
            )

        product = existing.get(row.sku)
        is_new = product is None
        if product is None:
            product = Product(sku=row.sku)
            session.add(product)
        changed = _apply(
            product,
            {
                "name": row.name,
                "description": row.description,
                "ean": row.ean,
                "category": category,
                "active": row.active,
            },
        )
        result.record(created=is_new, changed=changed)

    session.flush()
    return result


def _sync_supplier_products(session: Session, catalog: Catalog) -> EntityResult:
    result = EntityResult()
    suppliers = {supplier.code: supplier for supplier in session.scalars(select(Supplier))}
    products = {product.sku: product for product in session.scalars(select(Product))}
    existing = {
        (link.supplier_id, link.product_id): link
        for link in session.scalars(select(SupplierProduct))
    }

    for row in catalog.supplier_products:
        supplier = suppliers.get(row.supplier_code)
        product = products.get(row.product_sku)
        if supplier is None:
            raise CatalogIngestionError(
                f"Unknown supplier code {row.supplier_code!r} in supplier terms."
            )
        if product is None:
            raise CatalogIngestionError(
                f"Unknown product SKU {row.product_sku!r} in supplier terms."
            )

        link = existing.get((supplier.id, product.id))
        is_new = link is None
        if link is None:
            link = SupplierProduct(supplier_id=supplier.id, product_id=product.id)
            session.add(link)
        changed = _apply(
            link,
            {
                "supplier_sku": row.supplier_sku,
                "cost": row.cost,
                "case_pack": row.case_pack,
                "minimum_order_quantity": row.minimum_order_quantity,
                "lead_time_days": row.lead_time_days,
                "active": row.active,
            },
        )
        result.record(created=is_new, changed=changed)

    session.flush()
    return result
