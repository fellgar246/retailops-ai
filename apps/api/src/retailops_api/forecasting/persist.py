"""Write forecast runs and their predictions. Does not commit."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from retailops_api.domain.models import ForecastPrediction, ForecastRun
from retailops_api.forecasting.backtest import BacktestResult
from retailops_api.forecasting.models import ForecastPoint


def persist_run(
    session: Session,
    *,
    model_id: str,
    generated_at: datetime,
    cutoff: date,
    horizon: int,
    problem_id: str,
    predictions: Sequence[ForecastPoint],
    run_metadata: dict[str, Any] | None = None,
) -> ForecastRun:
    """Insert one run and its prediction rows. The caller owns the transaction."""
    run = ForecastRun(
        model_id=model_id,
        generated_at=generated_at,
        cutoff=cutoff,
        horizon=horizon,
        problem_id=problem_id,
        run_metadata=run_metadata,
    )
    session.add(run)
    session.flush()
    for point in predictions:
        session.add(
            ForecastPrediction(
                forecast_run_id=run.id,
                store_code=point.store_code,
                category_code=point.category_code,
                period_start=point.period_start,
                step=point.step,
                predicted=point.predicted,
                actual=point.actual,
            )
        )
    session.flush()
    return run


def persist_backtest(
    session: Session,
    result: BacktestResult,
    *,
    generated_at: datetime,
    problem_id: str,
    run_metadata: dict[str, Any] | None = None,
    backtest_id: str | None = None,
) -> list[ForecastRun]:
    """Persist each fold as its own run, grouped by a shared ``backtest_id``."""
    group = backtest_id or uuid.uuid4().hex
    runs: list[ForecastRun] = []
    for index, fold in enumerate(result.folds):
        metadata = {
            **(run_metadata or {}),
            "backtest_id": group,
            "fold_index": index,
            "fold_count": len(result.folds),
            "overall_metrics": result.overall.to_dict(),
            "fold_metrics": fold.metrics.to_dict(),
        }
        runs.append(
            persist_run(
                session,
                model_id=fold.model_id,
                generated_at=generated_at,
                cutoff=fold.cutoff,
                horizon=fold.horizon,
                problem_id=problem_id,
                predictions=fold.predictions,
                run_metadata=metadata,
            )
        )
    return runs
