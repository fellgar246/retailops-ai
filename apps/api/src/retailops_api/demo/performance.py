"""Wall-clock samples for development-scale local steps.

Thresholds are wide: they catch a step that suddenly takes many times longer,
not a 10 % drift.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from retailops_api.dataset.contract import Dataset
from retailops_api.demo.procurement import create_demo_procurement
from retailops_api.demo.sales import generator_config, seed_and_ingest_sales
from retailops_api.forecasting.benchmark import DatasetSummary
from retailops_api.forecasting.booster import HistGBMTrainerConfig
from retailops_api.forecasting.feature_contract import FeatureConfig
from retailops_api.forecasting.frame import build_forecast_frame
from retailops_api.forecasting.registry import LocalModelRegistry
from retailops_api.forecasting.sources import dataset_span
from retailops_api.forecasting.train import TrainSettings, run_training
from retailops_api.review.cases import ReviewFilters
from retailops_api.review.queue import list_cases
from retailops_api.synthetic.generate import generate_dataset

THRESHOLDS_SECONDS = {
    "generate": 8.0,
    "ingest": 8.0,
    "train": 60.0,
    "reconcile": 4.0,
    "review_queue": 2.0,
}


@dataclass(frozen=True)
class StepTiming:
    name: str
    seconds: float
    limit: float

    @property
    def ok(self) -> bool:
        return self.seconds <= self.limit


def measure_local_steps(
    session: Session, output: Path, *, work: Path | None = None
) -> list[StepTiming]:
    """Time generate, ingest, a small training pass, match and the review queue."""

    work_dir = work or (output / "_timing")
    config = generator_config("tiny")
    generate_seconds = _timed(lambda: generate_dataset(config))
    ingested: list[Dataset] = []
    ingest_seconds = _timed(
        lambda: ingested.append(seed_and_ingest_sales(session, preset="tiny", output=output)[0])
    )
    train_seconds = _timed(lambda: _train_tiny(ingested[0], work_dir))
    reconcile_seconds = _timed(lambda: create_demo_procurement(session))
    queue_seconds = _timed(lambda: list_cases(session, ReviewFilters(), limit=50, offset=0))
    return [
        StepTiming("generate", generate_seconds, THRESHOLDS_SECONDS["generate"]),
        StepTiming("ingest", ingest_seconds, THRESHOLDS_SECONDS["ingest"]),
        StepTiming("train", train_seconds, THRESHOLDS_SECONDS["train"]),
        StepTiming("reconcile", reconcile_seconds, THRESHOLDS_SECONDS["reconcile"]),
        StepTiming("review_queue", queue_seconds, THRESHOLDS_SECONDS["review_queue"]),
    ]


def _train_tiny(dataset: Dataset, work_dir: Path) -> None:
    frame = build_forecast_frame(dataset)
    start, end = dataset_span(dataset)
    summary = DatasetSummary(
        source="local-timing",
        start_date=start,
        end_date=end,
        checksum=None,
        complete_weeks=len(frame.periods()),
        entity_count=len(frame.entities()),
        row_count=len(frame.rows),
    )
    run_training(
        dataset,
        frame,
        summary=summary,
        settings=TrainSettings(
            feature=FeatureConfig(min_history_weeks=8),
            trainer=HistGBMTrainerConfig(n_estimators=10, max_depth=3, min_samples_leaf=5),
            validation_periods=4,
            test_periods=4,
            model_name="local-timing",
        ),
        output_dir=work_dir / "train",
        registry=LocalModelRegistry(work_dir / "registry"),
    )


def _timed(action: Callable[[], object]) -> float:
    started = time.perf_counter()
    action()
    return time.perf_counter() - started
