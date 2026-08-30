"""The data-access helpers: lookups by business code and bulk sales writes."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from retailops_api.domain.models import SalesRecord
from retailops_api.domain.repositories import (
    SalesRecordRow,
    bulk_insert_sales_records,
    bulk_upsert_sales_records,
    category_ids_by_code,
    get_category_by_code,
    get_product_by_sku,
    get_store_by_code,
    get_supplier_by_code,
    get_supplier_product,
    product_ids_by_sku,
    store_ids_by_code,
    supplier_ids_by_code,
)
from tests.factories import (
    make_category,
    make_product,
    make_store,
    make_supplier,
    make_supplier_product,
)

BUSINESS_DATE = date(2026, 3, 15)


# --------------------------------------------------------------------------- #
# Lookups by business code
# --------------------------------------------------------------------------- #


def test_category_is_found_by_code(session: Session) -> None:
    make_category(session, code="BEV", name="Beverages")

    found = get_category_by_code(session, "BEV")

    assert found is not None
    assert found.name == "Beverages"


def test_product_is_found_by_sku(session: Session) -> None:
    make_product(session, sku="SKU-1001", name="Cola 355ml")

    found = get_product_by_sku(session, "SKU-1001")

    assert found is not None
    assert found.name == "Cola 355ml"


def test_supplier_is_found_by_code(session: Session) -> None:
    make_supplier(session, code="SUP-BEVCO", name="BevCo")

    found = get_supplier_by_code(session, "SUP-BEVCO")

    assert found is not None
    assert found.name == "BevCo"


def test_store_is_found_by_code(session: Session) -> None:
    make_store(session, code="ST-001", name="Centro")

    found = get_store_by_code(session, "ST-001")

    assert found is not None
    assert found.name == "Centro"


def test_supplier_terms_are_found_by_pairing(session: Session) -> None:
    supplier = make_supplier(session, code="SUP-1")
    product = make_product(session, sku="SKU-1001")
    make_supplier_product(session, supplier, product, cost=Decimal("7.4500"))

    found = get_supplier_product(session, supplier.id, product.id)

    assert found is not None
    assert found.cost == Decimal("7.4500")


@pytest.mark.parametrize(
    "lookup",
    [get_category_by_code, get_product_by_sku, get_supplier_by_code, get_store_by_code],
)
def test_an_unknown_code_returns_none(session: Session, lookup: object) -> None:
    assert lookup(session, "DOES-NOT-EXIST") is None  # type: ignore[operator]


def test_lookups_are_case_sensitive(session: Session) -> None:
    """Business codes are exact strings; no implicit normalisation happens."""
    make_product(session, sku="SKU-1001")

    assert get_product_by_sku(session, "sku-1001") is None


# --------------------------------------------------------------------------- #
# Bulk code -> id maps
# --------------------------------------------------------------------------- #


def test_product_ids_are_resolved_in_one_query(session: Session) -> None:
    first = make_product(session, sku="SKU-1001")
    second = make_product(session, sku="SKU-1002")

    resolved = product_ids_by_sku(session, ["SKU-1001", "SKU-1002", "SKU-MISSING"])

    assert resolved == {"SKU-1001": first.id, "SKU-1002": second.id}


def test_store_ids_are_resolved_in_one_query(session: Session) -> None:
    store = make_store(session, code="ST-001")

    assert store_ids_by_code(session, ["ST-001", "ST-999"]) == {"ST-001": store.id}


def test_category_and_supplier_ids_are_resolved(session: Session) -> None:
    category = make_category(session, code="BEV")
    supplier = make_supplier(session, code="SUP-1")

    assert category_ids_by_code(session, ["BEV"]) == {"BEV": category.id}
    assert supplier_ids_by_code(session, ["SUP-1"]) == {"SUP-1": supplier.id}


@pytest.mark.parametrize(
    "resolver",
    [product_ids_by_sku, store_ids_by_code, category_ids_by_code, supplier_ids_by_code],
)
def test_resolving_nothing_touches_the_database(session: Session, resolver: object) -> None:
    assert resolver(session, []) == {}  # type: ignore[operator]


# --------------------------------------------------------------------------- #
# Bulk sales insertion
# --------------------------------------------------------------------------- #


@pytest.fixture
def sales_context(session: Session) -> tuple[int, int]:
    store = make_store(session, code="ST-001")
    product = make_product(session, sku="SKU-1001")
    return store.id, product.id


def _row(store_id: int, product_id: int, **overrides: object) -> SalesRecordRow:
    row: SalesRecordRow = {
        "store_id": store_id,
        "product_id": product_id,
        "business_date": BUSINESS_DATE,
        "units_sold": 10,
        "unit_price": Decimal("19.9900"),
        "stock_on_hand": 40,
    }
    row.update(overrides)  # type: ignore[typeddict-item]
    return row


def test_bulk_insert_writes_every_row(session: Session, sales_context: tuple[int, int]) -> None:
    store_id, product_id = sales_context
    rows = [
        _row(store_id, product_id, business_date=date(2026, 3, day), units_sold=day)
        for day in range(1, 11)
    ]

    inserted = bulk_insert_sales_records(session, rows)

    assert inserted == 10
    assert session.scalar(select(func.count()).select_from(SalesRecord)) == 10


def test_bulk_insert_applies_the_measure_defaults(
    session: Session, sales_context: tuple[int, int]
) -> None:
    store_id, product_id = sales_context

    bulk_insert_sales_records(session, [_row(store_id, product_id)])

    stored = session.scalars(select(SalesRecord)).one()
    assert stored.discount_amount == Decimal("0")
    assert stored.promotion is False


def test_bulk_insert_keeps_explicit_promotion_values(
    session: Session, sales_context: tuple[int, int]
) -> None:
    store_id, product_id = sales_context
    rows = [
        _row(
            store_id,
            product_id,
            business_date=date(2026, 3, 1),
            promotion=True,
            discount_amount=Decimal("2.5000"),
        ),
        _row(store_id, product_id, business_date=date(2026, 3, 2)),
    ]

    bulk_insert_sales_records(session, rows)

    by_date = {
        record.business_date: record for record in session.scalars(select(SalesRecord)).all()
    }
    assert by_date[date(2026, 3, 1)].promotion is True
    assert by_date[date(2026, 3, 1)].discount_amount == Decimal("2.5000")
    assert by_date[date(2026, 3, 2)].promotion is False


def test_bulk_insert_refuses_a_duplicate_natural_key(
    session: Session, sales_context: tuple[int, int]
) -> None:
    store_id, product_id = sales_context
    bulk_insert_sales_records(session, [_row(store_id, product_id)])

    with pytest.raises(IntegrityError):
        bulk_insert_sales_records(session, [_row(store_id, product_id, units_sold=99)])


def test_bulk_insert_of_nothing_is_a_no_op(session: Session) -> None:
    assert bulk_insert_sales_records(session, []) == 0


def test_upsert_inserts_rows_that_are_new(session: Session, sales_context: tuple[int, int]) -> None:
    store_id, product_id = sales_context

    sent = bulk_upsert_sales_records(session, [_row(store_id, product_id)])

    assert sent == 1
    assert session.scalar(select(func.count()).select_from(SalesRecord)) == 1


def test_upsert_corrects_a_row_instead_of_duplicating_it(
    session: Session, sales_context: tuple[int, int]
) -> None:
    """Re-ingesting a corrected file must be safe and repeatable."""
    store_id, product_id = sales_context
    bulk_upsert_sales_records(session, [_row(store_id, product_id, units_sold=10)])

    bulk_upsert_sales_records(
        session,
        [
            _row(
                store_id,
                product_id,
                units_sold=17,
                unit_price=Decimal("21.5000"),
                discount_amount=Decimal("1.0000"),
                promotion=True,
                stock_on_hand=12,
            )
        ],
    )

    stored = session.scalars(select(SalesRecord)).one()
    assert stored.units_sold == 17
    assert stored.unit_price == Decimal("21.5000")
    assert stored.discount_amount == Decimal("1.0000")
    assert stored.promotion is True
    assert stored.stock_on_hand == 12


def test_upsert_preserves_the_first_seen_time(
    session: Session, sales_context: tuple[int, int]
) -> None:
    store_id, product_id = sales_context
    bulk_upsert_sales_records(session, [_row(store_id, product_id)])
    created_at = session.scalars(select(SalesRecord)).one().created_at

    session.expire_all()
    bulk_upsert_sales_records(session, [_row(store_id, product_id, units_sold=99)])

    assert session.scalars(select(SalesRecord)).one().created_at == created_at


def test_upsert_is_idempotent(session: Session, sales_context: tuple[int, int]) -> None:
    store_id, product_id = sales_context
    rows = [_row(store_id, product_id, business_date=date(2026, 3, day)) for day in range(1, 6)]

    bulk_upsert_sales_records(session, rows)
    bulk_upsert_sales_records(session, rows)

    assert session.scalar(select(func.count()).select_from(SalesRecord)) == 5


def test_upsert_handles_a_mix_of_new_and_existing_rows(
    session: Session, sales_context: tuple[int, int]
) -> None:
    store_id, product_id = sales_context
    bulk_upsert_sales_records(
        session, [_row(store_id, product_id, business_date=date(2026, 3, 1), units_sold=1)]
    )

    bulk_upsert_sales_records(
        session,
        [
            _row(store_id, product_id, business_date=date(2026, 3, 1), units_sold=100),
            _row(store_id, product_id, business_date=date(2026, 3, 2), units_sold=2),
        ],
    )

    stored = {
        record.business_date: record.units_sold
        for record in session.scalars(select(SalesRecord)).all()
    }
    assert stored == {date(2026, 3, 1): 100, date(2026, 3, 2): 2}


def test_batching_does_not_change_the_result(
    session: Session, sales_context: tuple[int, int]
) -> None:
    store_id, product_id = sales_context
    rows = [
        _row(store_id, product_id, business_date=date(2026, 3, day), units_sold=day)
        for day in range(1, 26)
    ]

    sent = bulk_upsert_sales_records(session, rows, batch_size=7)

    assert sent == 25
    assert session.scalar(select(func.count()).select_from(SalesRecord)) == 25


def test_an_invalid_batch_size_is_rejected(
    session: Session, sales_context: tuple[int, int]
) -> None:
    store_id, product_id = sales_context

    with pytest.raises(ValueError, match="batch_size"):
        bulk_upsert_sales_records(session, [_row(store_id, product_id)], batch_size=0)


def test_bulk_writes_still_honour_the_check_constraints(
    session: Session, sales_context: tuple[int, int]
) -> None:
    store_id, product_id = sales_context

    with pytest.raises(IntegrityError):
        bulk_insert_sales_records(session, [_row(store_id, product_id, units_sold=-1)])


def test_bulk_writes_accept_a_generator(session: Session, sales_context: tuple[int, int]) -> None:
    """Ingestion streams rows; the helpers must not require a materialised list."""
    store_id, product_id = sales_context
    rows = (_row(store_id, product_id, business_date=date(2026, 3, day)) for day in range(1, 4))

    assert bulk_insert_sales_records(session, rows, batch_size=2) == 3
