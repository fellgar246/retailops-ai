"""Focused persistence helpers for the retail ingestion paths.

These are deliberately plain functions rather than a generic repository layer:
ingestion needs a handful of lookups by business code and one high-volume write
path, and every other query is better expressed where it is used.

None of these helpers commit. Transaction boundaries belong to the caller.
"""

from collections.abc import Iterable, Iterator, Sequence
from datetime import date
from decimal import Decimal
from itertools import islice
from typing import Any, NotRequired, TypedDict

from sqlalchemy import Executable, insert, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from retailops_api.domain.models import (
    Category,
    Product,
    SalesRecord,
    Store,
    Supplier,
    SupplierProduct,
)

DEFAULT_BATCH_SIZE = 1_000

#: Natural key of a sales fact, as documented in ADR-002.
SALES_NATURAL_KEY = ("store_id", "product_id", "business_date")

#: Measures that a re-ingested row is allowed to correct.
_SALES_MUTABLE_COLUMNS = (
    "units_sold",
    "unit_price",
    "discount_amount",
    "promotion",
    "stock_on_hand",
)


class SalesRecordRow(TypedDict):
    """One row of daily sales, keyed by resolved store and product ids."""

    store_id: int
    product_id: int
    business_date: date
    units_sold: int
    unit_price: Decimal
    stock_on_hand: int
    discount_amount: NotRequired[Decimal]
    promotion: NotRequired[bool]


# --------------------------------------------------------------------------- #
# Catalog lookups by business code
# --------------------------------------------------------------------------- #


def get_category_by_code(session: Session, code: str) -> Category | None:
    return session.scalar(select(Category).where(Category.code == code))


def get_product_by_sku(session: Session, sku: str) -> Product | None:
    return session.scalar(select(Product).where(Product.sku == sku))


def get_supplier_by_code(session: Session, code: str) -> Supplier | None:
    return session.scalar(select(Supplier).where(Supplier.code == code))


def get_store_by_code(session: Session, code: str) -> Store | None:
    return session.scalar(select(Store).where(Store.code == code))


def get_supplier_product(
    session: Session, supplier_id: int, product_id: int
) -> SupplierProduct | None:
    return session.scalar(
        select(SupplierProduct).where(
            SupplierProduct.supplier_id == supplier_id,
            SupplierProduct.product_id == product_id,
        )
    )


# --------------------------------------------------------------------------- #
# Bulk code -> id maps
#
# Ingestion reads business codes from files but writes foreign keys. Resolving a
# whole file's codes in one query keeps that translation off the per-row path.
# --------------------------------------------------------------------------- #


def product_ids_by_sku(session: Session, skus: Iterable[str]) -> dict[str, int]:
    wanted = set(skus)
    if not wanted:
        return {}
    rows = session.execute(select(Product.sku, Product.id).where(Product.sku.in_(wanted))).tuples()
    return dict(rows.all())


def store_ids_by_code(session: Session, codes: Iterable[str]) -> dict[str, int]:
    wanted = set(codes)
    if not wanted:
        return {}
    rows = session.execute(select(Store.code, Store.id).where(Store.code.in_(wanted))).tuples()
    return dict(rows.all())


def category_ids_by_code(session: Session, codes: Iterable[str]) -> dict[str, int]:
    wanted = set(codes)
    if not wanted:
        return {}
    rows = session.execute(
        select(Category.code, Category.id).where(Category.code.in_(wanted))
    ).tuples()
    return dict(rows.all())


def supplier_ids_by_code(session: Session, codes: Iterable[str]) -> dict[str, int]:
    wanted = set(codes)
    if not wanted:
        return {}
    rows = session.execute(
        select(Supplier.code, Supplier.id).where(Supplier.code.in_(wanted))
    ).tuples()
    return dict(rows.all())


# --------------------------------------------------------------------------- #
# Bulk sales insertion
# --------------------------------------------------------------------------- #


def bulk_insert_sales_records(
    session: Session,
    rows: Iterable[SalesRecordRow],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> int:
    """Insert sales rows, failing if any natural key already exists.

    The fast path for loading a period that is known to be empty, such as freshly
    generated synthetic history. Use :func:`bulk_upsert_sales_records` when a row
    may already be present.
    """
    inserted = 0
    for batch in _batched(rows, batch_size):
        session.execute(insert(SalesRecord), [_normalise(row) for row in batch])
        inserted += len(batch)
    return inserted


def bulk_upsert_sales_records(
    session: Session,
    rows: Iterable[SalesRecordRow],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> int:
    """Insert sales rows, overwriting the measures of any row that already exists.

    Makes re-ingesting a corrected file safe and repeatable: the natural key
    ``(store_id, product_id, business_date)`` decides identity, and the measures
    of a conflicting row are replaced rather than duplicated. ``created_at`` is
    left at its original value so the first-seen time survives a correction.

    Returns the number of rows sent, not the number the database changed --
    an upsert cannot distinguish an insert from a no-op update portably.
    """
    dialect = session.get_bind().dialect.name
    sent = 0
    for batch in _batched(rows, batch_size):
        session.execute(_upsert(dialect, [_normalise(row) for row in batch]))
        sent += len(batch)
    return sent


def _upsert(dialect: str, payload: list[dict[str, Any]]) -> Executable:
    """Build the dialect-specific INSERT ... ON CONFLICT DO UPDATE statement.

    The two branches are spelled out rather than sharing a builder because
    PostgreSQL and SQLite expose their own distinct ``Insert`` constructs.
    """
    if dialect == "postgresql":
        postgresql_statement = postgresql_insert(SalesRecord).values(payload)
        return postgresql_statement.on_conflict_do_update(
            index_elements=list(SALES_NATURAL_KEY),
            set_={
                column: postgresql_statement.excluded[column] for column in _SALES_MUTABLE_COLUMNS
            },
        )
    if dialect == "sqlite":
        sqlite_statement = sqlite_insert(SalesRecord).values(payload)
        return sqlite_statement.on_conflict_do_update(
            index_elements=list(SALES_NATURAL_KEY),
            set_={column: sqlite_statement.excluded[column] for column in _SALES_MUTABLE_COLUMNS},
        )
    raise NotImplementedError(f"Bulk sales upsert is not implemented for {dialect!r}.")


def _normalise(row: SalesRecordRow) -> dict[str, Any]:
    """Fill optional measures so every row in a batch has identical keys.

    A multi-values INSERT compiles one column list for the whole batch, so a row
    that omits ``promotion`` while another supplies it would otherwise misalign.
    """
    return {
        "store_id": row["store_id"],
        "product_id": row["product_id"],
        "business_date": row["business_date"],
        "units_sold": row["units_sold"],
        "unit_price": row["unit_price"],
        "discount_amount": row.get("discount_amount", Decimal("0")),
        "promotion": row.get("promotion", False),
        "stock_on_hand": row["stock_on_hand"],
    }


def _batched(rows: Iterable[SalesRecordRow], size: int) -> Iterator[Sequence[SalesRecordRow]]:
    if size < 1:
        raise ValueError("batch_size must be at least 1")
    iterator = iter(rows)
    while batch := list(islice(iterator, size)):
        yield batch
