"""Deterministic reference data for local development.

Every record is identified by its business code, so seeding is idempotent:
running it twice creates nothing the second time, and editing a name below and
re-running updates the existing row in place rather than inserting a duplicate.

No sales history is seeded here; generate that with ``make synthetic``.

Run with ``make seed`` or ``uv run retailops-seed``.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from retailops_api.dataset.contract import (
    Catalog,
    CategoryRow,
    ProductRow,
    StoreRow,
    SupplierProductRow,
    SupplierRow,
)
from retailops_api.db.session import get_session_factory
from retailops_api.ingestion.catalog import (
    CatalogIngestionError,
    CatalogIngestionResult,
    ingest_catalog,
)

# Names kept so existing tests and callers keep importing the same symbols.
CategorySeed = CategoryRow
ProductSeed = ProductRow
SupplierSeed = SupplierRow
SupplierProductSeed = SupplierProductRow
StoreSeed = StoreRow
SeedDataError = CatalogIngestionError
SeedSummary = CatalogIngestionResult

CATEGORIES: tuple[CategoryRow, ...] = (
    CategoryRow("BEV", "Beverages"),
    CategoryRow("SNACK", "Snacks"),
    CategoryRow("HOME", "Household"),
    CategoryRow("BEV-SOFT", "Soft Drinks", "BEV"),
    CategoryRow("BEV-WATER", "Water", "BEV"),
    CategoryRow("BEV-COFFEE", "Coffee & Tea", "BEV"),
    CategoryRow("SNACK-CHIPS", "Chips & Crisps", "SNACK"),
    CategoryRow("SNACK-CANDY", "Candy & Chocolate", "SNACK"),
    CategoryRow("HOME-CLEAN", "Cleaning Supplies", "HOME"),
    CategoryRow("HOME-PAPER", "Paper Goods", "HOME"),
)

PRODUCTS: tuple[ProductRow, ...] = (
    ProductRow("SKU-1001", "Cola Classic 355ml Can", "BEV-SOFT", "7501000110018"),
    ProductRow("SKU-1002", "Cola Zero 355ml Can", "BEV-SOFT", "7501000110025"),
    ProductRow("SKU-1003", "Orange Soda 600ml Bottle", "BEV-SOFT", "7501000110032"),
    ProductRow("SKU-1004", "Still Water 1L Bottle", "BEV-WATER", "7501000110049"),
    ProductRow("SKU-1005", "Sparkling Water 500ml Bottle", "BEV-WATER", "7501000110056"),
    ProductRow("SKU-1006", "Ground Coffee 500g", "BEV-COFFEE", "7501000110063"),
    # Deliberately without a barcode: exercises the nullable unique EAN column.
    ProductRow("SKU-1007", "Loose Leaf Green Tea 100g", "BEV-COFFEE"),
    ProductRow("SKU-2001", "Salted Potato Chips 150g", "SNACK-CHIPS", "7501000120017"),
    ProductRow("SKU-2002", "Spicy Tortilla Chips 180g", "SNACK-CHIPS", "7501000120024"),
    ProductRow("SKU-2003", "Milk Chocolate Bar 100g", "SNACK-CANDY", "7501000120031"),
    ProductRow("SKU-2004", "Fruit Gummies 90g", "SNACK-CANDY", "7501000120048"),
    ProductRow("SKU-3001", "Multi-Surface Cleaner 750ml", "HOME-CLEAN", "7501000130016"),
    ProductRow("SKU-3002", "Dishwashing Liquid 500ml", "HOME-CLEAN", "7501000130023"),
    ProductRow("SKU-3003", "Paper Towels 2-Pack", "HOME-PAPER", "7501000130030"),
    ProductRow("SKU-3004", "Toilet Paper 4-Pack", "HOME-PAPER", "7501000130047"),
)

SUPPLIERS: tuple[SupplierRow, ...] = (
    SupplierRow("SUP-BEVCO", "BevCo Distribution", "BEV920304AB1"),
    SupplierRow("SUP-SNACKW", "Snackworks Wholesale", "SNK850612CD2"),
    SupplierRow("SUP-HOMESUP", "HomeSupply Partners", "HSP001122EF3"),
    SupplierRow("SUP-NATGRO", "National Grocery Group", None),
)

SUPPLIER_PRODUCTS: tuple[SupplierProductRow, ...] = (
    SupplierProductRow("SUP-BEVCO", "SKU-1001", Decimal("7.4500"), 24, 2, 3, "BC-COLA-355"),
    SupplierProductRow("SUP-BEVCO", "SKU-1002", Decimal("7.4500"), 24, 2, 3, "BC-COLAZ-355"),
    SupplierProductRow("SUP-BEVCO", "SKU-1003", Decimal("9.8000"), 12, 1, 3, "BC-ORNG-600"),
    SupplierProductRow("SUP-BEVCO", "SKU-1004", Decimal("5.2500"), 12, 1, 2, "BC-WATER-1L"),
    SupplierProductRow("SUP-BEVCO", "SKU-1005", Decimal("6.1000"), 12, 1, 2, "BC-SPKL-500"),
    SupplierProductRow("SUP-BEVCO", "SKU-1006", Decimal("48.9000"), 6, 1, 7, "BC-COFFEE-500"),
    SupplierProductRow("SUP-SNACKW", "SKU-2001", Decimal("12.3000"), 20, 1, 4, "SW-CHIP-150"),
    SupplierProductRow("SUP-SNACKW", "SKU-2002", Decimal("14.7500"), 20, 1, 4, "SW-TORT-180"),
    SupplierProductRow("SUP-SNACKW", "SKU-2003", Decimal("16.4000"), 18, 2, 5, "SW-CHOC-100"),
    SupplierProductRow("SUP-SNACKW", "SKU-2004", Decimal("8.9500"), 24, 1, 5, "SW-GUMM-90"),
    SupplierProductRow("SUP-HOMESUP", "SKU-3001", Decimal("22.5000"), 12, 1, 6, "HS-CLEAN-750"),
    SupplierProductRow("SUP-HOMESUP", "SKU-3002", Decimal("18.2500"), 12, 1, 6, "HS-DISH-500"),
    SupplierProductRow("SUP-HOMESUP", "SKU-3003", Decimal("26.0000"), 8, 1, 6, "HS-TOWEL-2"),
    SupplierProductRow("SUP-HOMESUP", "SKU-3004", Decimal("31.5000"), 8, 1, 6, "HS-TP-4"),
    # Second source for four products, so supplier comparison has something to
    # compare: slower and pricier, but a smaller minimum.
    SupplierProductRow("SUP-NATGRO", "SKU-1001", Decimal("7.9900"), 12, 1, 10, "NG-1001"),
    SupplierProductRow("SUP-NATGRO", "SKU-2001", Decimal("12.9900"), 10, 1, 9, "NG-2001"),
    SupplierProductRow("SUP-NATGRO", "SKU-2003", Decimal("17.1000"), 12, 1, 9, "NG-2003"),
    SupplierProductRow("SUP-NATGRO", "SKU-3003", Decimal("27.4000"), 6, 1, 8, "NG-3003"),
    SupplierProductRow("SUP-NATGRO", "SKU-1007", Decimal("33.0000"), 10, 1, 12, "NG-1007"),
)

STORES: tuple[StoreRow, ...] = (
    StoreRow("ST-001", "Centro Flagship", "Central", "flagship"),
    StoreRow("ST-002", "Norte Supermarket", "North", "supermarket"),
    StoreRow("ST-003", "Sur Supermarket", "South", "supermarket"),
    StoreRow("ST-004", "Poniente Express", "West", "express"),
    StoreRow("ST-005", "Oriente Express", "East", "express"),
)


def reference_catalog() -> Catalog:
    """The catalog declared in this module, as a portable dataset."""
    return Catalog(
        categories=CATEGORIES,
        products=PRODUCTS,
        suppliers=SUPPLIERS,
        supplier_products=SUPPLIER_PRODUCTS,
        stores=STORES,
    )


def seed_reference_data(session: Session) -> CatalogIngestionResult:
    """Bring the database in line with the reference data declared in this module.

    Does not commit; the caller owns the transaction.
    """
    return ingest_catalog(session, reference_catalog())


def main() -> None:
    """Seed the configured database and print what changed."""
    with get_session_factory()() as session:
        summary = seed_reference_data(session)
        session.commit()

    print(summary.format_report())
    print(f"\nTotal: {summary.created} created, {summary.updated} updated.")


if __name__ == "__main__":
    main()
