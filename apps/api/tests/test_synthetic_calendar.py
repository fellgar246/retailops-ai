"""Retail calendar features: weekends, month boundaries and named events."""

from datetime import date

from retailops_api.synthetic.calendar import buen_fin_dates, calendar_day, last_day_of_month


def test_weekend_flags_saturday_and_sunday() -> None:
    saturday = calendar_day(date(2026, 3, 7))
    sunday = calendar_day(date(2026, 3, 8))
    wednesday = calendar_day(date(2026, 3, 4))

    assert saturday.is_weekend and saturday.weekday_name == "Sat"
    assert sunday.is_weekend and sunday.weekday_name == "Sun"
    assert not wednesday.is_weekend
    assert saturday.demand_multiplier > wednesday.demand_multiplier


def test_month_boundaries_are_flagged() -> None:
    first = calendar_day(date(2026, 3, 1))
    fifteenth = calendar_day(date(2026, 3, 15))
    last = calendar_day(date(2026, 3, 31))

    assert first.is_month_start
    assert fifteenth.is_mid_month
    assert last.is_month_end
    assert last_day_of_month(date(2026, 2, 1)) == date(2026, 2, 28)


def test_christmas_peak_is_stronger_than_an_ordinary_december_weekday() -> None:
    peak = calendar_day(date(2025, 12, 22))
    ordinary = calendar_day(date(2025, 12, 10))
    christmas_day = calendar_day(date(2025, 12, 25))

    assert peak.is_christmas
    assert peak.demand_multiplier > ordinary.demand_multiplier
    assert christmas_day.is_christmas
    assert christmas_day.demand_multiplier < ordinary.demand_multiplier


def test_new_year_is_quiet() -> None:
    new_year = calendar_day(date(2026, 1, 1))
    recovery = calendar_day(date(2026, 1, 2))
    ordinary = calendar_day(date(2026, 1, 7))

    assert new_year.is_new_year
    assert recovery.is_new_year
    assert new_year.demand_multiplier < recovery.demand_multiplier < ordinary.demand_multiplier


def test_buen_fin_is_the_weekend_before_revolution_day() -> None:
    # 20 November 2025 is a Thursday, so the preceding Friday-Monday is 14-17.
    window = buen_fin_dates(2025)
    assert window == {
        date(2025, 11, 14),
        date(2025, 11, 15),
        date(2025, 11, 16),
        date(2025, 11, 17),
    }

    event = calendar_day(date(2025, 11, 15))
    ordinary = calendar_day(date(2025, 11, 5))
    assert event.is_buen_fin
    assert event.demand_multiplier > ordinary.demand_multiplier


def test_configurable_holidays_are_marked_and_dampen_demand() -> None:
    holiday = date(2026, 5, 1)
    marked = calendar_day(holiday, holidays=(holiday,))
    unmarked = calendar_day(holiday)

    assert marked.is_holiday
    assert not unmarked.is_holiday
    assert marked.demand_multiplier < unmarked.demand_multiplier
