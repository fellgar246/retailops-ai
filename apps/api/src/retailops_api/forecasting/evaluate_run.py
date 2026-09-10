"""Evaluate the demand baselines over persisted history.

This is what an operator triggers. It scores the panel the platform already
holds and persists the runs, without writing a report to disk: a worker has no
durable filesystem, and the console reads runs from the database anyway.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from retailops_api.forecasting.benchmark import (
    BenchmarkConfig,
    DatasetSummary,
    run_benchmark,
)
from retailops_api.forecasting.database_frame import build_frame_from_database
from retailops_api.forecasting.persist import persist_backtest
from retailops_api.forecasting.problem import (
    DEFAULT_HORIZON_WEEKS,
    DEFAULT_MIN_TRAIN_PERIODS,
)

#: An operator-triggered evaluation must not occupy a worker indefinitely.
MAX_HORIZON_WEEKS = 26
MAX_MIN_TRAIN_PERIODS = 260


@dataclass(frozen=True)
class EvaluationSummary:
    run_id: int
    model_id: str
    prediction_count: int
    complete_weeks: int
    backtest_id: str


def evaluate_from_database(
    session: Session,
    *,
    horizon: int = DEFAULT_HORIZON_WEEKS,
    min_train_periods: int = DEFAULT_MIN_TRAIN_PERIODS,
    generated_at: datetime | None = None,
) -> EvaluationSummary:
    if not 1 <= horizon <= MAX_HORIZON_WEEKS:
        raise ValueError(f"horizon must be between 1 and {MAX_HORIZON_WEEKS}")
    if not 1 <= min_train_periods <= MAX_MIN_TRAIN_PERIODS:
        raise ValueError(f"min_train_periods must be between 1 and {MAX_MIN_TRAIN_PERIODS}")

    frame = build_frame_from_database(session)
    periods = frame.periods()
    summary = DatasetSummary(
        source="database",
        start_date=periods[0] if periods else None,
        end_date=periods[-1] if periods else None,
        checksum="",
        complete_weeks=len(periods),
        entity_count=len(frame.entities()),
        row_count=len(frame.rows),
    )
    report = run_benchmark(
        frame,
        dataset=summary,
        config=BenchmarkConfig(horizon=horizon, min_train_periods=min_train_periods),
    )

    moment = generated_at or datetime.now(UTC)
    group = uuid.uuid4().hex
    runs = []
    for result in report.results:
        runs.extend(
            persist_backtest(
                session,
                result,
                generated_at=moment,
                problem_id=report.holdout.train.problem.id,
                run_metadata={"source": summary.source, "trigger": "operator"},
                backtest_id=group,
            )
        )
    if not runs:
        raise ValueError("the history is too short to evaluate")

    latest = runs[-1]
    return EvaluationSummary(
        run_id=latest.id,
        model_id=latest.model_id,
        prediction_count=sum(len(run.predictions) for run in runs),
        complete_weeks=len(periods),
        backtest_id=group,
    )
