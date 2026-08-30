"""ISO week helpers for the weekly demand frame.

Weeks start on Monday, matching ``datetime.date.weekday`` (Monday = 0) and
ISO-8601. ``period_start`` in the forecast frame is always that Monday.
"""

from __future__ import annotations

from datetime import date, timedelta


def iso_week_start(day: date) -> date:
    """Monday of the ISO week that contains ``day``."""
    return day - timedelta(days=day.weekday())


def add_weeks(day: date, weeks: int) -> date:
    return day + timedelta(weeks=weeks)


def iso_week_label(day: date) -> str:
    """``YYYY-Www`` for the ISO week containing ``day``."""
    iso = iso_week_start(day).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def complete_week_starts(start: date, end: date) -> tuple[date, ...]:
    """Mondays of ISO weeks whose Monday-Sunday range lies inside ``[start, end]``.

    A week that begins before ``start`` or ends after ``end`` is omitted so a
    partial week never enters the forecast target.
    """
    if end < start:
        raise ValueError("end must be on or after start")

    first = iso_week_start(start)
    if first < start:
        first = add_weeks(first, 1)

    last = iso_week_start(end)
    if add_weeks(last, 1) - timedelta(days=1) > end:
        last = add_weeks(last, -1)

    if first > last:
        return ()

    weeks: list[date] = []
    current = first
    while current <= last:
        weeks.append(current)
        current = add_weeks(current, 1)
    return tuple(weeks)
