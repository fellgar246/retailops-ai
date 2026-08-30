"""Generated sales history varies for reasons a trivial forecast would miss."""

from collections import defaultdict
from datetime import date
from statistics import mean, pstdev

from retailops_api.synthetic.config import GeneratorConfig
from retailops_api.synthetic.generate import generate_dataset


def _tiny(**overrides: object) -> GeneratorConfig:
    return GeneratorConfig.from_preset("tiny", **overrides)


def test_the_same_seed_and_config_reproduce_every_sales_row() -> None:
    first = generate_dataset(_tiny())
    second = generate_dataset(_tiny())

    assert first.sales == second.sales


def test_every_store_product_day_has_a_row() -> None:
    dataset = generate_dataset(_tiny())
    expected = len(dataset.catalog.stores) * len(dataset.catalog.products) * len(dataset.calendar)

    assert len(dataset.sales) == expected


def test_weekend_sales_differ_from_weekday_sales() -> None:
    dataset = generate_dataset(_tiny())
    weekend = [row.units_sold for row in dataset.sales if row.business_date.weekday() >= 5]
    weekday = [row.units_sold for row in dataset.sales if row.business_date.weekday() < 5]

    assert weekend and weekday
    assert mean(weekend) != mean(weekday)


def test_products_are_not_equally_popular() -> None:
    dataset = generate_dataset(_tiny())
    by_sku: dict[str, int] = defaultdict(int)
    for row in dataset.sales:
        by_sku[row.product_sku] += row.units_sold

    totals = list(by_sku.values())
    assert max(totals) > min(totals)


def test_stores_are_not_interchangeable() -> None:
    dataset = generate_dataset(_tiny(store_count=3))
    by_store: dict[str, int] = defaultdict(int)
    for row in dataset.sales:
        by_store[row.store_code] += row.units_sold

    totals = list(by_store.values())
    assert max(totals) != min(totals)


def test_sales_are_not_a_constant_or_a_pure_trend() -> None:
    dataset = generate_dataset(_tiny())
    units = [row.units_sold for row in dataset.sales]

    assert pstdev(units) > 0
    # A series that is only "day index" would be perfectly explained by date
    # order; mixed store/product rows on the same day already break that, and
    # the residual noise keeps the same SKU from being a straight line.
    one_sku = [
        row.units_sold for row in dataset.sales if row.product_sku == dataset.sales[0].product_sku
    ]
    assert pstdev(one_sku) > 0


def test_promotions_change_price_and_are_present() -> None:
    dataset = generate_dataset(_tiny())
    promoted = [row for row in dataset.sales if row.promotion]
    regular = [row for row in dataset.sales if not row.promotion]

    assert promoted
    assert regular
    assert all(row.discount_amount > 0 for row in promoted)
    assert all(row.discount_amount == 0 for row in regular)


def test_stockouts_censor_sales() -> None:
    dataset = generate_dataset(_tiny())
    empty = [row for row in dataset.sales if row.stock_on_hand == 0 and row.units_sold == 0]
    moving = [row for row in dataset.sales if row.units_sold > 0]

    assert empty
    assert moving


def test_measures_never_go_negative() -> None:
    dataset = generate_dataset(_tiny())

    for row in dataset.sales:
        assert row.units_sold >= 0
        assert row.unit_price >= 0
        assert row.discount_amount >= 0
        assert row.stock_on_hand >= 0


def test_christmas_lifts_unconstrained_sales_relative_to_early_december() -> None:
    config = GeneratorConfig.from_preset(
        "tiny",
        start_date=date(2025, 12, 1),
        end_date=date(2025, 12, 31),
    )
    dataset = generate_dataset(config)
    peak = [
        row.units_sold
        for row in dataset.sales
        if date(2025, 12, 20) <= row.business_date <= date(2025, 12, 24)
    ]
    early = [
        row.units_sold
        for row in dataset.sales
        if date(2025, 12, 8) <= row.business_date <= date(2025, 12, 11)
    ]

    assert peak and early
    assert mean(peak) > mean(early)


def test_a_zero_promotion_probability_produces_no_promotions() -> None:
    dataset = generate_dataset(_tiny(promotion_probability=0.0))

    assert all(not row.promotion and row.discount_amount == 0 for row in dataset.sales)
