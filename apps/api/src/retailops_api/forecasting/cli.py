"""Build the weekly demand frame and run baseline backtests.

    make forecast

Or, from ``apps/api``:

    uv run retailops-forecast
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from retailops_api.dataset.contract import Dataset
from retailops_api.forecasting.benchmark import (
    BENCHMARK_JSON,
    BENCHMARK_MARKDOWN,
    BenchmarkConfig,
    BenchmarkReport,
    DatasetSummary,
    run_benchmark,
    write_benchmark,
)
from retailops_api.forecasting.frame import ForecastFrame
from retailops_api.forecasting.persist import persist_backtest
from retailops_api.forecasting.problem import (
    DEFAULT_HORIZON_WEEKS,
    DEFAULT_MIN_TRAIN_PERIODS,
    DEFAULT_MOVING_AVERAGE_WINDOW,
    DEFAULT_SEASONAL_LAG,
    DEFAULT_STEP_WEEKS,
    DEFAULT_TEST_PERIODS,
    DEFAULT_VALIDATION_PERIODS,
)
from retailops_api.forecasting.sources import (
    FRAME_FILE,
    default_forecast_output,
    load_forecast_dataset,
    write_frame_csv,
)
from retailops_api.synthetic.config import ScalePreset


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    command = args.command or "benchmark"
    try:
        if command == "frame":
            _write_frame(args)
            return 0
        _run_benchmark(args)
        return 0
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="retailops-forecast",
        description=(
            "Build the weekly category-demand frame and walk-forward the "
            "naive, seasonal-naive and moving-average baselines."
        ),
    )
    parser.add_argument(
        "--preset",
        choices=[preset.value for preset in ScalePreset],
        default=ScalePreset.development.value,
        help="Synthetic scale used when --input is omitted (default: development).",
    )
    parser.add_argument("--seed", type=int)
    parser.add_argument("--start-date", type=_date)
    parser.add_argument("--end-date", type=_date)
    parser.add_argument(
        "--input",
        type=Path,
        help="Directory of a portable dataset to score instead of generating one.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Directory for the frame and benchmark files (default: <repo>/data/forecasts).",
    )
    parser.add_argument("--horizon", type=int, default=DEFAULT_HORIZON_WEEKS)
    parser.add_argument("--min-train-periods", type=int, default=DEFAULT_MIN_TRAIN_PERIODS)
    parser.add_argument("--step-weeks", type=int, default=DEFAULT_STEP_WEEKS)
    parser.add_argument("--seasonal-lag", type=int, default=DEFAULT_SEASONAL_LAG)
    parser.add_argument("--ma-window", type=int, default=DEFAULT_MOVING_AVERAGE_WINDOW)
    parser.add_argument("--validation-periods", type=int, default=DEFAULT_VALIDATION_PERIODS)
    parser.add_argument("--test-periods", type=int, default=DEFAULT_TEST_PERIODS)
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Write each backtest fold to the configured database.",
    )
    parser.add_argument("--source", help="Override the dataset source label on the report.")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("frame", help="Write the weekly demand frame as CSV.")
    sub.add_parser("benchmark", help="Walk-forward every baseline and write the report (default).")
    return parser.parse_args(argv)


def _write_frame(args: argparse.Namespace) -> None:
    _, _, frame = _load_or_generate(args)
    output = _output_dir(args)
    write_frame_csv(frame, output / FRAME_FILE)
    print(
        f"wrote {output / FRAME_FILE}  rows={len(frame.rows)}  "
        f"entities={len(frame.entities())}  weeks={len(frame.periods())}"
    )


def _run_benchmark(args: argparse.Namespace) -> None:
    _, summary, frame = _load_or_generate(args)
    output = _output_dir(args)
    write_frame_csv(frame, output / FRAME_FILE)
    report = run_benchmark(frame, dataset=summary, config=_config_from_args(args))
    write_benchmark(report, output)
    if args.persist:
        _persist(report)
    print(
        f"wrote {output / BENCHMARK_JSON}  {output / BENCHMARK_MARKDOWN}  "
        f"folds={len(report.results[0].folds)}  models={len(report.results)}"
    )
    for result in report.results:
        metrics = result.overall
        print(
            f"  {result.model_id}: mae={metrics.mae:.4f} rmse={metrics.rmse:.4f} "
            f"wape={metrics.wape:.4f} bias={metrics.bias:.4f}"
        )


def _load_or_generate(args: argparse.Namespace) -> tuple[Dataset, DatasetSummary, ForecastFrame]:
    return load_forecast_dataset(
        input_path=args.input,
        preset=args.preset,
        seed=args.seed,
        start_date=args.start_date,
        end_date=args.end_date,
        source=args.source,
    )


def _config_from_args(args: argparse.Namespace) -> BenchmarkConfig:
    return BenchmarkConfig(
        horizon=args.horizon,
        min_train_periods=args.min_train_periods,
        step_weeks=args.step_weeks,
        seasonal_lag=args.seasonal_lag,
        window=args.ma_window,
        validation_periods=args.validation_periods,
        test_periods=args.test_periods,
    )


def _persist(report: BenchmarkReport) -> None:
    from retailops_api.db.session import get_session_factory

    generated_at = datetime.now(UTC)
    with get_session_factory()() as session:
        try:
            for result in report.results:
                persist_backtest(
                    session,
                    result,
                    generated_at=generated_at,
                    problem_id=report.holdout.train.problem.id,
                    run_metadata={
                        "source": report.dataset.source,
                        "checksum": report.dataset.checksum,
                        "seasonal_lag": report.config.seasonal_lag,
                        "window": report.config.window,
                    },
                )
            session.commit()
        except Exception:
            session.rollback()
            raise
    print("persisted forecast runs")


def _output_dir(args: argparse.Namespace) -> Path:
    if args.output is not None:
        return Path(args.output)
    return default_forecast_output()


def _date(value: str) -> date:
    return date.fromisoformat(value)


if __name__ == "__main__":
    raise SystemExit(main())
