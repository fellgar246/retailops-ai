from datetime import date
from decimal import Decimal

from retailops_api.dataset.contract import (
    Catalog,
    CategoryRow,
    Dataset,
    ProductRow,
    SalesRow,
    StoreRow,
)
from retailops_api.dataset.snapshot import dataset_checksum
from retailops_api.forecasting.feature_contract import FeatureConfig
from retailops_api.forecasting.feature_panel import build_inference_rows, build_supervised_frame
from retailops_api.forecasting.features import (
    WeeklyObservables,
    build_observables,
    fit_identifier_maps,
)
from retailops_api.forecasting.frame import build_forecast_frame
from retailops_api.synthetic.config import GeneratorConfig
from retailops_api.synthetic.generate import generate_dataset
from tests.forecast_support import entity, series_frame, week


def test_supervised_frame_records_checksum_config_names_and_cutoffs() -> None:
    dataset = generate_dataset(
        GeneratorConfig.from_preset(
            "tiny",
            start_date=date(2025, 1, 6),
            end_date=date(2025, 6, 29),
        )
    )
    frame = build_forecast_frame(dataset)
    train_end = frame.periods()[-(4 + 4 + 1)]
    config = FeatureConfig(min_history_weeks=8)
    supervised = build_supervised_frame(
        frame,
        config=config,
        train_end=train_end,
        horizon=4,
        observables=build_observables(dataset, frame.periods()),
        catalog=dataset.catalog,
        dataset_checksum=dataset_checksum(dataset),
        source="synthetic:tiny",
        validation_end=frame.periods()[-5],
        test_end=frame.periods()[-1],
    )

    assert supervised.dataset_checksum == dataset_checksum(dataset)
    assert supervised.feature_names == config.feature_names()
    assert supervised.cutoff == train_end
    assert supervised.train_end == train_end
    assert supervised.source == "synthetic:tiny"
    assert supervised.rows
    assert all(row.as_of <= train_end for row in supervised.rows)
    assert all(row.period_start <= train_end for row in supervised.rows)
    assert all(row.target is not None for row in supervised.rows)
    assert all(len(row.values) == len(supervised.feature_names) for row in supervised.rows)


def test_inference_rows_do_not_need_the_target_week_to_exist() -> None:
    frame = series_frame([10.0] * 12)
    config = FeatureConfig(
        include_calendar=False,
        include_commercial_lags=False,
        include_identifiers=True,
        rolling_min_max=False,
        min_history_weeks=4,
    )
    supervised = build_supervised_frame(
        frame,
        config=config,
        train_end=week(7),
        horizon=4,
    )
    assert supervised.identifier_maps is not None
    rows = build_inference_rows(
        frame,
        cutoff=week(11),
        horizon=4,
        config=config,
        identifier_maps=supervised.identifier_maps,
    )

    assert [row.period_start for row in rows] == [week(12), week(13), week(14), week(15)]
    assert all(row.target is None for row in rows)
    assert all(row.as_of == week(11) for row in rows)


def test_commercial_lags_use_the_last_week_on_or_before_the_cutoff() -> None:
    sales = (
        _sale("ST-001", "SKU-0001", date(2025, 1, 6), price="2.0000", discount="0"),
        _sale("ST-001", "SKU-0001", date(2025, 1, 13), price="9.0000", discount="1"),
        _sale("ST-001", "SKU-0001", date(2025, 1, 19), price="9.0000", discount="1"),
    )
    dataset = _dataset(sales)
    frame = build_forecast_frame(dataset)
    observables = build_observables(dataset, frame.periods())
    by_week = {row.period_start: row for row in observables if row.store_code == "ST-001"}

    assert by_week[date(2025, 1, 6)].avg_price == 2.0
    assert by_week[date(2025, 1, 13)].avg_price == 9.0

    config = FeatureConfig(
        include_calendar=False,
        include_identifiers=False,
        rolling_min_max=False,
        lags=(1,),
        rolling_stats=("mean",),
        min_history_weeks=1,
    )
    supervised = build_supervised_frame(
        frame,
        config=config,
        train_end=date(2025, 1, 13),
        horizon=1,
        observables=observables,
        catalog=dataset.catalog,
    )
    row = next(item for item in supervised.rows if item.entity == entity())
    names = dict(zip(supervised.feature_names, row.values, strict=True))
    assert names["price_lag_1"] == 2.0


def test_poisoned_future_observables_are_not_read() -> None:
    observables = (
        WeeklyObservables("ST-001", "BEV-SOFT", week(0), 2.0, 0.0, 0.0, 5.0, 0.0),
        WeeklyObservables("ST-001", "BEV-SOFT", week(1), 999.0, 50.0, 1.0, 0.0, 1.0),
    )
    frame = series_frame([4.0, 5.0, 6.0])
    config = FeatureConfig(
        include_calendar=False,
        include_identifiers=False,
        rolling_min_max=False,
        lags=(1,),
        rolling_stats=("mean",),
        min_history_weeks=1,
    )
    rows = build_inference_rows(
        frame,
        cutoff=week(0),
        horizon=1,
        config=config,
        identifier_maps=fit_identifier_maps(frame),
        observables=observables,
    )
    names = dict(zip(config.feature_names(), rows[0].values, strict=True))
    assert names["price_lag_1"] == 2.0
    assert names["discount_lag_1"] == 0.0


def _sale(
    store: str,
    sku: str,
    day: date,
    *,
    price: str,
    discount: str,
) -> SalesRow:
    return SalesRow(
        store_code=store,
        product_sku=sku,
        business_date=day,
        units_sold=2,
        unit_price=Decimal(price),
        discount_amount=Decimal(discount),
        promotion=Decimal(discount) > 0,
        stock_on_hand=8,
    )


def _dataset(sales: tuple[SalesRow, ...]) -> Dataset:
    return Dataset(
        catalog=Catalog(
            categories=(CategoryRow("BEV-SOFT", "Soft Drinks"),),
            products=(ProductRow("SKU-0001", "Cola", "BEV-SOFT"),),
            suppliers=(),
            supplier_products=(),
            stores=(StoreRow("ST-001", "Centro", "Central", "flagship"),),
        ),
        sales=sales,
        calendar=(),
    )
