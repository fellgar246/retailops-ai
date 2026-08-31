"""Persist one origin forecast so the operations console has a demand run."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from retailops_api.dataset.contract import Dataset
from retailops_api.domain.models import ForecastRun
from retailops_api.forecasting.frame import build_forecast_frame
from retailops_api.forecasting.metrics import score_points
from retailops_api.forecasting.models import NaiveForecaster
from retailops_api.forecasting.persist import persist_run
from retailops_api.forecasting.problem import DEFAULT_HORIZON_WEEKS, WEEKLY_CATEGORY_STORE_DEMAND

DEMO_FORECAST_SOURCE = "local-demo"


def persist_demo_forecast(
    session: Session,
    dataset: Dataset,
    *,
    generated_at: datetime | None = None,
    horizon: int = DEFAULT_HORIZON_WEEKS,
) -> ForecastRun | None:
    """Write a naive run at the last origin that still has a full horizon.

    Re-running is a no-op when a local-demo run already exists.
    """

    existing = _existing_demo_run(session)
    if existing is not None:
        return existing

    frame = build_forecast_frame(dataset)
    periods = frame.periods()
    if len(periods) <= horizon:
        return None
    cutoff = periods[-(horizon + 1)]
    actuals = {
        (row.store_code, row.category_code, row.period_start): row.target for row in frame.rows
    }
    predicted = NaiveForecaster().predict(frame, cutoff=cutoff, horizon=horizon)
    points = [
        point.with_actual(actuals.get((point.store_code, point.category_code, point.period_start)))
        for point in predicted
    ]
    scored = [point for point in points if point.actual is not None]
    metrics = score_points(scored).to_dict() if scored else None
    return persist_run(
        session,
        model_id="naive",
        generated_at=generated_at or datetime.now(UTC),
        cutoff=cutoff,
        horizon=horizon,
        problem_id=WEEKLY_CATEGORY_STORE_DEMAND.id,
        predictions=points,
        run_metadata={
            "source": DEMO_FORECAST_SOURCE,
            "overall_metrics": metrics,
        },
    )


def _existing_demo_run(session: Session) -> ForecastRun | None:
    for run in session.scalars(select(ForecastRun)).all():
        metadata = run.run_metadata or {}
        if metadata.get("source") == DEMO_FORECAST_SOURCE:
            return run
    return None
