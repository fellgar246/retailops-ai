"""Train the weekly demand model, evaluate it and register a local version.

    make train

Or, from ``apps/api``:

    uv run retailops-train
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from retailops_api.core.adapters import model_registry_for
from retailops_api.core.config import get_settings
from retailops_api.forecasting.booster import HistGBMTrainerConfig
from retailops_api.forecasting.feature_contract import FeatureConfig
from retailops_api.forecasting.problem import (
    DEFAULT_HORIZON_WEEKS,
    DEFAULT_MOVING_AVERAGE_WINDOW,
    DEFAULT_SEASONAL_LAG,
    DEFAULT_TEST_PERIODS,
    DEFAULT_VALIDATION_PERIODS,
)
from retailops_api.forecasting.registry import DEFAULT_MODEL_NAME
from retailops_api.forecasting.sources import (
    FRAME_FILE,
    default_forecast_output,
    default_registry_root,
    load_forecast_dataset,
    write_frame_csv,
)
from retailops_api.forecasting.train import TrainSettings, run_training
from retailops_api.synthetic.config import ScalePreset


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        dataset, summary, frame = load_forecast_dataset(
            input_path=args.input,
            preset=args.preset,
            seed=args.seed,
            start_date=args.start_date,
            end_date=args.end_date,
            source=args.source,
        )
        output = args.output or default_forecast_output()
        registry = model_registry_for(
            get_settings(),
            root=args.registry or default_registry_root(),
        )
        result = run_training(
            dataset,
            frame,
            summary=summary,
            settings=_settings_from_args(args),
            output_dir=output,
            registry=registry,
        )
        write_frame_csv(frame, output / FRAME_FILE)
        version = result.version
        print(
            f"wrote {output / 'train_metrics.json'}  {output / 'train_report.md'}  "
            f"rows={len(result.supervised.rows)}  features={len(result.supervised.feature_names)}"
        )
        if version is not None:
            print(
                f"registered {version.model_name}/{version.version}  "
                f"status={version.status.value}  path={version.artifact_path}"
            )
        metrics = result.decision.candidate.metrics
        print(
            f"  {result.model.model_id}: mae={metrics.mae:.4f} rmse={metrics.rmse:.4f} "
            f"wape={metrics.wape:.4f} bias={metrics.bias:.4f}  "
            f"promote={str(result.decision.promote).lower()}"
        )
        for score in result.decision.comparisons:
            print(f"  {score.model_id}: mae={score.metrics.mae:.4f} wape={score.metrics.wape:.4f}")
        return 0
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="retailops-train",
        description=(
            "Build weekly features, train a histogram-GBM demand model, score it "
            "against the baselines and register the artifact locally."
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
        help="Directory of a portable dataset to train on instead of generating one.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Directory for the frame, metrics and staging artifact.",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        help="Local registry root (default: <repo>/artifacts/models).",
    )
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--horizon", type=int, default=DEFAULT_HORIZON_WEEKS)
    parser.add_argument("--validation-periods", type=int, default=DEFAULT_VALIDATION_PERIODS)
    parser.add_argument("--test-periods", type=int, default=DEFAULT_TEST_PERIODS)
    parser.add_argument("--seasonal-lag", type=int, default=DEFAULT_SEASONAL_LAG)
    parser.add_argument("--ma-window", type=int, default=DEFAULT_MOVING_AVERAGE_WINDOW)
    parser.add_argument("--min-history-weeks", type=int, default=FeatureConfig().min_history_weeks)
    parser.add_argument("--n-estimators", type=int, default=HistGBMTrainerConfig().n_estimators)
    parser.add_argument("--learning-rate", type=float, default=HistGBMTrainerConfig().learning_rate)
    parser.add_argument("--max-depth", type=int, default=HistGBMTrainerConfig().max_depth)
    parser.add_argument(
        "--min-samples-leaf", type=int, default=HistGBMTrainerConfig().min_samples_leaf
    )
    parser.add_argument("--seed-model", type=int, default=HistGBMTrainerConfig().random_state)
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Promote the candidate to champion when both policy gates pass.",
    )
    parser.add_argument("--source", help="Override the dataset source label on the report.")
    return parser.parse_args(argv)


def _settings_from_args(args: argparse.Namespace) -> TrainSettings:
    return TrainSettings(
        feature=FeatureConfig(min_history_weeks=args.min_history_weeks),
        trainer=HistGBMTrainerConfig(
            n_estimators=args.n_estimators,
            learning_rate=args.learning_rate,
            max_depth=args.max_depth,
            min_samples_leaf=args.min_samples_leaf,
            random_state=args.seed_model,
        ),
        horizon=args.horizon,
        validation_periods=args.validation_periods,
        test_periods=args.test_periods,
        seasonal_lag=args.seasonal_lag,
        window=args.ma_window,
        model_name=args.model_name,
        promote=args.promote,
    )


def _date(value: str) -> date:
    return date.fromisoformat(value)


if __name__ == "__main__":
    raise SystemExit(main())
