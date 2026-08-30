"""Batch sales ingestion with a documented duplicate strategy.

Duplicate strategy
------------------
The natural key is ``(store_code, product_sku, business_date)``, resolved to
``(store_id, product_id, business_date)``. A row whose key is already in the
database is counted as a duplicate and upserted: measures are replaced, the
original ``created_at`` is kept. A second ingest of the same file is therefore
a no-op on row count and a correction on drifted measures.

Rows that fail validation (unknown store or SKU, negative measures, a
duplicate key inside the file) are rejected and listed; they do not abort the
accepted rows.

Transaction boundaries
----------------------
This function does not commit. The caller opens the transaction, calls this
function, and commits or rolls back. A database error raises and the caller
should roll back the whole batch. Validation rejects are not a database
error: they are reported and the accepted rows are still written.

Writes go through the bulk upsert helper, never one ORM ``add`` per row.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from retailops_api.dataset.contract import SalesRow
from retailops_api.dataset.validate import ValidationIssue
from retailops_api.domain.models import SalesRecord
from retailops_api.domain.repositories import (
    DEFAULT_BATCH_SIZE,
    SalesRecordRow,
    bulk_upsert_sales_records,
    product_ids_by_sku,
    store_ids_by_code,
)


@dataclass
class SalesIngestionStats:
    rows_read: int = 0
    rows_accepted: int = 0
    rows_rejected: int = 0
    duplicate_count: int = 0
    validation_errors: list[ValidationIssue] = field(default_factory=list)


def ingest_sales(
    session: Session,
    rows: Iterable[SalesRow],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> SalesIngestionStats:
    """Upsert sales rows. Does not commit; the caller owns the transaction."""
    payload = list(rows)
    stats = SalesIngestionStats(rows_read=len(payload))
    if not payload:
        return stats

    accepted, rejects = _screen(payload)
    stats.validation_errors = rejects
    stats.rows_rejected = len(rejects)
    if not accepted:
        return stats

    store_ids = store_ids_by_code(session, (row.store_code for row, _ in accepted))
    product_ids = product_ids_by_sku(session, (row.product_sku for row, _ in accepted))

    resolved: list[tuple[SalesRow, int, SalesRecordRow]] = []
    for row, number in accepted:
        store_id = store_ids.get(row.store_code)
        product_id = product_ids.get(row.product_sku)
        key = f"{row.store_code}/{row.product_sku}/{row.business_date.isoformat()}"
        if store_id is None:
            stats.validation_errors.append(
                ValidationIssue(
                    table="daily_sales",
                    code="broken_reference",
                    message=f"store_code {row.store_code!r} is not in the catalog",
                    row_number=number,
                    field="store_code",
                    natural_key=key,
                )
            )
            continue
        if product_id is None:
            stats.validation_errors.append(
                ValidationIssue(
                    table="daily_sales",
                    code="broken_reference",
                    message=f"product_sku {row.product_sku!r} is not in the catalog",
                    row_number=number,
                    field="product_sku",
                    natural_key=key,
                )
            )
            continue
        resolved.append(
            (
                row,
                number,
                {
                    "store_id": store_id,
                    "product_id": product_id,
                    "business_date": row.business_date,
                    "units_sold": row.units_sold,
                    "unit_price": row.unit_price,
                    "discount_amount": row.discount_amount,
                    "promotion": row.promotion,
                    "stock_on_hand": row.stock_on_hand,
                },
            )
        )

    stats.rows_rejected = len(stats.validation_errors)
    if not resolved:
        return stats

    stats.duplicate_count = _count_existing(session, [record for _, _, record in resolved])
    bulk_upsert_sales_records(session, (record for _, _, record in resolved), batch_size=batch_size)
    stats.rows_accepted = len(resolved)
    return stats


def _screen(rows: Sequence[SalesRow]) -> tuple[list[tuple[SalesRow, int]], list[ValidationIssue]]:
    accepted: list[tuple[SalesRow, int]] = []
    rejects: list[ValidationIssue] = []
    seen: set[tuple[str, str, date]] = set()
    for number, row in enumerate(rows, start=1):
        key = (row.store_code, row.product_sku, row.business_date)
        natural = f"{row.store_code}/{row.product_sku}/{row.business_date.isoformat()}"
        if key in seen:
            rejects.append(
                ValidationIssue(
                    table="daily_sales",
                    code="duplicate_key",
                    message="natural key already appears earlier in this file",
                    row_number=number,
                    field="business_date",
                    natural_key=natural,
                )
            )
            continue
        seen.add(key)
        problem = _row_problem(row)
        if problem is not None:
            field_name, message = problem
            rejects.append(
                ValidationIssue(
                    table="daily_sales",
                    code="negative_value" if "must be >=" in message else "invalid_identifier",
                    message=message,
                    row_number=number,
                    field=field_name,
                    natural_key=natural,
                )
            )
            continue
        accepted.append((row, number))
    return accepted, rejects


def _row_problem(row: SalesRow) -> tuple[str, str] | None:
    for field_name, value in (
        ("units_sold", row.units_sold),
        ("unit_price", row.unit_price),
        ("discount_amount", row.discount_amount),
        ("stock_on_hand", row.stock_on_hand),
    ):
        if value < 0:
            return field_name, f"{field_name} {value} must be >= 0"
    if not isinstance(row.unit_price, Decimal):
        return "unit_price", "unit_price must be a decimal"
    return None


def _count_existing(session: Session, rows: Sequence[SalesRecordRow]) -> int:
    store_ids = {row["store_id"] for row in rows}
    product_ids = {row["product_id"] for row in rows}
    dates = {row["business_date"] for row in rows}
    existing = {
        (store_id, product_id, business_date)
        for store_id, product_id, business_date in session.execute(
            select(SalesRecord.store_id, SalesRecord.product_id, SalesRecord.business_date).where(
                SalesRecord.store_id.in_(store_ids),
                SalesRecord.product_id.in_(product_ids),
                SalesRecord.business_date.in_(dates),
            )
        ).all()
    }
    return sum(
        1 for row in rows if (row["store_id"], row["product_id"], row["business_date"]) in existing
    )
