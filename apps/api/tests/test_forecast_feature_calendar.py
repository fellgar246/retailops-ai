from datetime import date

import pytest

from retailops_api.forecasting.features import weekly_calendar_features
from retailops_api.synthetic.calendar import buen_fin_dates


def test_a_non_monday_is_rejected() -> None:
    with pytest.raises(ValueError, match="Monday"):
        weekly_calendar_features(date(2025, 1, 7))


def test_iso_year_boundary_week_is_week_one_of_the_next_year() -> None:
    # Monday 30 December 2024 is ISO 2025-W01.
    features = weekly_calendar_features(date(2024, 12, 30))

    assert features["iso_week"] == 1
    assert features["iso_year"] == 2025
    assert features["month"] == 12
    assert features["new_year_days"] == 2
    assert features["is_month_end_week"] == 1
    assert features["is_month_start_week"] == 1


def test_christmas_window_splits_across_two_weeks_in_2025() -> None:
    mid = weekly_calendar_features(date(2025, 12, 15))
    late = weekly_calendar_features(date(2025, 12, 22))

    assert mid["christmas_days"] == 2  # 20-21 December
    assert late["christmas_days"] == 4  # 22-25 December
    assert late["mean_demand_multiplier"] != mid["mean_demand_multiplier"]


def test_buen_fin_2025_falls_on_the_weekend_before_20_november() -> None:
    assert buen_fin_dates(2025) == frozenset(
        {date(2025, 11, 14), date(2025, 11, 15), date(2025, 11, 16), date(2025, 11, 17)}
    )
    leading = weekly_calendar_features(date(2025, 11, 10))
    trailing = weekly_calendar_features(date(2025, 11, 17))

    assert leading["buen_fin_days"] == 3
    assert trailing["buen_fin_days"] == 1


def test_a_week_that_contains_month_start_and_month_end() -> None:
    # Monday 31 March 2025 through 6 April: March ends and April begins.
    features = weekly_calendar_features(date(2025, 3, 31))

    assert features["is_month_end_week"] == 1
    assert features["is_month_start_week"] == 1
    assert features["month"] == 3
    assert features["week_of_month"] == 5


def test_mid_month_and_configured_holidays_are_counted() -> None:
    features = weekly_calendar_features(
        date(2025, 1, 13),
        holidays=(date(2025, 1, 15), date(2025, 2, 1)),
    )

    assert features["is_mid_month_week"] == 1
    assert features["holiday_days"] == 1
    assert features["christmas_days"] == 0
