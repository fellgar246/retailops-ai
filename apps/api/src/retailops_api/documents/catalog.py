"""Catalog snapshot used by cross-reference rules.

Rules themselves stay free of SQL: this module loads a read-only index from
a session, and ``catalog_rules`` compares a sheet against that index.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from retailops_api.domain.models import Category, Product, Supplier, SupplierProduct


@dataclass(frozen=True)
class ProductRef:
    id: int
    sku: str
    ean: str | None
    name: str
    category_code: str
    category_name: str


@dataclass(frozen=True)
class TermRef:
    supplier_id: int
    supplier_code: str
    supplier_sku: str | None
    cost: Decimal
    product: ProductRef


@dataclass(frozen=True)
class CatalogIndex:
    """In-memory view of live catalog rows a sheet can be compared against."""

    products_by_ean: dict[str, ProductRef]
    terms_by_supplier_sku: dict[str, tuple[TermRef, ...]]
    terms_by_supplier_ean: dict[tuple[int, str], TermRef]
    terms_by_supplier_and_sku: dict[tuple[int, str], TermRef]

    def product_for_ean(self, ean: str) -> ProductRef | None:
        return self.products_by_ean.get(ean)

    def terms_for_supplier_sku(self, supplier_sku: str) -> tuple[TermRef, ...]:
        return self.terms_by_supplier_sku.get(supplier_sku, ())

    def term_for_row(
        self,
        *,
        supplier_id: int,
        ean: str | None,
        supplier_sku: str | None,
    ) -> TermRef | None:
        if ean:
            by_ean = self.terms_by_supplier_ean.get((supplier_id, ean))
            if by_ean is not None:
                return by_ean
        if supplier_sku:
            return self.terms_by_supplier_and_sku.get((supplier_id, supplier_sku))
        return None


def load_catalog_index(session: Session) -> CatalogIndex:
    """Load active catalog rows. Inactive records are ignored."""
    categories = {
        row.id: row
        for row in session.scalars(select(Category).where(Category.active.is_(True))).all()
    }
    products_by_id: dict[int, ProductRef] = {}
    products_by_ean: dict[str, ProductRef] = {}
    for product_row in session.scalars(select(Product).where(Product.active.is_(True))).all():
        category = categories.get(product_row.category_id)
        if category is None:
            continue
        product_ref = ProductRef(
            id=product_row.id,
            sku=product_row.sku,
            ean=product_row.ean,
            name=product_row.name,
            category_code=category.code,
            category_name=category.name,
        )
        products_by_id[product_row.id] = product_ref
        if product_row.ean:
            products_by_ean[product_row.ean] = product_ref

    suppliers = {
        row.id: row
        for row in session.scalars(select(Supplier).where(Supplier.active.is_(True))).all()
    }
    by_sku: dict[str, list[TermRef]] = defaultdict(list)
    by_supplier_ean: dict[tuple[int, str], TermRef] = {}
    by_supplier_sku: dict[tuple[int, str], TermRef] = {}
    terms = session.scalars(select(SupplierProduct).where(SupplierProduct.active.is_(True))).all()
    for term in terms:
        supplier = suppliers.get(term.supplier_id)
        linked = products_by_id.get(term.product_id)
        if supplier is None or linked is None:
            continue
        term_ref = TermRef(
            supplier_id=supplier.id,
            supplier_code=supplier.code,
            supplier_sku=term.supplier_sku,
            cost=term.cost,
            product=linked,
        )
        if term.supplier_sku:
            by_sku[term.supplier_sku].append(term_ref)
            by_supplier_sku[(supplier.id, term.supplier_sku)] = term_ref
        if linked.ean:
            by_supplier_ean[(supplier.id, linked.ean)] = term_ref

    return CatalogIndex(
        products_by_ean=products_by_ean,
        terms_by_supplier_sku={key: tuple(value) for key, value in by_sku.items()},
        terms_by_supplier_ean=by_supplier_ean,
        terms_by_supplier_and_sku=by_supplier_sku,
    )
