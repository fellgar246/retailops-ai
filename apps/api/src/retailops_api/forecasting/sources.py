"""Load a portable dataset or generate a synthetic one for forecasting jobs."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from retailops_api.dataset.contract import Dataset
from retailops_api.dataset.snapshot import dataset_checksum, load_dataset
from retailops_api.dataset.validate import assert_valid
from retailops_api.forecasting.benchmark import DatasetSummary
from retailops_api.forecasting.frame import (
    FRAME_COLUMNS,
    ForecastFrame,
    build_forecast_frame,
    frame_to_rows,
)
from retailops_api.synthetic.config import GeneratorConfig
from retailops_api.synthetic.generate import generate_dataset

FRAME_FILE = "forecast_frame.csv"


def find_repo_root() -> Path:
    for candidate in (Path.cwd(), *Path.cwd().parents):
        if (candidate / "apps" / "api" / "pyproject.toml").exists():
            return candidate
    return Path.cwd()


def default_forecast_output() -> Path:
    return find_repo_root() / "data" / "forecasts"


def default_registry_root() -> Path:
    return find_repo_root() / "artifacts" / "models"


def load_forecast_dataset(
    *,
    input_path: Path | None,
    preset: str,
    seed: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    source: str | None = None,
) -> tuple[Dataset, DatasetSummary, ForecastFrame]:
    if input_path is not None:
        dataset = load_dataset(input_path)
        assert_valid(dataset)
        label = source or f"file:{input_path}"
    else:
        config = _generator_config(preset, seed=seed, start_date=start_date, end_date=end_date)
        dataset = generate_dataset(config)
        assert_valid(dataset)
        label = source or f"synthetic:{config.preset or 'custom'}"
    start, end = dataset_span(dataset)
    frame = build_forecast_frame(dataset)
    summary = DatasetSummary(
        source=label,
        start_date=start,
        end_date=end,
        checksum=dataset_checksum(dataset),
        complete_weeks=len(frame.periods()),
        entity_count=len(frame.entities()),
        row_count=len(frame.rows),
    )
    return dataset, summary, frame


def write_frame_csv(frame: ForecastFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(FRAME_COLUMNS)
        writer.writerows(frame_to_rows(frame))


def dataset_span(dataset: Dataset) -> tuple[date | None, date | None]:
    dates = [row.business_date for row in dataset.sales]
    if not dates:
        dates = [day.business_date for day in dataset.calendar]
    if not dates:
        return None, None
    return min(dates), max(dates)


def _generator_config(
    preset: str,
    *,
    seed: int | None,
    start_date: date | None,
    end_date: date | None,
) -> GeneratorConfig:
    overrides: dict[str, object] = {}
    if seed is not None:
        overrides["seed"] = seed
    if start_date is not None:
        overrides["start_date"] = start_date
    if end_date is not None:
        overrides["end_date"] = end_date
    return GeneratorConfig.from_preset(preset, **overrides)
