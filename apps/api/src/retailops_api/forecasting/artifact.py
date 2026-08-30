"""On-disk model package: estimator, metadata, features, config, metrics, fingerprint.

A directory written by ``write_artifact`` reloads with ``load_artifact`` in a
fresh process. Nothing is taken from notebook or interpreter state.
"""

from __future__ import annotations

import json
import platform
import sys
from dataclasses import dataclass
from datetime import datetime
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

import joblib

from retailops_api.forecasting.booster import HistGBMForecaster, HistGBMTrainerConfig
from retailops_api.forecasting.feature_contract import FEATURE_CONTRACT, FeatureConfig
from retailops_api.forecasting.features import IdentifierMaps, WeeklyObservables
from retailops_api.forecasting.metrics import ForecastMetrics

MODEL_FILE = "model.joblib"
METADATA_FILE = "metadata.json"
FEATURES_FILE = "features.json"
TRAINING_CONFIG_FILE = "training_config.json"
METRICS_FILE = "metrics.json"
FINGERPRINT_FILE = "data_fingerprint.json"
RUNTIME_FILE = "runtime.json"
ENCODINGS_FILE = "encodings.json"
OBSERVABLES_FILE = "observables.json"

ARTIFACT_FILES = (
    MODEL_FILE,
    METADATA_FILE,
    FEATURES_FILE,
    TRAINING_CONFIG_FILE,
    METRICS_FILE,
    FINGERPRINT_FILE,
    RUNTIME_FILE,
    ENCODINGS_FILE,
    OBSERVABLES_FILE,
)


@dataclass(frozen=True)
class ArtifactMetadata:
    model_id: str
    model_name: str
    problem_id: str
    created_at: datetime
    feature_names: tuple[str, ...]
    horizon: int
    status: str = "candidate"

    def to_dict(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "problem_id": self.problem_id,
            "created_at": self.created_at.isoformat(),
            "feature_names": list(self.feature_names),
            "horizon": self.horizon,
            "status": self.status,
        }


@dataclass(frozen=True)
class DataFingerprint:
    dataset_checksum: str | None
    source: str
    train_end: str | None
    validation_end: str | None
    test_end: str | None
    train_rows: int
    feature_names: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "dataset_checksum": self.dataset_checksum,
            "source": self.source,
            "train_end": self.train_end,
            "validation_end": self.validation_end,
            "test_end": self.test_end,
            "train_rows": self.train_rows,
            "feature_names": list(self.feature_names),
        }


def write_artifact(
    directory: Path,
    model: HistGBMForecaster,
    *,
    metadata: ArtifactMetadata,
    metrics: ForecastMetrics | dict[str, float],
    fingerprint: DataFingerprint,
    extra_metrics: dict[str, object] | None = None,
) -> Path:
    """Write every required file. Creates ``directory`` if needed."""
    directory.mkdir(parents=True, exist_ok=True)
    joblib.dump(model.estimator, directory / MODEL_FILE)
    _write_json(directory / METADATA_FILE, metadata.to_dict())
    _write_json(
        directory / FEATURES_FILE,
        {
            "feature_names": list(model.feature_names),
            "config": model.feature_config.to_dict(),
            "contract": [spec.to_dict() for spec in FEATURE_CONTRACT],
        },
    )
    _write_json(
        directory / TRAINING_CONFIG_FILE,
        {
            "feature": model.feature_config.to_dict(),
            "trainer": model.trainer_config.to_dict(),
        },
    )
    metrics_payload: dict[str, object] = dict(
        metrics.to_dict() if isinstance(metrics, ForecastMetrics) else metrics
    )
    if extra_metrics:
        metrics_payload = {**metrics_payload, **extra_metrics}
    _write_json(directory / METRICS_FILE, metrics_payload)
    _write_json(directory / FINGERPRINT_FILE, fingerprint.to_dict())
    _write_json(directory / RUNTIME_FILE, runtime_info())
    _write_json(directory / ENCODINGS_FILE, model.identifier_maps.to_dict())
    _write_json(
        directory / OBSERVABLES_FILE,
        [row.to_dict() for row in model.observables],
    )
    return directory


def load_artifact(directory: Path) -> HistGBMForecaster:
    """Reload an estimator and its sidecar files. Raises if the package is incomplete."""
    missing = [name for name in ARTIFACT_FILES if not (directory / name).is_file()]
    if missing:
        raise FileNotFoundError(f"incomplete model artifact in {directory}: {missing}")
    estimator = joblib.load(directory / MODEL_FILE)
    features = _read_json(directory / FEATURES_FILE)
    training = _read_json(directory / TRAINING_CONFIG_FILE)
    encodings = _read_json(directory / ENCODINGS_FILE)
    observables_raw = _read_json(directory / OBSERVABLES_FILE)
    if not isinstance(observables_raw, list):
        raise ValueError("observables.json must be a list")
    feature_payload = features.get("config", {})
    trainer_payload = training.get("trainer", {})
    if not isinstance(feature_payload, dict) or not isinstance(trainer_payload, dict):
        raise ValueError("artifact config objects must be mappings")
    names_raw = features.get("feature_names", [])
    if not isinstance(names_raw, list):
        raise ValueError("feature_names must be a list")
    if not isinstance(encodings, dict):
        raise ValueError("encodings.json must be a mapping")
    meta = read_metadata(directory)
    model_id = str(meta.get("model_id", "hist_gbm"))
    return HistGBMForecaster(
        estimator=estimator,
        feature_config=FeatureConfig.from_dict(feature_payload),
        trainer_config=HistGBMTrainerConfig.from_dict(trainer_payload),
        feature_names=tuple(str(name) for name in names_raw),
        identifier_maps=IdentifierMaps.from_dict(encodings),
        observables=tuple(
            WeeklyObservables.from_dict(row) for row in observables_raw if isinstance(row, dict)
        ),
        model_id=model_id,
    )


def read_metadata(directory: Path) -> dict[str, Any]:
    payload = _read_json(directory / METADATA_FILE)
    if not isinstance(payload, dict):
        raise ValueError("metadata.json must be a mapping")
    return payload


def read_metrics(directory: Path) -> dict[str, Any]:
    payload = _read_json(directory / METRICS_FILE)
    if not isinstance(payload, dict):
        raise ValueError("metrics.json must be a mapping")
    return payload


def read_fingerprint(directory: Path) -> dict[str, Any]:
    payload = _read_json(directory / FINGERPRINT_FILE)
    if not isinstance(payload, dict):
        raise ValueError("data_fingerprint.json must be a mapping")
    return payload


def runtime_info() -> dict[str, str]:
    return {
        "python": sys.version.split()[0],
        "scikit_learn": _package_version("scikit-learn"),
        "joblib": _package_version("joblib"),
        "numpy": _package_version("numpy"),
        "platform": platform.platform(),
        "implementation": platform.python_implementation(),
    }


def _package_version(name: str) -> str:
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return "unknown"


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
