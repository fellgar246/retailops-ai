"""Deterministic reference data for local development.

Every record is identified by its business code, so seeding is idempotent:
running it twice creates nothing the second time, and editing a name below and
re-running updates the existing row in place rather than inserting a duplicate.

No sales history is seeded here; that is generated synthetically elsewhere.

Run with ``make seed`` or ``uv run retailops-seed``.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from retailops_api.db.session import get_session_factory
from retailops_api.domain.models import Category, Product, Store, Supplier, SupplierProduct


@dataclass(frozen=True)
class CategorySeed:
    code: str
    name: str
    parent_code: str | None = None


@dataclass(frozen=True)
class ProductSeed:
    sku: str
    name: str
    category_code: str
    ean: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class SupplierSeed:
    code: str
    name: str
    tax_id: str | None = None


@dataclass(frozen=True)
class SupplierProductSeed:
    supplier_code: str
    product_sku: str
    cost: Decimal
    case_pack: int
    minimum_order_quantity: int
    lead_time_days: int
    supplier_sku: str | None = None


@dataclass(frozen=True)
class StoreSeed:
    code: str
    name: str
    region: str
    store_type: str


CATEGORIES: tuple[CategorySeed, ...] = (
    CategorySeed("BEV", "Beverages"),
    CategorySeed("SNACK", "Snacks"),
    CategorySeed("HOME", "Household"),
    CategorySeed("BEV-SOFT", "Soft Drinks", "BEV"),
    CategorySeed("BEV-WATER", "Water", "BEV"),
    CategorySeed("BEV-COFFEE", "Coffee & Tea", "BEV"),
    CategorySeed("SNACK-CHIPS", "Chips & Crisps", "SNACK"),
    CategorySeed("SNACK-CANDY", "Candy & Chocolate", "SNACK"),
    CategorySeed("HOME-CLEAN", "Cleaning Supplies", "HOME"),
    CategorySeed("HOME-PAPER", "Paper Goods", "HOME"),
)

PRODUCTS: tuple[ProductSeed, ...] = (
    ProductSeed("SKU-1001", "Cola Classic 355ml Can", "BEV-SOFT", "7501000110018"),
    ProductSeed("SKU-1002", "Cola Zero 355ml Can", "BEV-SOFT", "7501000110025"),
    ProductSeed("SKU-1003", "Orange Soda 600ml Bottle", "BEV-SOFT", "7501000110032"),
    ProductSeed("SKU-1004", "Still Water 1L Bottle", "BEV-WATER", "7501000110049"),
    ProductSeed("SKU-1005", "Sparkling Water 500ml Bottle", "BEV-WATER", "7501000110056"),
    ProductSeed("SKU-1006", "Ground Coffee 500g", "BEV-COFFEE", "7501000110063"),
    # Deliberately without a barcode: exercises the nullable unique EAN column.
    ProductSeed("SKU-1007", "Loose Leaf Green Tea 100g", "BEV-COFFEE"),
    ProductSeed("SKU-2001", "Salted Potato Chips 150g", "SNACK-CHIPS", "7501000120017"),
    ProductSeed("SKU-2002", "Spicy Tortilla Chips 180g", "SNACK-CHIPS", "7501000120024"),
    ProductSeed("SKU-2003", "Milk Chocolate Bar 100g", "SNACK-CANDY", "7501000120031"),
    ProductSeed("SKU-2004", "Fruit Gummies 90g", "SNACK-CANDY", "7501000120048"),
    ProductSeed("SKU-3001", "Multi-Surface Cleaner 750ml", "HOME-CLEAN", "7501000130016"),
    ProductSeed("SKU-3002", "Dishwashing Liquid 500ml", "HOME-CLEAN", "7501000130023"),
    ProductSeed("SKU-3003", "Paper Towels 2-Pack", "HOME-PAPER", "7501000130030"),
    ProductSeed("SKU-3004", "Toilet Paper 4-Pack", "HOME-PAPER", "7501000130047"),
)

SUPPLIERS: tuple[SupplierSeed, ...] = (
    SupplierSeed("SUP-BEVCO", "BevCo Distribution", "BEV920304AB1"),
    SupplierSeed("SUP-SNACKW", "Snackworks Wholesale", "SNK850612CD2"),
    SupplierSeed("SUP-HOMESUP", "HomeSupply Partners", "HSP001122EF3"),
    SupplierSeed("SUP-NATGRO", "National Grocery Group", None),
)

SUPPLIER_PRODUCTS: tuple[SupplierProductSeed, ...] = (
    SupplierProductSeed("SUP-BEVCO", "SKU-1001", Decimal("7.4500"), 24, 2, 3, "BC-COLA-355"),
    SupplierProductSeed("SUP-BEVCO", "SKU-1002", Decimal("7.4500"), 24, 2, 3, "BC-COLAZ-355"),
    SupplierProductSeed("SUP-BEVCO", "SKU-1003", Decimal("9.8000"), 12, 1, 3, "BC-ORNG-600"),
    SupplierProductSeed("SUP-BEVCO", "SKU-1004", Decimal("5.2500"), 12, 1, 2, "BC-WATER-1L"),
    SupplierProductSeed("SUP-BEVCO", "SKU-1005", Decimal("6.1000"), 12, 1, 2, "BC-SPKL-500"),
    SupplierProductSeed("SUP-BEVCO", "SKU-1006", Decimal("48.9000"), 6, 1, 7, "BC-COFFEE-500"),
    SupplierProductSeed("SUP-SNACKW", "SKU-2001", Decimal("12.3000"), 20, 1, 4, "SW-CHIP-150"),
    SupplierProductSeed("SUP-SNACKW", "SKU-2002", Decimal("14.7500"), 20, 1, 4, "SW-TORT-180"),
    SupplierProductSeed("SUP-SNACKW", "SKU-2003", Decimal("16.4000"), 18, 2, 5, "SW-CHOC-100"),
    SupplierProductSeed("SUP-SNACKW", "SKU-2004", Decimal("8.9500"), 24, 1, 5, "SW-GUMM-90"),
    SupplierProductSeed("SUP-HOMESUP", "SKU-3001", Decimal("22.5000"), 12, 1, 6, "HS-CLEAN-750"),
    SupplierProductSeed("SUP-HOMESUP", "SKU-3002", Decimal("18.2500"), 12, 1, 6, "HS-DISH-500"),
    SupplierProductSeed("SUP-HOMESUP", "SKU-3003", Decimal("26.0000"), 8, 1, 6, "HS-TOWEL-2"),
    SupplierProductSeed("SUP-HOMESUP", "SKU-3004", Decimal("31.5000"), 8, 1, 6, "HS-TP-4"),
    # Second source for four products, so supplier comparison has something to
    # compare: slower and pricier, but a smaller minimum.
    SupplierProductSeed("SUP-NATGRO", "SKU-1001", Decimal("7.9900"), 12, 1, 10, "NG-1001"),
    SupplierProductSeed("SUP-NATGRO", "SKU-2001", Decimal("12.9900"), 10, 1, 9, "NG-2001"),
    SupplierProductSeed("SUP-NATGRO", "SKU-2003", Decimal("17.1000"), 12, 1, 9, "NG-2003"),
    SupplierProductSeed("SUP-NATGRO", "SKU-3003", Decimal("27.4000"), 6, 1, 8, "NG-3003"),
    SupplierProductSeed("SUP-NATGRO", "SKU-1007", Decimal("33.0000"), 10, 1, 12, "NG-1007"),
)

STORES: tuple[StoreSeed, ...] = (
    StoreSeed("ST-001", "Centro Flagship", "Central", "flagship"),
    StoreSeed("ST-002", "Norte Supermarket", "North", "supermarket"),
    StoreSeed("ST-003", "Sur Supermarket", "South", "supermarket"),
    StoreSeed("ST-004", "Poniente Express", "West", "express"),
    StoreSeed("ST-005", "Oriente Express", "East", "express"),
)


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
class SeedSummary:
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


class SeedDataError(RuntimeError):
    """Raised when the declared seed data is internally inconsistent."""


def seed_reference_data(session: Session) -> SeedSummary:
    """Bring the database in line with the reference data declared in this module.

    Does not commit; the caller owns the transaction.
    """
    summary = SeedSummary()
    summary.categories = _sync_categories(session)
    summary.stores = _sync_stores(session)
    summary.suppliers = _sync_suppliers(session)
    summary.products = _sync_products(session)
    summary.supplier_products = _sync_supplier_products(session)
    return summary


def _apply(instance: object, values: dict[str, object]) -> bool:
    """Assign only the attributes that differ, and report whether any did.

    Assigning an identical value would still mark the row dirty and bump
    ``updated_at``, which would make a no-op re-seed look like a change.
    """
    changed = False
    for attribute, value in values.items():
        if getattr(instance, attribute) != value:
            setattr(instance, attribute, value)
            changed = True
    return changed


def _sync_categories(session: Session) -> EntityResult:
    result = EntityResult()
    existing = {category.code: category for category in session.scalars(select(Category))}

    # Every node has to exist as an object before parents can be wired, so the
    # seed list above does not need to be in topological order.
    new_codes = set()
    for seed in CATEGORIES:
        if seed.code not in existing:
            category = Category(code=seed.code)
            session.add(category)
            existing[seed.code] = category
            new_codes.add(seed.code)

    for seed in CATEGORIES:
        parent = existing[seed.parent_code] if seed.parent_code else None
        # Assigning the related object rather than parent_id lets SQLAlchemy
        # order the inserts and fill the foreign key itself at flush time.
        changed = _apply(existing[seed.code], {"name": seed.name, "parent": parent, "active": True})
        result.record(created=seed.code in new_codes, changed=changed)

    session.flush()
    return result


def _sync_stores(session: Session) -> EntityResult:
    result = EntityResult()
    existing = {store.code: store for store in session.scalars(select(Store))}

    for seed in STORES:
        store = existing.get(seed.code)
        is_new = store is None
        if store is None:
            store = Store(code=seed.code)
            session.add(store)
        changed = _apply(
            store,
            {
                "name": seed.name,
                "region": seed.region,
                "store_type": seed.store_type,
                "active": True,
            },
        )
        result.record(created=is_new, changed=changed)

    session.flush()
    return result


def _sync_suppliers(session: Session) -> EntityResult:
    result = EntityResult()
    existing = {supplier.code: supplier for supplier in session.scalars(select(Supplier))}

    for seed in SUPPLIERS:
        supplier = existing.get(seed.code)
        is_new = supplier is None
        if supplier is None:
            supplier = Supplier(code=seed.code)
            session.add(supplier)
        changed = _apply(supplier, {"name": seed.name, "tax_id": seed.tax_id, "active": True})
        result.record(created=is_new, changed=changed)

    session.flush()
    return result


def _sync_products(session: Session) -> EntityResult:
    result = EntityResult()
    categories = {category.code: category for category in session.scalars(select(Category))}
    existing = {product.sku: product for product in session.scalars(select(Product))}

    for seed in PRODUCTS:
        category = categories.get(seed.category_code)
        if category is None:
            raise SeedDataError(
                f"Product {seed.sku!r} references unknown category {seed.category_code!r}."
            )

        product = existing.get(seed.sku)
        is_new = product is None
        if product is None:
            product = Product(sku=seed.sku)
            session.add(product)
        changed = _apply(
            product,
            {
                "name": seed.name,
                "description": seed.description,
                "ean": seed.ean,
                "category": category,
                "active": True,
            },
        )
        result.record(created=is_new, changed=changed)

    session.flush()
    return result


def _sync_supplier_products(session: Session) -> EntityResult:
    result = EntityResult()
    suppliers = {supplier.code: supplier for supplier in session.scalars(select(Supplier))}
    products = {product.sku: product for product in session.scalars(select(Product))}
    existing = {
        (link.supplier_id, link.product_id): link
        for link in session.scalars(select(SupplierProduct))
    }

    for seed in SUPPLIER_PRODUCTS:
        supplier = suppliers.get(seed.supplier_code)
        product = products.get(seed.product_sku)
        if supplier is None:
            raise SeedDataError(f"Unknown supplier code {seed.supplier_code!r} in supplier terms.")
        if product is None:
            raise SeedDataError(f"Unknown product SKU {seed.product_sku!r} in supplier terms.")

        link = existing.get((supplier.id, product.id))
        is_new = link is None
        if link is None:
            link = SupplierProduct(supplier_id=supplier.id, product_id=product.id)
            session.add(link)
        changed = _apply(
            link,
            {
                "supplier_sku": seed.supplier_sku,
                "cost": seed.cost,
                "case_pack": seed.case_pack,
                "minimum_order_quantity": seed.minimum_order_quantity,
                "lead_time_days": seed.lead_time_days,
                "active": True,
            },
        )
        result.record(created=is_new, changed=changed)

    session.flush()
    return result


def main() -> None:
    """Seed the configured database and print what changed."""
    with get_session_factory()() as session:
        summary = seed_reference_data(session)
        session.commit()

    print(summary.format_report())
    print(f"\nTotal: {summary.created} created, {summary.updated} updated.")


if __name__ == "__main__":
    main()
