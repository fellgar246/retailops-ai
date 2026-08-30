"""Time-based train / validation / test cuts.

Time-series rows are never shuffled and never drawn at random. A later week
cannot appear in an earlier split: train ends at ``train_end``, validation
covers weeks after that through ``validation_end``, and test is everything
after ``validation_end``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from retailops_api.forecasting.frame import ForecastFrame, require_periods
from retailops_api.forecasting.problem import DEFAULT_TEST_PERIODS, DEFAULT_VALIDATION_PERIODS
from retailops_api.forecasting.weeks import iso_week_start


@dataclass(frozen=True)
class TemporalSplit:
    """Three contiguous, time-ordered slices of one frame.

    ``train_end`` and ``validation_end`` are the last ``period_start`` included
    in those slices. ``test_end`` is the last week in the test slice (or
    ``None`` when the test slice is empty).
    """

    train: ForecastFrame
    validation: ForecastFrame
    test: ForecastFrame
    train_end: date
    validation_end: date
    test_end: date | None


def split_temporal(
    frame: ForecastFrame,
    *,
    train_end: date,
    validation_end: date,
) -> TemporalSplit:
    """Cut the frame at two inclusive week dates.

    ``train_end`` and ``validation_end`` are snapped to the Monday of the week
    that contains them. Validation weeks are those with
    ``train_end < period_start <= validation_end``. Test weeks are those with
    ``period_start > validation_end``.
    """
    train_cutoff = iso_week_start(train_end)
    validation_cutoff = iso_week_start(validation_end)
    if validation_cutoff < train_cutoff:
        raise ValueError("validation_end must be on or after train_end")

    train = frame.up_to(train_cutoff)
    validation = frame.between(train_cutoff, validation_cutoff)
    test = frame.after(validation_cutoff)
    test_end = test.periods()[-1] if test.periods() else None
    return TemporalSplit(
        train=train,
        validation=validation,
        test=test,
        train_end=train_cutoff,
        validation_end=validation_cutoff,
        test_end=test_end,
    )


def split_holdout(
    frame: ForecastFrame,
    *,
    validation_periods: int = DEFAULT_VALIDATION_PERIODS,
    test_periods: int = DEFAULT_TEST_PERIODS,
) -> TemporalSplit:
    """Last ``test_periods`` weeks are test; the ``validation_periods`` before that are validation.

    The remaining leading weeks are train. Raises if the frame is too short to
    leave at least one training week.
    """
    if validation_periods < 1 or test_periods < 1:
        raise ValueError("validation_periods and test_periods must be at least 1")
    periods = require_periods(
        frame,
        validation_periods + test_periods + 1,
        what="a holdout split",
    )
    train_end = periods[-(test_periods + validation_periods + 1)]
    validation_end = periods[-(test_periods + 1)]
    return split_temporal(frame, train_end=train_end, validation_end=validation_end)
