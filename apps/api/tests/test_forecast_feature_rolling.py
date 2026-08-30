from datetime import date

from retailops_api.forecasting.features import rolling_values
from tests.forecast_support import week


def _series(values: list[float]) -> list[tuple[date, float]]:
    return [(week(index), value) for index, value in enumerate(values)]


def test_rolling_shifts_the_target_week_out_of_the_window() -> None:
    # Weeks 0-3 are 1,2,3,4. Target is week 3; the window must be 1,2,3 not 2,3,4.
    series = _series([1.0, 2.0, 3.0, 4.0])
    values = rolling_values(
        series,
        period_start=week(3),
        cutoff=week(3),
        window=3,
        stats=("mean", "median"),
        include_min_max=True,
    )

    assert values["roll_mean_3"] == 2.0
    assert values["roll_median_3"] == 2.0
    assert values["roll_min_3"] == 1.0
    assert values["roll_max_3"] == 3.0


def test_rolling_ignores_weeks_after_the_cutoff() -> None:
    series = _series([10.0] * 8 + [999.0] * 4)
    values = rolling_values(
        series,
        period_start=week(8),
        cutoff=week(7),
        window=4,
        stats=("mean", "std"),
        include_min_max=True,
    )

    assert values["roll_mean_4"] == 10.0
    assert values["roll_std_4"] == 0.0
    assert values["roll_max_4"] == 10.0
    assert values["roll_min_4"] == 10.0


def test_rolling_on_an_empty_history_is_zero() -> None:
    values = rolling_values(
        (),
        period_start=week(0),
        cutoff=week(0),
        window=4,
        stats=("mean", "median", "std"),
        include_min_max=True,
    )

    assert values == {
        "roll_mean_4": 0.0,
        "roll_median_4": 0.0,
        "roll_std_4": 0.0,
        "roll_min_4": 0.0,
        "roll_max_4": 0.0,
    }


def test_a_single_point_has_zero_std() -> None:
    values = rolling_values(
        [(week(0), 5.0)],
        period_start=week(1),
        cutoff=week(0),
        window=4,
        stats=("std",),
        include_min_max=False,
    )

    assert values["roll_std_4"] == 0.0
