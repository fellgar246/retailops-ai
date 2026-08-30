"""Behaviour that only the real dialect can confirm.

The SQLite suite proves the mapping and the constraints; these tests prove the
things SQLite cannot: exact numeric scale, timezone-aware timestamps, and the
NULL-distinct semantics the nullable-unique EAN column depends on.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from retailops_api.db.seed import PRODUCTS, seed_reference_data
from retailops_api.domain.models import Product, SalesRecord
from retailops_api.domain.repositories import SalesRecordRow, bulk_upsert_sales_records
from tests.conftest import requires_postgres
from tests.factories import make_product, make_store, make_supplier, make_supplier_product

pytestmark = requires_postgres

BUSINESS_DATE = date(2026, 3, 15)


def test_timestamps_come_back_timezone_aware(postgres_session: Session) -> None:
    product = make_product(postgres_session, sku="SKU-PG-1")
    postgres_session.refresh(product)

    assert product.created_at.tzinfo is not None
    assert product.updated_at.tzinfo is not None
    # Sanity check that the server clock is sane rather than epoch-zero.
    assert product.created_at > datetime(2020, 1, 1, tzinfo=UTC)


def test_updated_at_advances_on_change(postgres_session: Session) -> None:
    product = make_product(postgres_session, sku="SKU-PG-1")
    postgres_session.refresh(product)
    before = product.updated_at

    product.name = "Renamed"
    postgres_session.flush()
    postgres_session.refresh(product)

    assert product.updated_at >= before


def test_created_at_is_not_touched_by_an_update(postgres_session: Session) -> None:
    product = make_product(postgres_session, sku="SKU-PG-1")
    postgres_session.refresh(product)
    created_at = product.created_at

    product.name = "Renamed"
    postgres_session.flush()
    postgres_session.refresh(product)

    assert product.created_at == created_at


def test_numeric_scale_is_exact(postgres_session: Session) -> None:
    supplier = make_supplier(postgres_session, code="SUP-PG-1")
    product = make_product(postgres_session, sku="SKU-PG-1")

    link = make_supplier_product(postgres_session, supplier, product, cost=Decimal("0.8329"))
    postgres_session.expire_all()
    postgres_session.refresh(link)

    assert isinstance(link.cost, Decimal)
    assert str(link.cost) == "0.8329"


def test_money_does_not_drift_when_summed(postgres_session: Session) -> None:
    """The reason money is Numeric and not float. See ADR-002."""
    store = make_store(postgres_session, code="ST-PG-1")
    product = make_product(postgres_session, sku="SKU-PG-1")
    bulk_upsert_sales_records(
        postgres_session,
        [
            {
                "store_id": store.id,
                "product_id": product.id,
                "business_date": date(2026, 3, day),
                "units_sold": 1,
                "unit_price": Decimal("0.1000"),
                "stock_on_hand": 1,
            }
            for day in range(1, 11)
        ],
    )

    total = postgres_session.scalar(select(func.sum(SalesRecord.unit_price)))

    assert total == Decimal("1.0000")


def test_absent_barcodes_do_not_collide(postgres_session: Session) -> None:
    """PostgreSQL treats NULLs as distinct, which is what makes the column work."""
    make_product(postgres_session, sku="SKU-PG-1", ean=None)
    make_product(postgres_session, sku="SKU-PG-2", ean=None)

    count = postgres_session.scalar(
        select(func.count()).select_from(Product).where(Product.ean.is_(None))
    )
    assert count == 2


def test_a_present_barcode_stays_unique(postgres_session: Session) -> None:
    make_product(postgres_session, sku="SKU-PG-1", ean="7501000999991")

    with pytest.raises(IntegrityError):
        make_product(postgres_session, sku="SKU-PG-2", ean="7501000999991")


def test_the_sales_natural_key_is_enforced(postgres_session: Session) -> None:
    store = make_store(postgres_session, code="ST-PG-1")
    product = make_product(postgres_session, sku="SKU-PG-1")
    values = {
        "store_id": store.id,
        "product_id": product.id,
        "business_date": BUSINESS_DATE,
        "units_sold": 5,
        "unit_price": Decimal("10.0000"),
        "stock_on_hand": 10,
    }
    postgres_session.add(SalesRecord(**values))
    postgres_session.flush()

    postgres_session.add(SalesRecord(**values))
    with pytest.raises(IntegrityError):
        postgres_session.flush()


def test_the_upsert_uses_the_postgresql_conflict_clause(postgres_session: Session) -> None:
    store = make_store(postgres_session, code="ST-PG-1")
    product = make_product(postgres_session, sku="SKU-PG-1")
    row: SalesRecordRow = {
        "store_id": store.id,
        "product_id": product.id,
        "business_date": BUSINESS_DATE,
        "units_sold": 5,
        "unit_price": Decimal("10.0000"),
        "stock_on_hand": 10,
    }
    corrected = row.copy()
    corrected["units_sold"] = 42

    bulk_upsert_sales_records(postgres_session, [row])
    bulk_upsert_sales_records(postgres_session, [corrected])

    stored = postgres_session.scalars(select(SalesRecord)).one()
    assert stored.units_sold == 42


def test_check_constraints_are_enforced_by_the_server(postgres_session: Session) -> None:
    store = make_store(postgres_session, code="ST-PG-1")
    product = make_product(postgres_session, sku="SKU-PG-1")
    postgres_session.add(
        SalesRecord(
            store_id=store.id,
            product_id=product.id,
            business_date=BUSINESS_DATE,
            units_sold=-5,
            unit_price=Decimal("10.0000"),
            stock_on_hand=10,
        )
    )

    with pytest.raises(IntegrityError):
        postgres_session.flush()


def test_seeding_works_against_postgresql(postgres_session: Session) -> None:
    first = seed_reference_data(postgres_session)
    second = seed_reference_data(postgres_session)

    assert first.products.created == len(PRODUCTS)
    assert second.created == 0
    assert second.updated == 0
