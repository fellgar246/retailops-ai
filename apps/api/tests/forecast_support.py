"""Hand-built weekly frames so forecast tests do not need a generator."""

from datetime import date, timedelta

from retailops_api.forecasting.frame import ForecastEntity, ForecastFrame, ForecastRow
from retailops_api.forecasting.problem import WEEKLY_CATEGORY_STORE_DEMAND

MONDAY = date(2025, 1, 6)


def week(index: int, *, start: date = MONDAY) -> date:
    return start + timedelta(weeks=index)


def series_frame(
    values: list[float],
    *,
    store: str = "ST-001",
    category: str = "BEV-SOFT",
    start: date = MONDAY,
) -> ForecastFrame:
    rows = [
        ForecastRow(store, category, week(index, start=start), float(value))
        for index, value in enumerate(values)
    ]
    return ForecastFrame(problem=WEEKLY_CATEGORY_STORE_DEMAND, rows=tuple(rows))


def panel_frame(
    series: dict[tuple[str, str], list[float]],
    *,
    start: date = MONDAY,
) -> ForecastFrame:
    rows: list[ForecastRow] = []
    for (store, category), values in series.items():
        rows.extend(
            ForecastRow(store, category, week(index, start=start), float(value))
            for index, value in enumerate(values)
        )
    rows.sort(key=lambda row: (row.store_code, row.category_code, row.period_start))
    return ForecastFrame(problem=WEEKLY_CATEGORY_STORE_DEMAND, rows=tuple(rows))


def entity(store: str = "ST-001", category: str = "BEV-SOFT") -> ForecastEntity:
    return ForecastEntity(store, category)
