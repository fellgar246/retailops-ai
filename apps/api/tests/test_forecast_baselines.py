from retailops_api.forecasting.models import (
    MovingAverageForecaster,
    NaiveForecaster,
    SeasonalNaiveForecaster,
)
from tests.forecast_support import entity, panel_frame, series_frame, week

# Weeks 0-7 are history (10). Weeks 8-11 are poison (999) that a leaky model
# would copy into its forecast.
_POISONED = [10.0] * 8 + [999.0] * 4
_CUTOFF = week(7)
_HORIZON = 4


def _by_step(points: tuple[object, ...]) -> dict[int, float]:
    from retailops_api.forecasting.models import ForecastPoint

    return {point.step: point.predicted for point in points if isinstance(point, ForecastPoint)}


def test_naive_repeats_the_last_observed_week() -> None:
    frame = series_frame(_POISONED)
    points = NaiveForecaster().predict(frame, cutoff=_CUTOFF, horizon=_HORIZON)

    assert _by_step(points) == {1: 10.0, 2: 10.0, 3: 10.0, 4: 10.0}
    assert [point.period_start for point in points] == [week(8), week(9), week(10), week(11)]


def test_naive_on_the_filtered_frame_matches_the_full_frame() -> None:
    frame = series_frame(_POISONED)
    model = NaiveForecaster()

    assert model.predict(frame, cutoff=_CUTOFF, horizon=_HORIZON) == model.predict(
        frame.up_to(_CUTOFF), cutoff=_CUTOFF, horizon=_HORIZON
    )


def test_seasonal_naive_uses_the_lagged_week_when_it_exists() -> None:
    # 12 weeks, values equal to the week index. Lag 4 at cutoff week 7:
    # step 1 → week 8 looks back to week 4 (value 4), not poison week 8.
    frame = series_frame([float(index) for index in range(12)])
    points = SeasonalNaiveForecaster(seasonal_lag=4).predict(
        frame, cutoff=_CUTOFF, horizon=_HORIZON
    )

    assert _by_step(points) == {1: 4.0, 2: 5.0, 3: 6.0, 4: 7.0}


def test_seasonal_naive_falls_back_to_the_last_week_when_the_lag_is_missing() -> None:
    frame = series_frame(_POISONED)
    points = SeasonalNaiveForecaster(seasonal_lag=52).predict(
        frame, cutoff=_CUTOFF, horizon=_HORIZON
    )

    assert _by_step(points) == {1: 10.0, 2: 10.0, 3: 10.0, 4: 10.0}


def test_seasonal_naive_does_not_read_a_lookback_after_the_cutoff() -> None:
    # Lag 1, step 2 would look at week 8 if leakage were allowed.
    frame = series_frame(_POISONED)
    points = SeasonalNaiveForecaster(seasonal_lag=1).predict(
        frame, cutoff=_CUTOFF, horizon=_HORIZON
    )

    assert points[0].predicted == 10.0  # week 8 looks at week 7
    assert points[1].predicted == 10.0  # week 9 would look at week 8; fallback


def test_moving_average_uses_only_the_trailing_window_before_cutoff() -> None:
    frame = series_frame([1, 2, 3, 4, 5, 6, 7, 8] + [999.0] * 4)
    points = MovingAverageForecaster(window=4).predict(frame, cutoff=_CUTOFF, horizon=_HORIZON)

    assert _by_step(points) == {1: 6.5, 2: 6.5, 3: 6.5, 4: 6.5}


def test_moving_average_shortens_the_window_when_history_is_thin() -> None:
    frame = series_frame([4.0, 6.0])
    points = MovingAverageForecaster(window=4).predict(frame, cutoff=week(1), horizon=2)

    assert _by_step(points) == {1: 5.0, 2: 5.0}


def test_each_entity_is_forecast_from_its_own_history() -> None:
    frame = panel_frame(
        {
            ("ST-001", "BEV-SOFT"): [10.0, 10.0, 10.0, 999.0],
            ("ST-002", "SNACK-CHIPS"): [3.0, 3.0, 3.0, 999.0],
        }
    )
    points = NaiveForecaster().predict(frame, cutoff=week(2), horizon=1)
    by_entity = {(point.store_code, point.category_code): point.predicted for point in points}

    assert by_entity[("ST-001", "BEV-SOFT")] == 10.0
    assert by_entity[("ST-002", "SNACK-CHIPS")] == 3.0
    assert entity("ST-003") not in {point.entity for point in points}


def test_baselines_ignore_future_targets_on_the_full_frame() -> None:
    frame = series_frame(_POISONED)
    filtered = frame.up_to(_CUTOFF)
    models = (
        NaiveForecaster(),
        SeasonalNaiveForecaster(seasonal_lag=4),
        MovingAverageForecaster(window=4),
    )
    for model in models:
        assert model.predict(frame, cutoff=_CUTOFF, horizon=_HORIZON) == model.predict(
            filtered, cutoff=_CUTOFF, horizon=_HORIZON
        )
