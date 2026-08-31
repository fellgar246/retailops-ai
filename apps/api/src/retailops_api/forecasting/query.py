"""Read forecast runs for the operations API. Does not commit."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from retailops_api.domain.models import ForecastPrediction, ForecastRun
from retailops_api.forecasting.metrics import score_pairs


def list_runs(session: Session, *, limit: int, offset: int) -> dict[str, Any]:
    total = session.scalar(select(func.count()).select_from(ForecastRun)) or 0
    runs = session.scalars(
        select(ForecastRun)
        .order_by(ForecastRun.generated_at.desc(), ForecastRun.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    counts = _prediction_counts(session, [run.id for run in runs])
    return {
        "items": [run_summary(run, prediction_count=counts.get(run.id, 0)) for run in runs],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_run(session: Session, run_id: int) -> dict[str, Any] | None:
    run = session.get(ForecastRun, run_id, options=(selectinload(ForecastRun.predictions),))
    if run is None:
        return None
    return run_detail(run)


def run_summary(run: ForecastRun, *, prediction_count: int | None = None) -> dict[str, Any]:
    metadata = run.run_metadata or {}
    metrics = _metrics_from_metadata(metadata)
    count = prediction_count
    if count is None:
        count = len(run.predictions)
    status = "evaluated" if metrics is not None else "projected"
    return {
        "id": run.id,
        "model_id": run.model_id,
        "model_version": _model_version(metadata),
        "generated_at": run.generated_at.isoformat(),
        "cutoff": run.cutoff.isoformat(),
        "horizon": run.horizon,
        "problem_id": run.problem_id,
        "status": status,
        "prediction_count": count,
        "metrics": metrics,
    }


def run_detail(run: ForecastRun) -> dict[str, Any]:
    predictions = sorted(
        run.predictions,
        key=lambda item: (item.store_code, item.category_code, item.step, item.id),
    )
    computed = _metrics_from_predictions(predictions)
    payload = run_summary(run, prediction_count=len(predictions))
    if payload["metrics"] is None:
        payload["metrics"] = computed
        payload["status"] = "evaluated" if computed is not None else "projected"
    payload["run_metadata"] = run.run_metadata
    payload["predictions"] = [
        {
            "store_code": item.store_code,
            "category_code": item.category_code,
            "period_start": item.period_start.isoformat(),
            "step": item.step,
            "predicted": item.predicted,
            "actual": item.actual,
        }
        for item in predictions
    ]
    return payload


def _prediction_counts(session: Session, run_ids: Sequence[int]) -> dict[int, int]:
    if not run_ids:
        return {}
    rows = session.execute(
        select(ForecastPrediction.forecast_run_id, func.count())
        .where(ForecastPrediction.forecast_run_id.in_(run_ids))
        .group_by(ForecastPrediction.forecast_run_id)
    ).all()
    return {int(run_id): int(count) for run_id, count in rows}


def _metrics_from_metadata(metadata: dict[str, Any]) -> dict[str, float] | None:
    for key in ("overall_metrics", "fold_metrics"):
        raw = metadata.get(key)
        if isinstance(raw, dict) and {"wape", "bias"} <= set(raw):
            return {
                name: float(raw[name]) for name in ("mae", "rmse", "wape", "bias") if name in raw
            }
    return None


def _metrics_from_predictions(predictions: Sequence[ForecastPrediction]) -> dict[str, float] | None:
    pairs = [(item.actual, item.predicted) for item in predictions if item.actual is not None]
    if not pairs:
        return None
    return score_pairs(pairs).to_dict()


def _model_version(metadata: dict[str, Any]) -> str | None:
    for key in ("model_version", "version", "registry_version"):
        value = metadata.get(key)
        if value is not None and str(value):
            return str(value)
    return None
