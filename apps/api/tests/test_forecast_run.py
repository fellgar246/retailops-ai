from datetime import UTC, date, datetime
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from retailops_api.domain.models import ForecastPrediction, ForecastRun

CUTOFF = date(2025, 6, 2)
GENERATED = datetime(2026, 8, 30, 13, 32, tzinfo=UTC)


@pytest.fixture
def defaults() -> dict[str, Any]:
    return {
        "model_id": "naive",
        "generated_at": GENERATED,
        "cutoff": CUTOFF,
        "horizon": 4,
        "problem_id": "weekly_category_store_demand",
    }


def _add_run(session: Session, defaults: dict[str, Any], **overrides: Any) -> ForecastRun:
    run = ForecastRun(**{**defaults, **overrides})
    session.add(run)
    session.flush()
    return run


def test_a_run_records_the_model_origin_and_horizon(
    session: Session, defaults: dict[str, Any]
) -> None:
    run = _add_run(session, defaults)
    session.refresh(run)

    assert run.id is not None
    assert run.model_id == "naive"
    assert run.cutoff == CUTOFF
    assert run.horizon == 4
    assert run.generated_at.replace(tzinfo=None) == GENERATED.replace(tzinfo=None)
    assert run.created_at is not None


def test_run_metadata_round_trips(session: Session, defaults: dict[str, Any]) -> None:
    run = _add_run(session, defaults, run_metadata={"seasonal_lag": 52, "fold_index": 0})
    session.expire_all()
    session.refresh(run)

    assert run.run_metadata == {"seasonal_lag": 52, "fold_index": 0}


def test_horizon_must_be_at_least_one(session: Session, defaults: dict[str, Any]) -> None:
    with pytest.raises(IntegrityError):
        _add_run(session, defaults, horizon=0)


def test_deleting_a_run_removes_its_predictions(session: Session, defaults: dict[str, Any]) -> None:
    run = _add_run(session, defaults)
    session.add(
        ForecastPrediction(
            forecast_run_id=run.id,
            store_code="ST-001",
            category_code="BEV-SOFT",
            period_start=date(2025, 6, 9),
            step=1,
            predicted=10.0,
            actual=9.0,
        )
    )
    session.flush()

    session.delete(run)
    session.flush()

    assert session.query(ForecastPrediction).count() == 0
    assert session.query(ForecastRun).count() == 0
