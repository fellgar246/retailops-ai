from retailops_api.forecasting.feature_contract import FeatureConfig
from retailops_api.forecasting.features import (
    IdentifierMaps,
    lag_value,
    row_feature_values,
    target_index,
)
from tests.forecast_support import entity, series_frame, week

_POISONED = [10.0] * 8 + [999.0] * 4
_CUTOFF = week(7)
_EMPTY_IDS = IdentifierMaps({}, {}, {}, {})


def test_lag_reads_only_the_historical_week() -> None:
    frame = series_frame([float(index) for index in range(12)])
    index = target_index(frame)

    assert lag_value(index, entity(), period_start=week(8), lag=1, cutoff=_CUTOFF) == 7.0
    assert lag_value(index, entity(), period_start=week(8), lag=4, cutoff=_CUTOFF) == 4.0


def test_lag_is_zero_when_the_lookback_is_after_the_cutoff() -> None:
    frame = series_frame(_POISONED)
    index = target_index(frame)

    # Horizon step 2 looks at week 9; lag 1 would be week 8 (poison) if leakage
    # were allowed. The cutoff forbids it.
    assert lag_value(index, entity(), period_start=week(9), lag=1, cutoff=_CUTOFF) == 0.0
    assert index[(entity().store_code, entity().category_code, week(8))] == 999.0


def test_missing_lags_are_zero_not_invented_from_the_future() -> None:
    frame = series_frame(_POISONED)
    index = target_index(frame)

    assert lag_value(index, entity(), period_start=week(8), lag=52, cutoff=_CUTOFF) == 0.0


def test_feature_vector_lags_ignore_poison_after_the_cutoff() -> None:
    frame = series_frame(_POISONED)
    config = FeatureConfig(
        lags=(1, 2, 4),
        include_calendar=False,
        include_commercial_lags=False,
        include_identifiers=False,
        rolling_min_max=False,
        rolling_stats=("mean",),
    )
    values = dict(
        zip(
            config.feature_names(),
            row_feature_values(
                entity=entity(),
                period_start=week(8),
                cutoff=_CUTOFF,
                horizon_step=1,
                config=config,
                targets=target_index(frame),
                series=[(row.period_start, row.target) for row in frame.rows],
                commercial={},
                identifiers=_EMPTY_IDS,
            ),
            strict=True,
        )
    )

    assert values["lag_1"] == 10.0
    assert values["lag_2"] == 10.0
    assert 999.0 not in values.values()
