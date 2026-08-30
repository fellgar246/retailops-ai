from datetime import date, timedelta

from retailops_api.forecasting.weeks import (
    add_weeks,
    complete_week_starts,
    iso_week_label,
    iso_week_start,
)


def test_iso_week_start_is_monday() -> None:
    assert iso_week_start(date(2025, 1, 1)) == date(2024, 12, 30)
    assert iso_week_start(date(2025, 1, 6)) == date(2025, 1, 6)
    assert iso_week_start(date(2025, 1, 12)) == date(2025, 1, 6)


def test_complete_weeks_drop_partial_edges() -> None:
    # 2025-01-01 is Wednesday; 2025-12-31 is Wednesday.
    weeks = complete_week_starts(date(2025, 1, 1), date(2025, 12, 31))

    assert weeks[0] == date(2025, 1, 6)
    assert weeks[-1] == date(2025, 12, 22)
    assert len(weeks) == 51
    assert add_weeks(weeks[-1], 1) - timedelta(days=1) == date(2025, 12, 28)
    assert iso_week_label(weeks[0]) == "2025-W02"


def test_a_range_shorter_than_one_week_has_no_complete_weeks() -> None:
    assert complete_week_starts(date(2025, 1, 6), date(2025, 1, 10)) == ()


def test_an_exact_monday_to_sunday_range_is_one_week() -> None:
    assert complete_week_starts(date(2025, 1, 6), date(2025, 1, 12)) == (date(2025, 1, 6),)
