"""Cloud-neutral model registry contract and a local filesystem implementation.

Operations:

- register a candidate
- list versions
- retrieve a version
- update approval status
- retrieve the champion

``LocalModelRegistry`` versions a model name under a directory, for example
``artifacts/models/category-forecast/v001``. The same operations map onto a
hosted registry (SageMaker Model Registry: ``CreateModelPackage``,
``ModelPackageVersion``, ``ModelApprovalStatus``, the approved package an
endpoint loads) without changing callers.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

DEFAULT_MODEL_NAME = "category-forecast"
INDEX_FILE = "index.json"


class ApprovalStatus(StrEnum):
    candidate = "candidate"
    approved = "approved"
    champion = "champion"
    rejected = "rejected"
    archived = "archived"


class RegistryError(ValueError):
    """Unknown model, version or illegal status transition."""


@dataclass(frozen=True)
class ModelVersion:
    model_name: str
    version: str
    status: ApprovalStatus
    registered_at: datetime
    artifact_path: Path
    metrics: dict[str, float] | None = None
    data_fingerprint: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "model_name": self.model_name,
            "version": self.version,
            "status": self.status.value,
            "registered_at": self.registered_at.isoformat(),
            "artifact_path": str(self.artifact_path),
            "metrics": self.metrics,
            "data_fingerprint": self.data_fingerprint,
        }


class ModelRegistry(Protocol):
    """Storage-neutral versioning and approval. Implementations must not assume a cloud."""

    def register(
        self,
        model_name: str,
        artifact_dir: Path,
        *,
        metrics: dict[str, float] | None = None,
        data_fingerprint: str | None = None,
    ) -> ModelVersion: ...

    def list_versions(self, model_name: str) -> tuple[ModelVersion, ...]: ...

    def get_version(self, model_name: str, version: str) -> ModelVersion: ...

    def update_approval(
        self,
        model_name: str,
        version: str,
        status: ApprovalStatus,
    ) -> ModelVersion: ...

    def get_champion(self, model_name: str) -> ModelVersion | None: ...


class LocalModelRegistry:
    """Filesystem versions: ``<root>/<model_name>/v001``, ``v002``, … plus ``index.json``."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def register(
        self,
        model_name: str,
        artifact_dir: Path,
        *,
        metrics: dict[str, float] | None = None,
        data_fingerprint: str | None = None,
    ) -> ModelVersion:
        source = Path(artifact_dir)
        if not source.is_dir():
            raise RegistryError(f"artifact directory does not exist: {source}")
        model_dir = self._model_dir(model_name)
        model_dir.mkdir(parents=True, exist_ok=True)
        index = self._load_index(model_name)
        version = _next_version(index["versions"])
        dest = model_dir / version
        if dest.resolve() != source.resolve():
            if dest.exists():
                raise RegistryError(f"version directory already exists: {dest}")
            shutil.copytree(source, dest)
        record = {
            "version": version,
            "status": ApprovalStatus.candidate.value,
            "registered_at": datetime.now(UTC).isoformat(),
            "metrics": metrics,
            "data_fingerprint": data_fingerprint,
        }
        index["versions"].append(record)
        self._save_index(model_name, index)
        return self._to_version(model_name, record)

    def list_versions(self, model_name: str) -> tuple[ModelVersion, ...]:
        index = self._load_index(model_name)
        versions = [self._to_version(model_name, row) for row in index["versions"]]
        return tuple(sorted(versions, key=lambda item: _version_number(item.version)))

    def get_version(self, model_name: str, version: str) -> ModelVersion:
        for item in self.list_versions(model_name):
            if item.version == version:
                return item
        raise RegistryError(f"unknown version {version} for {model_name}")

    def update_approval(
        self,
        model_name: str,
        version: str,
        status: ApprovalStatus,
    ) -> ModelVersion:
        index = self._load_index(model_name)
        found = None
        for row in index["versions"]:
            if row["version"] == version:
                found = row
                break
        if found is None:
            raise RegistryError(f"unknown version {version} for {model_name}")
        if status is ApprovalStatus.champion:
            for row in index["versions"]:
                if row["status"] == ApprovalStatus.champion.value and row["version"] != version:
                    row["status"] = ApprovalStatus.approved.value
        found["status"] = status.value
        index["champion_version"] = (
            version if status is ApprovalStatus.champion else index.get("champion_version")
        )
        if status is not ApprovalStatus.champion and index.get("champion_version") == version:
            index["champion_version"] = None
        if status is ApprovalStatus.champion:
            index["champion_version"] = version
        self._save_index(model_name, index)
        return self._to_version(model_name, found)

    def get_champion(self, model_name: str) -> ModelVersion | None:
        index = self._load_index(model_name)
        champion = index.get("champion_version")
        if not champion:
            for row in index["versions"]:
                if row["status"] == ApprovalStatus.champion.value:
                    return self._to_version(model_name, row)
            return None
        try:
            return self.get_version(model_name, str(champion))
        except RegistryError:
            return None

    def _model_dir(self, model_name: str) -> Path:
        return self.root / model_name

    def _index_path(self, model_name: str) -> Path:
        return self._model_dir(model_name) / INDEX_FILE

    def _load_index(self, model_name: str) -> dict[str, Any]:
        path = self._index_path(model_name)
        if not path.is_file():
            return {"model_name": model_name, "champion_version": None, "versions": []}
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RegistryError(f"corrupt registry index: {path}")
        payload.setdefault("model_name", model_name)
        payload.setdefault("champion_version", None)
        payload.setdefault("versions", [])
        return payload

    def _save_index(self, model_name: str, index: dict[str, Any]) -> None:
        path = self._index_path(model_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _to_version(self, model_name: str, row: dict[str, Any]) -> ModelVersion:
        metrics_raw = row.get("metrics")
        metrics: dict[str, float] | None
        if isinstance(metrics_raw, dict):
            metrics = {str(key): float(value) for key, value in metrics_raw.items()}
        else:
            metrics = None
        registered = row.get("registered_at")
        registered_at = datetime.fromisoformat(str(registered)) if registered else datetime.now(UTC)
        return ModelVersion(
            model_name=model_name,
            version=str(row["version"]),
            status=ApprovalStatus(str(row["status"])),
            registered_at=registered_at,
            artifact_path=self._model_dir(model_name) / str(row["version"]),
            metrics=metrics,
            data_fingerprint=str(row["data_fingerprint"]) if row.get("data_fingerprint") else None,
        )


def _next_version(rows: list[dict[str, Any]]) -> str:
    numbers = [_version_number(str(row["version"])) for row in rows if "version" in row]
    return f"v{max(numbers, default=0) + 1:03d}"


def _version_number(version: str) -> int:
    if version.startswith("v") and version[1:].isdigit():
        return int(version[1:])
    raise RegistryError(f"unsupported version label {version!r}")
