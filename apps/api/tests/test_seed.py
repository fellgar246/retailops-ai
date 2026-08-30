"""The development reference data, and the idempotency it promises."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from retailops_api.db.seed import (
    CATEGORIES,
    PRODUCTS,
    STORES,
    SUPPLIER_PRODUCTS,
    SUPPLIERS,
    seed_reference_data,
)
from retailops_api.domain.models import (
    Category,
    Product,
    SalesRecord,
    Store,
    Supplier,
    SupplierProduct,
)
from retailops_api.domain.repositories import get_product_by_sku, get_supplier_by_code


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_seeding_creates_every_declared_record(session: Session) -> None:
    summary = seed_reference_data(session)

    assert summary.categories.created == len(CATEGORIES)
    assert summary.products.created == len(PRODUCTS)
    assert summary.suppliers.created == len(SUPPLIERS)
    assert summary.supplier_products.created == len(SUPPLIER_PRODUCTS)
    assert summary.stores.created == len(STORES)


def test_running_twice_does_not_duplicate_records(session: Session) -> None:
    seed_reference_data(session)
    session.commit()
    counts = {
        model: _count(session, model)
        for model in (Category, Product, Supplier, SupplierProduct, Store)
    }

    seed_reference_data(session)
    session.commit()

    assert {model: _count(session, model) for model in counts} == counts


def test_the_second_run_reports_no_changes(session: Session) -> None:
    seed_reference_data(session)
    session.commit()

    summary = seed_reference_data(session)

    assert summary.created == 0
    assert summary.updated == 0


def test_seeding_is_repeatable_many_times(session: Session) -> None:
    for _ in range(3):
        seed_reference_data(session)
        session.commit()

    assert _count(session, Product) == len(PRODUCTS)


def test_seeding_does_not_invent_sales_history(session: Session) -> None:
    """Sales history is produced by the synthetic generator; seeding is catalog only."""
    seed_reference_data(session)

    assert _count(session, SalesRecord) == 0


def test_a_drifted_record_is_corrected_in_place(session: Session) -> None:
    seed_reference_data(session)
    session.commit()
    product = get_product_by_sku(session, "SKU-1001")
    assert product is not None
    original_id, original_name = product.id, product.name
    product.name = "Manually Renamed"
    session.commit()

    summary = seed_reference_data(session)
    session.commit()

    restored = get_product_by_sku(session, "SKU-1001")
    assert restored is not None
    assert restored.id == original_id
    assert restored.name == original_name
    assert summary.products.updated == 1
    assert summary.products.created == 0


def test_the_category_hierarchy_is_wired(session: Session) -> None:
    seed_reference_data(session)

    roots = session.scalars(select(Category.code).where(Category.parent_id.is_(None))).all()
    assert set(roots) == {"BEV", "SNACK", "HOME"}

    children = session.scalars(select(Category).where(Category.parent_id.is_not(None))).all()
    assert children
    for child in children:
        assert child.parent is not None
        assert child.parent.parent_id is None


def test_every_seeded_product_belongs_to_a_leaf_category(session: Session) -> None:
    seed_reference_data(session)

    for product in session.scalars(select(Product)).all():
        assert product.category.parent_id is not None


def test_at_least_one_product_has_no_barcode(session: Session) -> None:
    """Keeps the nullable-unique EAN path exercised by development data."""
    seed_reference_data(session)

    assert session.scalar(select(func.count()).select_from(Product).where(Product.ean.is_(None)))


def test_at_least_one_product_has_two_suppliers(session: Session) -> None:
    """Supplier comparison needs at least one product with competing terms."""
    seed_reference_data(session)

    duplicated = session.execute(
        select(SupplierProduct.product_id)
        .group_by(SupplierProduct.product_id)
        .having(func.count() > 1)
    ).all()

    assert duplicated


def test_a_supplier_may_be_seeded_without_a_tax_id(session: Session) -> None:
    seed_reference_data(session)

    supplier = get_supplier_by_code(session, "SUP-NATGRO")
    assert supplier is not None
    assert supplier.tax_id is None


def test_seeded_stores_cover_several_regions(session: Session) -> None:
    seed_reference_data(session)

    regions = set(session.scalars(select(Store.region)).all())
    assert len(regions) > 1


@pytest.mark.parametrize(
    ("declared", "attribute"),
    [
        (CATEGORIES, "code"),
        (PRODUCTS, "sku"),
        (SUPPLIERS, "code"),
        (STORES, "code"),
    ],
    ids=["categories", "products", "suppliers", "stores"],
)
def test_declared_business_codes_are_unique(declared: tuple[object, ...], attribute: str) -> None:
    codes = [getattr(seed, attribute) for seed in declared]
    assert len(codes) == len(set(codes))


def test_declared_supplier_terms_are_unique_per_pairing() -> None:
    pairings = [(seed.supplier_code, seed.product_sku) for seed in SUPPLIER_PRODUCTS]
    assert len(pairings) == len(set(pairings))


def test_declared_barcodes_are_unique() -> None:
    barcodes = [seed.ean for seed in PRODUCTS if seed.ean is not None]
    assert len(barcodes) == len(set(barcodes))
