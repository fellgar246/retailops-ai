from datetime import date

import pytest

from retailops_api.forecasting.split import split_holdout, split_temporal
from tests.forecast_support import series_frame, week


def test_temporal_split_is_contiguous_and_ordered() -> None:
    frame = series_frame(list(range(12)))
    split = split_temporal(frame, train_end=week(5), validation_end=week(7))

    assert [row.period_start for row in split.train.rows] == [week(i) for i in range(6)]
    assert [row.period_start for row in split.validation.rows] == [week(6), week(7)]
    assert [row.period_start for row in split.test.rows] == [week(i) for i in range(8, 12)]
    assert split.train_end == week(5)
    assert split.validation_end == week(7)
    assert split.test_end == week(11)
    assert max(row.period_start for row in split.train.rows) <= split.train_end
    assert min(row.period_start for row in split.validation.rows) > split.train_end
    assert max(row.period_start for row in split.validation.rows) <= split.validation_end
    assert min(row.period_start for row in split.test.rows) > split.validation_end


def test_a_wednesday_cutoff_snaps_to_that_week_monday() -> None:
    frame = series_frame(list(range(6)))
    split = split_temporal(
        frame,
        train_end=date(2025, 1, 8),  # Wednesday of week 0
        validation_end=date(2025, 1, 17),  # Friday of week 1
    )

    assert split.train_end == week(0)
    assert split.validation_end == week(1)
    assert len(split.train.rows) == 1
    assert len(split.validation.rows) == 1


def test_validation_cannot_end_before_train() -> None:
    frame = series_frame(list(range(6)))
    with pytest.raises(ValueError, match="validation_end"):
        split_temporal(frame, train_end=week(3), validation_end=week(2))


def test_holdout_uses_the_last_weeks_and_leaves_train_history() -> None:
    frame = series_frame(list(range(20)))
    split = split_holdout(frame, validation_periods=4, test_periods=8)

    assert len(split.test.rows) == 8
    assert len(split.validation.rows) == 4
    assert len(split.train.rows) == 8
    assert split.train_end == week(7)
    assert split.validation_end == week(11)
    assert split.test_end == week(19)


def test_holdout_refuses_a_frame_that_cannot_leave_training_weeks() -> None:
    frame = series_frame(list(range(8)))
    with pytest.raises(ValueError, match="holdout split"):
        split_holdout(frame, validation_periods=4, test_periods=4)
