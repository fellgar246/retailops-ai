from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from retailops_api.dataset.contract import (
    Catalog,
    CategoryRow,
    Dataset,
    ProductRow,
    SalesRow,
    StoreRow,
)
from retailops_api.forecasting.frame import ForecastFrame, ForecastRow, build_forecast_frame
from retailops_api.forecasting.problem import WEEKLY_CATEGORY_STORE_DEMAND
from retailops_api.synthetic.config import GeneratorConfig
from retailops_api.synthetic.generate import generate_dataset
from tests.forecast_support import MONDAY, entity, series_frame, week


def _sale(
    store: str,
    sku: str,
    day: date,
    units: int,
) -> SalesRow:
    return SalesRow(
        store_code=store,
        product_sku=sku,
        business_date=day,
        units_sold=units,
        unit_price=Decimal("1.0000"),
        discount_amount=Decimal("0"),
        promotion=False,
        stock_on_hand=10,
    )


def _dataset(sales: tuple[SalesRow, ...]) -> Dataset:
    return Dataset(
        catalog=Catalog(
            categories=(
                CategoryRow("BEV-SOFT", "Soft Drinks"),
                CategoryRow("SNACK-CHIPS", "Chips"),
            ),
            products=(
                ProductRow("SKU-0001", "Cola", "BEV-SOFT"),
                ProductRow("SKU-0002", "Cola Zero", "BEV-SOFT"),
                ProductRow("SKU-0003", "Chips", "SNACK-CHIPS"),
            ),
            suppliers=(),
            supplier_products=(),
            stores=(
                StoreRow("ST-001", "Centro", "Central", "flagship"),
                StoreRow("ST-002", "Norte", "North", "supermarket"),
            ),
        ),
        sales=sales,
        calendar=(),
    )


def test_daily_units_sum_to_the_store_category_week() -> None:
    # Two complete weeks: 6-12 and 13-19 Jan 2025.
    sales = (
        _sale("ST-001", "SKU-0001", date(2025, 1, 6), 3),
        _sale("ST-001", "SKU-0002", date(2025, 1, 7), 5),
        _sale("ST-001", "SKU-0003", date(2025, 1, 8), 2),
        _sale("ST-002", "SKU-0001", date(2025, 1, 6), 1),
        _sale("ST-001", "SKU-0001", date(2025, 1, 19), 0),
    )
    frame = build_forecast_frame(_dataset(sales))

    assert frame.periods() == (date(2025, 1, 6), date(2025, 1, 13))
    assert frame.target_at(entity(), date(2025, 1, 6)) == 8.0
    assert frame.target_at(entity("ST-001", "SNACK-CHIPS"), date(2025, 1, 6)) == 2.0
    assert frame.target_at(entity("ST-002", "BEV-SOFT"), date(2025, 1, 6)) == 1.0
    assert frame.target_at(entity("ST-002", "SNACK-CHIPS"), date(2025, 1, 6)) == 0.0
    assert frame.target_at(entity(), date(2025, 1, 13)) == 0.0


def test_incomplete_edge_weeks_are_dropped() -> None:
    # Wednesday 1 Jan through Sunday 12 Jan: only the week of 6 Jan is complete.
    sales = (
        _sale("ST-001", "SKU-0001", date(2025, 1, 1), 9),
        _sale("ST-001", "SKU-0001", date(2025, 1, 8), 4),
        _sale("ST-001", "SKU-0001", date(2025, 1, 12), 0),
    )
    frame = build_forecast_frame(_dataset(sales))

    assert frame.periods() == (date(2025, 1, 6),)
    assert frame.target_at(entity(), date(2025, 1, 6)) == 4.0
    assert date(2024, 12, 30) not in frame.periods()


def test_history_window_keeps_only_the_trailing_weeks() -> None:
    problem = replace(WEEKLY_CATEGORY_STORE_DEMAND, history_periods=1)
    sales = (
        _sale("ST-001", "SKU-0001", date(2025, 1, 6), 3),
        _sale("ST-001", "SKU-0001", date(2025, 1, 13), 7),
        _sale("ST-001", "SKU-0001", date(2025, 1, 19), 0),
    )
    frame = build_forecast_frame(_dataset(sales), problem)

    assert frame.periods() == (date(2025, 1, 13),)
    assert frame.target_at(entity(), date(2025, 1, 13)) == 7.0


def test_duplicate_rows_are_rejected() -> None:
    row = ForecastRow("ST-001", "BEV-SOFT", MONDAY, 1.0)
    with pytest.raises(ValueError, match="duplicate"):
        ForecastFrame(problem=WEEKLY_CATEGORY_STORE_DEMAND, rows=(row, row))


def test_up_to_is_inclusive_and_after_is_strict() -> None:
    frame = series_frame([1, 2, 3, 4])
    cutoff = week(1)

    assert [row.target for row in frame.up_to(cutoff).rows] == [1, 2]
    assert [row.target for row in frame.after(cutoff).rows] == [3, 4]


def test_a_generated_year_builds_a_balanced_panel() -> None:
    dataset = generate_dataset(
        GeneratorConfig.from_preset(
            "tiny",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 3, 30),
        )
    )
    frame = build_forecast_frame(dataset)
    stores = {store.code for store in dataset.catalog.stores}
    categories = {product.category_code for product in dataset.catalog.products}

    assert len(frame.entities()) == len(stores) * len(categories)
    assert len(frame.rows) == len(frame.entities()) * len(frame.periods())
    assert frame.periods()[0] == date(2025, 1, 6)
