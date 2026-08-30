"""Build the canonical weekly demand frame from daily sales history."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date

from retailops_api.dataset.contract import Dataset
from retailops_api.forecasting.problem import WEEKLY_CATEGORY_STORE_DEMAND, ForecastProblem
from retailops_api.forecasting.weeks import complete_week_starts, iso_week_start

FRAME_COLUMNS = ("store_code", "category_code", "period_start", "target")


@dataclass(frozen=True)
class ForecastEntity:
    """One series in the weekly category-demand panel."""

    store_code: str
    category_code: str


@dataclass(frozen=True)
class ForecastRow:
    """One week of demand for one store and category."""

    store_code: str
    category_code: str
    period_start: date
    target: float

    @property
    def entity(self) -> ForecastEntity:
        return ForecastEntity(self.store_code, self.category_code)


@dataclass(frozen=True)
class ForecastFrame:
    """Balanced weekly panel used by every baseline and every split.

    Rows are unique on ``(store_code, category_code, period_start)``. Builders
    sort them in that order. Methods that slice by cutoff never shuffle rows.
    """

    problem: ForecastProblem
    rows: tuple[ForecastRow, ...]

    def __post_init__(self) -> None:
        seen: set[tuple[str, str, date]] = set()
        for row in self.rows:
            key = (row.store_code, row.category_code, row.period_start)
            if key in seen:
                raise ValueError(f"duplicate forecast row {key}")
            seen.add(key)

    def entities(self) -> tuple[ForecastEntity, ...]:
        unique: list[ForecastEntity] = []
        seen: set[ForecastEntity] = set()
        for row in self.rows:
            if row.entity not in seen:
                seen.add(row.entity)
                unique.append(row.entity)
        return tuple(unique)

    def periods(self) -> tuple[date, ...]:
        return tuple(sorted({row.period_start for row in self.rows}))

    def series(self, entity: ForecastEntity) -> tuple[ForecastRow, ...]:
        return tuple(
            row
            for row in self.rows
            if row.store_code == entity.store_code and row.category_code == entity.category_code
        )

    def up_to(self, cutoff: date) -> ForecastFrame:
        """Rows whose ``period_start`` is on or before ``cutoff`` (inclusive)."""
        return ForecastFrame(
            problem=self.problem,
            rows=tuple(row for row in self.rows if row.period_start <= cutoff),
        )

    def after(self, cutoff: date) -> ForecastFrame:
        """Rows whose ``period_start`` is strictly after ``cutoff``."""
        return ForecastFrame(
            problem=self.problem,
            rows=tuple(row for row in self.rows if row.period_start > cutoff),
        )

    def between(self, start: date, end: date) -> ForecastFrame:
        """Rows with ``start < period_start <= end``."""
        return ForecastFrame(
            problem=self.problem,
            rows=tuple(row for row in self.rows if start < row.period_start <= end),
        )

    def target_at(self, entity: ForecastEntity, period_start: date) -> float | None:
        for row in self.rows:
            if (
                row.store_code == entity.store_code
                and row.category_code == entity.category_code
                and row.period_start == period_start
            ):
                return row.target
        return None

    def last_target(self, entity: ForecastEntity, *, on_or_before: date) -> float | None:
        history = [row for row in self.series(entity) if row.period_start <= on_or_before]
        if not history:
            return None
        return max(history, key=lambda row: row.period_start).target


def build_forecast_frame(
    dataset: Dataset,
    problem: ForecastProblem | None = None,
) -> ForecastFrame:
    """Aggregate daily sales into the weekly category-demand panel.

    Incomplete ISO weeks at either end of the history are dropped. Weeks that
    fall inside the complete range and have no sales for an entity are stored
    as ``0``. If ``problem.history_periods`` is set, only the trailing that
    many complete weeks are kept.
    """
    chosen = problem or WEEKLY_CATEGORY_STORE_DEMAND
    start, end = _history_span(dataset)
    if start is None or end is None:
        return ForecastFrame(problem=chosen, rows=())

    weeks = complete_week_starts(start, end)
    if chosen.history_periods is not None:
        if chosen.history_periods < 1:
            raise ValueError("history_periods must be at least 1")
        weeks = weeks[-chosen.history_periods :]
    week_set = set(weeks)
    if not weeks:
        return ForecastFrame(problem=chosen, rows=())

    sku_to_category = {product.sku: product.category_code for product in dataset.catalog.products}
    stores = [store.code for store in dataset.catalog.stores]
    categories = sorted({product.category_code for product in dataset.catalog.products})

    totals: dict[tuple[str, str, date], float] = defaultdict(float)
    for sale in dataset.sales:
        category = sku_to_category.get(sale.product_sku)
        if category is None:
            continue
        week = iso_week_start(sale.business_date)
        if week not in week_set:
            continue
        totals[(sale.store_code, category, week)] += float(sale.units_sold)

    rows = [
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
    return ForecastFrame(problem=chosen, rows=tuple(rows))


def frame_to_rows(frame: ForecastFrame) -> Iterable[tuple[str, ...]]:
    for row in frame.rows:
        yield (
            row.store_code,
            row.category_code,
            row.period_start.isoformat(),
            _format_target(row.target),
        )


def _format_target(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return repr(value)


def _history_span(dataset: Dataset) -> tuple[date | None, date | None]:
    dates: list[date] = [row.business_date for row in dataset.sales]
    if not dates:
        dates = [day.business_date for day in dataset.calendar]
    if not dates:
        return None, None
    return min(dates), max(dates)


def require_periods(frame: ForecastFrame, minimum: int, *, what: str) -> Sequence[date]:
    periods = frame.periods()
    if len(periods) < minimum:
        raise ValueError(
            f"{what} needs at least {minimum} complete weeks; the frame has {len(periods)}"
        )
    return periods
