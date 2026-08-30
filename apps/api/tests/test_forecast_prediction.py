from datetime import UTC, date, datetime
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from retailops_api.domain.models import ForecastPrediction, ForecastRun

GENERATED = datetime(2026, 8, 30, 13, 32, tzinfo=UTC)


@pytest.fixture
def run(session: Session) -> ForecastRun:
    record = ForecastRun(
        model_id="naive",
        generated_at=GENERATED,
        cutoff=date(2025, 6, 2),
        horizon=4,
        problem_id="weekly_category_store_demand",
    )
    session.add(record)
    session.flush()
    return record


@pytest.fixture
def defaults(run: ForecastRun) -> dict[str, Any]:
    return {
        "forecast_run_id": run.id,
        "store_code": "ST-001",
        "category_code": "BEV-SOFT",
        "period_start": date(2025, 6, 9),
        "step": 1,
        "predicted": 10.0,
    }


def _add(session: Session, defaults: dict[str, Any], **overrides: Any) -> ForecastPrediction:
    row = ForecastPrediction(**{**defaults, **overrides})
    session.add(row)
    session.flush()
    return row


def test_a_prediction_can_carry_an_actual(session: Session, defaults: dict[str, Any]) -> None:
    row = _add(session, defaults, actual=8.5)
    session.refresh(row)

    assert row.predicted == 10.0
    assert row.actual == 8.5
    assert row.step == 1


def test_actual_may_be_absent(session: Session, defaults: dict[str, Any]) -> None:
    row = _add(session, defaults)
    session.expire_all()
    session.refresh(row)

    assert row.actual is None


def test_the_natural_key_is_unique(session: Session, defaults: dict[str, Any]) -> None:
    _add(session, defaults)
    with pytest.raises(IntegrityError):
        _add(session, defaults, step=2, predicted=11.0)


def test_the_same_week_may_appear_on_another_run(
    session: Session, defaults: dict[str, Any], run: ForecastRun
) -> None:
    _add(session, defaults)
    other = ForecastRun(
        model_id="moving_average",
        generated_at=GENERATED,
        cutoff=run.cutoff,
        horizon=4,
        problem_id=run.problem_id,
    )
    session.add(other)
    session.flush()
    _add(session, defaults, forecast_run_id=other.id)

    assert session.query(ForecastPrediction).count() == 2


def test_step_must_be_at_least_one(session: Session, defaults: dict[str, Any]) -> None:
    with pytest.raises(IntegrityError):
        _add(session, defaults, step=0)


def test_predicted_cannot_be_negative(session: Session, defaults: dict[str, Any]) -> None:
    with pytest.raises(IntegrityError):
        _add(session, defaults, predicted=-0.1)


def test_actual_cannot_be_negative(session: Session, defaults: dict[str, Any]) -> None:
    with pytest.raises(IntegrityError):
        _add(session, defaults, actual=-1.0)


def test_the_run_must_exist(session: Session, defaults: dict[str, Any]) -> None:
    with pytest.raises(IntegrityError):
        _add(session, defaults, forecast_run_id=999_999)
