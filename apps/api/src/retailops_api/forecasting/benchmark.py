"""Run every baseline on a frame and write a machine-readable report."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from retailops_api.forecasting.backtest import BacktestResult, walk_forward
from retailops_api.forecasting.frame import ForecastFrame
from retailops_api.forecasting.metrics import METRIC_DEFINITIONS_MARKDOWN, round_metrics
from retailops_api.forecasting.models import Forecaster, ForecastPoint, default_baselines
from retailops_api.forecasting.problem import (
    DEFAULT_HORIZON_WEEKS,
    DEFAULT_MIN_TRAIN_PERIODS,
    DEFAULT_MOVING_AVERAGE_WINDOW,
    DEFAULT_SEASONAL_LAG,
    DEFAULT_STEP_WEEKS,
    DEFAULT_TEST_PERIODS,
    DEFAULT_VALIDATION_PERIODS,
)
from retailops_api.forecasting.split import TemporalSplit, split_holdout
from retailops_api.forecasting.weeks import iso_week_label

BENCHMARK_JSON = "benchmark.json"
BENCHMARK_MARKDOWN = "benchmark.md"


@dataclass(frozen=True)
class BenchmarkConfig:
    horizon: int = DEFAULT_HORIZON_WEEKS
    min_train_periods: int = DEFAULT_MIN_TRAIN_PERIODS
    step_weeks: int = DEFAULT_STEP_WEEKS
    seasonal_lag: int = DEFAULT_SEASONAL_LAG
    window: int = DEFAULT_MOVING_AVERAGE_WINDOW
    validation_periods: int = DEFAULT_VALIDATION_PERIODS
    test_periods: int = DEFAULT_TEST_PERIODS


@dataclass(frozen=True)
class DatasetSummary:
    source: str
    start_date: date | None
    end_date: date | None
    checksum: str | None
    complete_weeks: int
    entity_count: int
    row_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "checksum": self.checksum,
            "complete_weeks": self.complete_weeks,
            "entity_count": self.entity_count,
            "row_count": self.row_count,
        }


@dataclass(frozen=True)
class BenchmarkReport:
    config: BenchmarkConfig
    dataset: DatasetSummary
    holdout: TemporalSplit
    results: tuple[BacktestResult, ...]


def run_benchmark(
    frame: ForecastFrame,
    *,
    dataset: DatasetSummary,
    config: BenchmarkConfig | None = None,
    models: tuple[Forecaster, ...] | None = None,
) -> BenchmarkReport:
    """Walk-forward every baseline and record the holdout cutoffs."""
    chosen = config or BenchmarkConfig()
    holdout = split_holdout(
        frame,
        validation_periods=chosen.validation_periods,
        test_periods=chosen.test_periods,
    )
    chosen_models = models or default_baselines(
        seasonal_lag=chosen.seasonal_lag,
        window=chosen.window,
    )
    results = tuple(
        walk_forward(
            frame,
            model,
            horizon=chosen.horizon,
            min_train_periods=chosen.min_train_periods,
            step_weeks=chosen.step_weeks,
        )
        for model in chosen_models
    )
    return BenchmarkReport(
        config=chosen,
        dataset=dataset,
        holdout=holdout,
        results=results,
    )


def report_to_dict(report: BenchmarkReport) -> dict[str, Any]:
    first = report.results[0]
    return {
        "problem": report.holdout.train.problem.to_dict(),
        "dataset": report.dataset.to_dict(),
        "holdout": {
            "train_end": report.holdout.train_end.isoformat(),
            "validation_end": report.holdout.validation_end.isoformat(),
            "test_end": report.holdout.test_end.isoformat() if report.holdout.test_end else None,
            "validation_periods": report.config.validation_periods,
            "test_periods": report.config.test_periods,
            "train_rows": len(report.holdout.train.rows),
            "validation_rows": len(report.holdout.validation.rows),
            "test_rows": len(report.holdout.test.rows),
        },
        "backtest": {
            "strategy": "rolling-origin",
            "horizon": report.config.horizon,
            "min_train_periods": report.config.min_train_periods,
            "step_weeks": report.config.step_weeks,
            "seasonal_lag": report.config.seasonal_lag,
            "moving_average_window": report.config.window,
            "fold_count": len(first.folds),
            "first_cutoff": first.first_cutoff.isoformat(),
            "last_cutoff": first.last_cutoff.isoformat(),
        },
        "models": {result.model_id: _result_to_dict(result) for result in report.results},
    }


def render_markdown(report: BenchmarkReport) -> str:
    problem = report.holdout.train.problem
    first = report.results[0]
    lines = [
        "# Forecast baseline benchmark",
        "",
        "## Problem",
        "",
        f"- **Name:** {problem.name}",
        f"- **Id:** `{problem.id}`",
        f"- **Target:** `{problem.target}`",
        f"- **Grain:** `{', '.join(problem.grain)}`",
        f"- **Frequency:** {problem.frequency}",
        f"- **Horizon:** {problem.horizon_periods} weeks",
        f"- **History window:** {_history_window(problem.history_periods)}",
        f"- **Aggregation:** {problem.aggregation}",
        f"- **Missing periods:** {problem.missing_periods}",
        "",
        "## Dataset",
        "",
        f"- **Source:** {report.dataset.source}",
        f"- **History:** {_date_range(report.dataset.start_date, report.dataset.end_date)}",
        f"- **Complete weeks:** {report.dataset.complete_weeks}",
        f"- **Entities:** {report.dataset.entity_count} store-category series",
        f"- **Frame rows:** {report.dataset.row_count}",
    ]
    if report.dataset.checksum:
        lines.append(f"- **Checksum:** `{report.dataset.checksum}`")
    lines.extend(
        [
            "",
            "## Backtest strategy",
            "",
            "Walk-forward (rolling-origin) evaluation. At each origin the model",
            "may read history through that cutoff, inclusive, and forecasts the",
            f"next {report.config.horizon} weeks. Origins advance by",
            f"{report.config.step_weeks} week(s). The first origin is the week",
            f"that first leaves {report.config.min_train_periods} weeks of",
            "history; the last origin still has a full horizon of observed weeks",
            "after it. Time-series rows are never split at random.",
            "",
            f"- **Folds:** {len(first.folds)}",
            f"- **First cutoff:** {_labeled(first.first_cutoff)}",
            f"- **Last cutoff:** {_labeled(first.last_cutoff)}",
            f"- **Seasonal lag:** {report.config.seasonal_lag} weeks",
            f"- **Moving-average window:** {report.config.window} weeks",
            "",
            "On a history shorter than the seasonal lag, seasonal naive falls",
            "back to the last observed week (the naive baseline). That is",
            "expected on a single year of weekly data with a 52-week lag.",
            "",
            "## Holdout cutoffs",
            "",
            "A contiguous time split is recorded so a later model can be compared",
            "on the same locked weeks. The numbers in this report come from the",
            "rolling backtest, not from a single shot on the holdout.",
            "",
            f"- **Train ends:** {_labeled(report.holdout.train_end)}",
            f"- **Validation ends:** {_labeled(report.holdout.validation_end)}",
            f"- **Test ends:** {_optional_date(report.holdout.test_end)}",
            "",
            "## Metric definitions",
            "",
            METRIC_DEFINITIONS_MARKDOWN.rstrip(),
            "",
            "## Results",
            "",
            "| Model | MAE | RMSE | WAPE | Bias |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for result in report.results:
        metrics = round_metrics(result.overall)
        lines.append(
            f"| `{result.model_id}` | {metrics['mae']} | {metrics['rmse']} | "
            f"{metrics['wape']} | {metrics['bias']} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_benchmark(report: BenchmarkReport, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    payload = report_to_dict(report)
    (directory / BENCHMARK_JSON).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (directory / BENCHMARK_MARKDOWN).write_text(render_markdown(report), encoding="utf-8")


def _result_to_dict(result: BacktestResult) -> dict[str, Any]:
    return {
        "model_id": result.model_id,
        "horizon": result.horizon,
        "overall": round_metrics(result.overall),
        "folds": [
            {
                "cutoff": fold.cutoff.isoformat(),
                "horizon": fold.horizon,
                "model_id": fold.model_id,
                "metrics": round_metrics(fold.metrics),
                "predictions": [_point_to_dict(point) for point in fold.predictions],
            }
            for fold in result.folds
        ],
    }


def _point_to_dict(point: ForecastPoint) -> dict[str, object]:
    return {
        "store_code": point.store_code,
        "category_code": point.category_code,
        "period_start": point.period_start.isoformat(),
        "step": point.step,
        "predicted": point.predicted,
        "actual": point.actual,
    }


def _history_window(periods: int | None) -> str:
    if periods is None:
        return "all complete ISO weeks in the source history"
    return f"{periods} trailing complete weeks"


def _labeled(day: date) -> str:
    return f"{day.isoformat()} ({iso_week_label(day)})"


def _date_range(start: date | None, end: date | None) -> str:
    if start is None or end is None:
        return "unknown"
    return f"{start.isoformat()} to {end.isoformat()}"


def _optional_date(value: date | None) -> str:
    if value is None:
        return "none"
    return _labeled(value)
