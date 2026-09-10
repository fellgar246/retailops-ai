"""Build the weekly demand panel from persisted sales.

The command line scores a portable dataset read from disk or generated
synthetically. An operator triggering an evaluation means the history the
platform already holds, so the panel is aggregated straight from the database
rather than reconstructing a whole portable dataset to throw most of it away.

The aggregation is the one the file-backed builder performs: daily units summed
into ISO weeks per store and category, incomplete weeks at either end dropped,
and quiet weeks stored as zero so the panel stays balanced.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from retailops_api.domain.models.category import Category
from retailops_api.domain.models.product import Product
from retailops_api.domain.models.sales_record import SalesRecord
from retailops_api.domain.models.store import Store
from retailops_api.forecasting.frame import ForecastFrame, ForecastRow
from retailops_api.forecasting.problem import WEEKLY_CATEGORY_STORE_DEMAND, ForecastProblem
from retailops_api.forecasting.weeks import complete_week_starts, iso_week_start


class NoHistoryError(ValueError):
    """There is not enough persisted history to build a panel."""


def build_frame_from_database(
    session: Session,
    problem: ForecastProblem | None = None,
) -> ForecastFrame:
    chosen = problem or WEEKLY_CATEGORY_STORE_DEMAND

    span = session.execute(
        select(func.min(SalesRecord.business_date), func.max(SalesRecord.business_date))
    ).one()
    start, end = span
    if start is None or end is None:
        raise NoHistoryError("no sales history has been ingested")

    weeks = complete_week_starts(start, end)
    if chosen.history_periods is not None:
        weeks = weeks[-chosen.history_periods :]
    if not weeks:
        raise NoHistoryError("the sales history does not cover a complete week")
    week_set = set(weeks)

    stores = sorted(session.scalars(select(Store.code)).all())
    categories = sorted(session.scalars(select(Category.code)).all())
    if not stores or not categories:
        raise NoHistoryError("the catalog has no stores or no categories")

    totals: dict[tuple[str, str, date], float] = defaultdict(float)
    rows = session.execute(
        select(
            Store.code,
            Category.code,
            SalesRecord.business_date,
            SalesRecord.units_sold,
        )
        .join(Store, Store.id == SalesRecord.store_id)
        .join(Product, Product.id == SalesRecord.product_id)
        .join(Category, Category.id == Product.category_id)
    )
    for store_code, category_code, business_date, units in rows:
        week = iso_week_start(business_date)
        if week not in week_set:
            continue
        totals[(store_code, category_code, week)] += float(units)

    panel = [
        ForecastRow(
            store_code=store,
            category_code=category,
            period_start=week,
            target=totals.get((store, category, week), 0.0),
        )
        for store in stores
        for category in categories
        for week in weeks
    ]
    return ForecastFrame(problem=chosen, rows=tuple(panel))
