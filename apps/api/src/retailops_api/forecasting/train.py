"""Train the gradient-boosted demand model, evaluate it and register the artifact."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from retailops_api.dataset.contract import Dataset
from retailops_api.forecasting.artifact import (
    ArtifactMetadata,
    DataFingerprint,
    load_artifact,
    write_artifact,
)
from retailops_api.forecasting.benchmark import DatasetSummary
from retailops_api.forecasting.booster import (
    HistGBMForecaster,
    HistGBMTrainerConfig,
    train_hist_gbm,
)
from retailops_api.forecasting.feature_contract import FeatureConfig
from retailops_api.forecasting.feature_panel import FeatureFrame, build_supervised_frame
from retailops_api.forecasting.features import build_observables
from retailops_api.forecasting.frame import ForecastFrame
from retailops_api.forecasting.metrics import round_metrics
from retailops_api.forecasting.problem import (
    DEFAULT_HORIZON_WEEKS,
    DEFAULT_MOVING_AVERAGE_WINDOW,
    DEFAULT_SEASONAL_LAG,
    DEFAULT_TEST_PERIODS,
    DEFAULT_VALIDATION_PERIODS,
)
from retailops_api.forecasting.promotion import (
    DEFAULT_PROMOTION_POLICY,
    PromotionDecision,
    PromotionPolicy,
    compare_against_baselines,
)
from retailops_api.forecasting.registry import (
    DEFAULT_MODEL_NAME,
    ApprovalStatus,
    LocalModelRegistry,
    ModelVersion,
)
from retailops_api.forecasting.split import TemporalSplit, split_holdout


@dataclass(frozen=True)
class TrainSettings:
    feature: FeatureConfig
    trainer: HistGBMTrainerConfig
    horizon: int = DEFAULT_HORIZON_WEEKS
    validation_periods: int = DEFAULT_VALIDATION_PERIODS
    test_periods: int = DEFAULT_TEST_PERIODS
    seasonal_lag: int = DEFAULT_SEASONAL_LAG
    window: int = DEFAULT_MOVING_AVERAGE_WINDOW
    model_name: str = DEFAULT_MODEL_NAME
    promote: bool = False
    policy: PromotionPolicy = DEFAULT_PROMOTION_POLICY


@dataclass(frozen=True)
class TrainResult:
    settings: TrainSettings
    dataset: DatasetSummary
    holdout: TemporalSplit
    supervised: FeatureFrame
    model: HistGBMForecaster
    decision: PromotionDecision
    version: ModelVersion | None
    champion: ModelVersion | None
    artifact_dir: Path
    report_dir: Path


def run_training(
    dataset: Dataset,
    frame: ForecastFrame,
    *,
    summary: DatasetSummary,
    settings: TrainSettings | None = None,
    output_dir: Path,
    registry: LocalModelRegistry,
) -> TrainResult:
    """Build features, fit, score against baselines, write the artifact and register it.

    Promotion is applied only when ``settings.promote`` is true *and* the
    two-gate policy accepts the candidate. Registration always records a
    candidate version.
    """
    base = settings or TrainSettings(feature=FeatureConfig(), trainer=HistGBMTrainerConfig())
    feature = FeatureConfig(
        lags=base.feature.lags,
        rolling_window=base.feature.rolling_window,
        rolling_stats=base.feature.rolling_stats,
        rolling_min_max=base.feature.rolling_min_max,
        include_calendar=base.feature.include_calendar,
        include_commercial_lags=base.feature.include_commercial_lags,
        include_identifiers=base.feature.include_identifiers,
        holidays=base.feature.holidays or _holidays_from(dataset),
        min_history_weeks=base.feature.min_history_weeks,
    )
    chosen = TrainSettings(
        feature=feature,
        trainer=base.trainer,
        horizon=base.horizon,
        validation_periods=base.validation_periods,
        test_periods=base.test_periods,
        seasonal_lag=base.seasonal_lag,
        window=base.window,
        model_name=base.model_name,
        promote=base.promote,
        policy=base.policy,
    )

    holdout = split_holdout(
        frame,
        validation_periods=chosen.validation_periods,
        test_periods=chosen.test_periods,
    )
    observables = build_observables(dataset, frame.periods())
    supervised = build_supervised_frame(
        frame,
        config=feature,
        train_end=holdout.train_end,
        horizon=chosen.horizon,
        observables=observables,
        catalog=dataset.catalog,
        dataset_checksum=summary.checksum,
        source=summary.source,
        validation_end=holdout.validation_end,
        test_end=holdout.test_end,
    )
    model = train_hist_gbm(supervised, trainer=chosen.trainer, observables=tuple(observables))
    champion_model, _champion_version = _load_champion(registry, chosen.model_name)
    decision = compare_against_baselines(
        frame,
        model,
        cutoff=holdout.train_end,
        horizon=chosen.horizon,
        seasonal_lag=chosen.seasonal_lag,
        window=chosen.window,
        champion=champion_model,
        policy=chosen.policy,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    staging = output_dir / "artifact"
    if staging.exists():
        shutil.rmtree(staging)
    write_training_artifact(
        staging,
        model,
        supervised=supervised,
        summary=summary,
        decision=decision,
        model_name=chosen.model_name,
        horizon=chosen.horizon,
    )
    version = registry.register(
        chosen.model_name,
        staging,
        metrics=decision.candidate.metrics.to_dict(),
        data_fingerprint=summary.checksum,
    )
    if chosen.promote and decision.promote:
        version = registry.update_approval(
            chosen.model_name, version.version, ApprovalStatus.champion
        )

    _write_outputs(output_dir, chosen, summary, holdout, supervised, decision, version)
    return TrainResult(
        settings=chosen,
        dataset=summary,
        holdout=holdout,
        supervised=supervised,
        model=model,
        decision=decision,
        version=version,
        champion=registry.get_champion(chosen.model_name),
        artifact_dir=version.artifact_path,
        report_dir=output_dir,
    )


def write_training_artifact(
    directory: Path,
    model: HistGBMForecaster,
    *,
    supervised: FeatureFrame,
    summary: DatasetSummary,
    decision: PromotionDecision,
    model_name: str,
    horizon: int,
) -> Path:
    return write_artifact(
        directory,
        model,
        metadata=ArtifactMetadata(
            model_id=model.model_id,
            model_name=model_name,
            problem_id=supervised.problem.id,
            created_at=datetime.now(UTC),
            feature_names=supervised.feature_names,
            horizon=horizon,
        ),
        metrics=decision.candidate.metrics,
        fingerprint=DataFingerprint(
            dataset_checksum=summary.checksum,
            source=summary.source,
            train_end=supervised.train_end.isoformat() if supervised.train_end else None,
            validation_end=supervised.validation_end.isoformat()
            if supervised.validation_end
            else None,
            test_end=supervised.test_end.isoformat() if supervised.test_end else None,
            train_rows=len(supervised.rows),
            feature_names=supervised.feature_names,
        ),
        extra_metrics={
            "comparisons": {
                score.model_id: score.metrics.to_dict() for score in decision.comparisons
            },
            "promotion": decision.to_dict(),
        },
    )


def render_train_markdown(
    *,
    settings: TrainSettings,
    summary: DatasetSummary,
    holdout: TemporalSplit,
    supervised: FeatureFrame,
    decision: PromotionDecision,
    version: ModelVersion | None,
) -> str:
    metrics = round_metrics(decision.candidate.metrics)
    lines = [
        "# Forecast model training",
        "",
        "## Dataset",
        "",
        f"- **Source:** {summary.source}",
        f"- **Checksum:** `{summary.checksum}`",
        f"- **Complete weeks:** {summary.complete_weeks}",
        f"- **Entities:** {summary.entity_count}",
        "",
        "## Holdout",
        "",
        f"- **Train ends:** {holdout.train_end.isoformat()}",
        f"- **Validation ends:** {holdout.validation_end.isoformat()}",
        f"- **Test ends:** {holdout.test_end.isoformat() if holdout.test_end else 'none'}",
        "",
        "## Features",
        "",
        f"- **Names:** {', '.join(supervised.feature_names)}",
        f"- **Training rows:** {len(supervised.rows)}",
        f"- **Lags:** {', '.join(str(lag) for lag in settings.feature.lags)}",
        f"- **Rolling window:** {settings.feature.rolling_window}",
        "",
        "## Trainer",
        "",
        "- **Implementation:** histogram gradient boosting",
        f"- **Trees:** {settings.trainer.n_estimators}",
        f"- **Learning rate:** {settings.trainer.learning_rate}",
        f"- **Max depth:** {settings.trainer.max_depth}",
        f"- **Seed:** {settings.trainer.random_state}",
        "",
        "## Promotion policy",
        "",
        str(settings.policy.to_dict()["rule"]),
        "",
        f"- **Promote:** {'yes' if decision.promote else 'no'}",
    ]
    for reason in decision.reasons:
        lines.append(f"- {reason}")
    lines.extend(
        [
            "",
            "## Validation origin metrics",
            "",
            f"Scored from `{holdout.train_end.isoformat()}` for {settings.horizon} weeks.",
            "",
            "| Model | MAE | RMSE | WAPE | Bias |",
            "| --- | ---: | ---: | ---: | ---: |",
            f"| `{decision.candidate.model_id}` | {metrics['mae']} | {metrics['rmse']} | "
            f"{metrics['wape']} | {metrics['bias']} |",
        ]
    )
    for score in decision.comparisons:
        rounded = round_metrics(score.metrics)
        lines.append(
            f"| `{score.model_id}` | {rounded['mae']} | {rounded['rmse']} | "
            f"{rounded['wape']} | {rounded['bias']} |"
        )
    if version is not None:
        lines.extend(
            [
                "",
                "## Registry",
                "",
                f"- **Model:** `{version.model_name}`",
                f"- **Version:** `{version.version}`",
                f"- **Status:** `{version.status.value}`",
                f"- **Path:** `{version.artifact_path}`",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def _write_outputs(
    output_dir: Path,
    settings: TrainSettings,
    summary: DatasetSummary,
    holdout: TemporalSplit,
    supervised: FeatureFrame,
    decision: PromotionDecision,
    version: ModelVersion | None,
) -> None:
    payload = {
        "dataset": summary.to_dict(),
        "holdout": {
            "train_end": holdout.train_end.isoformat(),
            "validation_end": holdout.validation_end.isoformat(),
            "test_end": holdout.test_end.isoformat() if holdout.test_end else None,
        },
        "features": supervised.to_dict(),
        "trainer": settings.trainer.to_dict(),
        "metrics": decision.to_dict(),
        "version": version.to_dict() if version else None,
    }
    (output_dir / "train_metrics.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "train_report.md").write_text(
        render_train_markdown(
            settings=settings,
            summary=summary,
            holdout=holdout,
            supervised=supervised,
            decision=decision,
            version=version,
        ),
        encoding="utf-8",
    )


def _load_champion(
    registry: LocalModelRegistry,
    model_name: str,
) -> tuple[HistGBMForecaster | None, ModelVersion | None]:
    version = registry.get_champion(model_name)
    if version is None:
        return None, None
    model = load_artifact(version.artifact_path)
    model.model_id = f"champion_{version.version}"
    return model, version


def _holidays_from(dataset: Dataset) -> tuple[date, ...]:
    return tuple(sorted({day.business_date for day in dataset.calendar if day.is_holiday}))
