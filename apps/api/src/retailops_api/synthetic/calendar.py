"""Deterministic retail-calendar features and demand multipliers.

The flags on each day are meant to be reused as modelling features: a
forecasting job can read ``calendar.csv`` rather than re-deriving weekends,
month boundaries or named events.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from datetime import date, timedelta

from retailops_api.dataset.contract import WEEKDAY_NAMES, CalendarDay
from retailops_api.synthetic.config import GeneratorConfig

# Weekday multipliers, Monday first. Weekends lift demand; Monday is quietest.
_WEEKDAY_MULTIPLIER = (0.85, 0.90, 0.95, 1.00, 1.15, 1.30, 1.10)

_MONTH_START_MULTIPLIER = 1.12
_MID_MONTH_MULTIPLIER = 1.15
_MONTH_END_MULTIPLIER = 1.18

# Named shopping / closure windows. These replace the weekday pattern rather
# than stacking on it, so a Christmas Saturday does not become 1.55 * 1.30.
_CHRISTMAS_PEAK_MULTIPLIER = 1.55  # 20-24 December
_CHRISTMAS_DAY_MULTIPLIER = 0.45  # 25 December
_NEW_YEAR_DAY_MULTIPLIER = 0.40  # 1 January
_NEW_YEAR_RECOVERY_MULTIPLIER = 0.70  # 2 January
_BUEN_FIN_MULTIPLIER = 1.70
_HOLIDAY_MULTIPLIER = 0.75


def iter_dates(start: date, end: date) -> Iterator[date]:
    """Yield every calendar day from ``start`` through ``end`` inclusive."""
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def last_day_of_month(day: date) -> date:
    if day.month == 12:
        return date(day.year, 12, 31)
    return date(day.year, day.month + 1, 1) - timedelta(days=1)


def buen_fin_dates(year: int) -> frozenset[date]:
    """Friday through Monday of the weekend immediately before 20 November.

    Revolution Day is 20 November; the shopping weekend that precedes it is
    the window used here so the dates stay deterministic from the year alone.
    """
    revolution = date(year, 11, 20)
    days_since_friday = (revolution.weekday() - 4) % 7
    if days_since_friday == 0:
        days_since_friday = 7
    friday = revolution - timedelta(days=days_since_friday)
    return frozenset(friday + timedelta(days=offset) for offset in range(4))


def calendar_day(day: date, holidays: Iterable[date] = ()) -> CalendarDay:
    """Build the feature row and demand multiplier for one trading day."""
    holiday_set = frozenset(holidays)
    weekday = day.weekday()
    month_end = last_day_of_month(day)
    is_weekend = weekday >= 5
    is_month_start = day.day == 1
    is_month_end = day == month_end
    is_mid_month = day.day == 15
    is_christmas = day.month == 12 and 20 <= day.day <= 25
    is_new_year = day.month == 1 and day.day in {1, 2}
    is_buen_fin = day in buen_fin_dates(day.year)
    is_holiday = day in holiday_set

    return CalendarDay(
        business_date=day,
        weekday=weekday,
        weekday_name=WEEKDAY_NAMES[weekday],
        is_weekend=is_weekend,
        is_month_start=is_month_start,
        is_month_end=is_month_end,
        is_mid_month=is_mid_month,
        is_christmas=is_christmas,
        is_new_year=is_new_year,
        is_buen_fin=is_buen_fin,
        is_holiday=is_holiday,
        demand_multiplier=round(
            _demand_multiplier(
                day,
                weekday=weekday,
                is_month_start=is_month_start,
                is_month_end=is_month_end,
                is_mid_month=is_mid_month,
                is_holiday=is_holiday,
            ),
            6,
        ),
    )


def build_calendar(config: GeneratorConfig) -> tuple[CalendarDay, ...]:
    return tuple(
        calendar_day(day, config.holidays) for day in iter_dates(config.start_date, config.end_date)
    )


def calendar_by_date(days: Sequence[CalendarDay]) -> dict[date, CalendarDay]:
    return {day.business_date: day for day in days}


def _demand_multiplier(
    day: date,
    *,
    weekday: int,
    is_month_start: bool,
    is_month_end: bool,
    is_mid_month: bool,
    is_holiday: bool,
) -> float:
    if day.month == 12 and 20 <= day.day <= 24:
        return _CHRISTMAS_PEAK_MULTIPLIER
    if day.month == 12 and day.day == 25:
        return _CHRISTMAS_DAY_MULTIPLIER
    if day.month == 1 and day.day == 1:
        return _NEW_YEAR_DAY_MULTIPLIER
    if day.month == 1 and day.day == 2:
        return _NEW_YEAR_RECOVERY_MULTIPLIER
    if day in buen_fin_dates(day.year):
        return _BUEN_FIN_MULTIPLIER
    if is_holiday:
        return _HOLIDAY_MULTIPLIER

    multiplier = _WEEKDAY_MULTIPLIER[weekday]
    if is_month_start:
        multiplier *= _MONTH_START_MULTIPLIER
    if is_mid_month:
        multiplier *= _MID_MONTH_MULTIPLIER
    if is_month_end:
        multiplier *= _MONTH_END_MULTIPLIER
    return multiplier
