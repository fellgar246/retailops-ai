"""SageMaker Model Registry implementation of ``ModelRegistry``.

Register records metadata (metrics, fingerprint, approval) through an
injectable client. Artifact files are not uploaded; the adapter only
declares the URI the package would point at.

Champion selection is explicit: a version whose customer metadata
``retailops_approval`` is ``champion``. Promoting a version demotes the
previous champion to ``approved``. Latest-approved is not implied.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from retailops_api.forecasting.registry import (
    ApprovalStatus,
    ModelVersion,
    RegistryError,
    _next_version,
    _version_number,
)

_APPROVAL_TO_SAGEMAKER = {
    ApprovalStatus.candidate: "PendingManualApproval",
    ApprovalStatus.approved: "Approved",
    ApprovalStatus.champion: "Approved",
    ApprovalStatus.rejected: "Rejected",
    ApprovalStatus.archived: "Rejected",
}

_SAGEMAKER_TO_APPROVAL = {
    "PendingManualApproval": ApprovalStatus.candidate,
    "Approved": ApprovalStatus.approved,
    "Rejected": ApprovalStatus.rejected,
}


class SageMakerClient(Protocol):
    """Subset of a boto3 SageMaker client used by this adapter."""

    def create_model_package(self, **kwargs: Any) -> dict[str, Any]: ...

    def list_model_packages(self, **kwargs: Any) -> dict[str, Any]: ...

    def describe_model_package(self, **kwargs: Any) -> dict[str, Any]: ...

    def update_model_package(self, **kwargs: Any) -> dict[str, Any]: ...


class SageMakerModelRegistry:
    """Hosted registry behind the same operations as ``LocalModelRegistry``."""

    def __init__(
        self,
        client: SageMakerClient,
        *,
        model_package_group: str,
        artifact_bucket: str,
        artifact_prefix: str = "models",
        region: str = "us-east-1",
        account_id: str = "",
        inference_image: str = "public.ecr.aws/docker/library/python:3.12-slim",
    ) -> None:
        if not model_package_group.strip():
            raise RegistryError("SageMaker model package group is required")
        if not artifact_bucket.strip():
            raise RegistryError("artifact bucket is required to declare a model-data URI")
        self.client = client
        self.model_package_group = model_package_group.strip()
        self.artifact_bucket = artifact_bucket.strip()
        self.artifact_prefix = artifact_prefix.strip().strip("/")
        self.region = region
        self.account_id = account_id
        self.inference_image = inference_image

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
        version = self._next_local_version(model_name)
        uri = self.declared_artifact_uri(model_name, version)
        metadata = _customer_metadata(
            model_name=model_name,
            version=version,
            status=ApprovalStatus.candidate,
            metrics=metrics,
            data_fingerprint=data_fingerprint,
        )
        try:
            created = self.client.create_model_package(
                ModelPackageGroupName=self.model_package_group,
                ModelPackageDescription=f"{model_name} {version}",
                ModelApprovalStatus=_APPROVAL_TO_SAGEMAKER[ApprovalStatus.candidate],
                CustomerMetadataProperties=metadata,
                InferenceSpecification={
                    "Containers": [
                        {
                            "Image": self.inference_image,
                            "ModelDataUrl": uri,
                        }
                    ],
                    "SupportedContentTypes": ["application/json"],
                    "SupportedResponseMIMETypes": ["application/json"],
                },
            )
        except Exception as error:
            raise RegistryError(f"CreateModelPackage failed: {error}") from error
        arn = str(created.get("ModelPackageArn") or "")
        described = self._describe(arn) if arn else None
        return self._to_version(described or created, fallback_dir=source)

    def list_versions(self, model_name: str) -> tuple[ModelVersion, ...]:
        versions = [item for item in self._all_versions() if item.model_name == model_name]
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
        current = self.get_version(model_name, version)
        arn = self._arn_for(model_name, version)
        if status is ApprovalStatus.champion:
            for other in self.list_versions(model_name):
                if other.version != version and other.status is ApprovalStatus.champion:
                    self._write_approval(
                        self._arn_for(model_name, other.version),
                        other,
                        ApprovalStatus.approved,
                    )
        updated = self._write_approval(arn, current, status)
        return updated

    def get_champion(self, model_name: str) -> ModelVersion | None:
        champions = [
            item
            for item in self.list_versions(model_name)
            if item.status is ApprovalStatus.champion
        ]
        if not champions:
            return None
        return champions[-1]

    def declared_artifact_uri(self, model_name: str, version: str) -> str:
        """S3 URI this adapter would record. Files are not uploaded."""
        prefix = (
            f"{self.artifact_prefix}/{model_name}/{version}"
            if self.artifact_prefix
            else f"{model_name}/{version}"
        )
        return f"s3://{self.artifact_bucket}/{prefix}/model.tar.gz"

    def _next_local_version(self, model_name: str) -> str:
        rows = [{"version": item.version} for item in self.list_versions(model_name)]
        return _next_version(rows)

    def _all_versions(self) -> list[ModelVersion]:
        try:
            listed = self.client.list_model_packages(
                ModelPackageGroupName=self.model_package_group,
                SortBy="CreationTime",
                SortOrder="Ascending",
            )
        except Exception as error:
            raise RegistryError(f"ListModelPackages failed: {error}") from error
        summaries = listed.get("ModelPackageSummaryList") or []
        versions: list[ModelVersion] = []
        for summary in summaries:
            if not isinstance(summary, dict):
                continue
            arn = str(summary.get("ModelPackageArn") or "")
            if not arn:
                continue
            versions.append(self._to_version(self._describe(arn)))
        return versions

    def _describe(self, arn: str) -> dict[str, Any]:
        try:
            described = self.client.describe_model_package(ModelPackageName=arn)
        except Exception as error:
            raise RegistryError(f"DescribeModelPackage failed for {arn}: {error}") from error
        if not isinstance(described, dict):
            raise RegistryError(f"DescribeModelPackage returned a non-object for {arn}")
        return described

    def _arn_for(self, model_name: str, version: str) -> str:
        described = self._package_for(model_name, version)
        arn = str(described.get("ModelPackageArn") or "")
        if not arn:
            raise RegistryError(f"unknown version {version} for {model_name}")
        return arn

    def _package_for(self, model_name: str, version: str) -> dict[str, Any]:
        for item in self._all_described():
            meta = _as_str_map(item.get("CustomerMetadataProperties"))
            if (
                meta.get("retailops_model_name") == model_name
                and meta.get("retailops_version") == version
            ):
                return item
        raise RegistryError(f"unknown version {version} for {model_name}")

    def _all_described(self) -> list[dict[str, Any]]:
        try:
            listed = self.client.list_model_packages(
                ModelPackageGroupName=self.model_package_group,
                SortBy="CreationTime",
                SortOrder="Ascending",
            )
        except Exception as error:
            raise RegistryError(f"ListModelPackages failed: {error}") from error
        result: list[dict[str, Any]] = []
        for summary in listed.get("ModelPackageSummaryList") or []:
            if not isinstance(summary, dict):
                continue
            arn = str(summary.get("ModelPackageArn") or "")
            if arn:
                result.append(self._describe(arn))
        return result

    def _write_approval(
        self,
        arn: str,
        current: ModelVersion,
        status: ApprovalStatus,
    ) -> ModelVersion:
        metadata = _customer_metadata(
            model_name=current.model_name,
            version=current.version,
            status=status,
            metrics=current.metrics,
            data_fingerprint=current.data_fingerprint,
        )
        try:
            self.client.update_model_package(
                ModelPackageArn=arn,
                ModelApprovalStatus=_APPROVAL_TO_SAGEMAKER[status],
                CustomerMetadataProperties=metadata,
            )
        except Exception as error:
            raise RegistryError(f"UpdateModelPackage failed for {arn}: {error}") from error
        return self._to_version(self._describe(arn), fallback_dir=current.artifact_path)

    def _to_version(self, raw: dict[str, Any], *, fallback_dir: Path | None = None) -> ModelVersion:
        meta = _as_str_map(raw.get("CustomerMetadataProperties"))
        model_name = meta.get("retailops_model_name") or self.model_package_group
        version = meta.get("retailops_version") or _version_from_package(raw)
        status = _status_from(raw, meta)
        registered = raw.get("CreationTime") or raw.get("created_at")
        if isinstance(registered, datetime):
            registered_at = registered if registered.tzinfo else registered.replace(tzinfo=UTC)
        elif registered:
            registered_at = datetime.fromisoformat(str(registered))
        else:
            registered_at = datetime.now(UTC)
        uri = _model_data_url(raw) or self.declared_artifact_uri(model_name, version)
        if fallback_dir is not None:
            artifact_path = fallback_dir
        elif uri.startswith("s3://"):
            artifact_path = Path(uri.removeprefix("s3://"))
        else:
            artifact_path = Path(uri)
        return ModelVersion(
            model_name=model_name,
            version=version,
            status=status,
            registered_at=registered_at,
            artifact_path=artifact_path,
            metrics=_metrics_from(meta),
            data_fingerprint=meta.get("retailops_data_fingerprint") or None,
        )


def _customer_metadata(
    *,
    model_name: str,
    version: str,
    status: ApprovalStatus,
    metrics: dict[str, float] | None,
    data_fingerprint: str | None,
) -> dict[str, str]:
    payload = {
        "retailops_model_name": model_name,
        "retailops_version": version,
        "retailops_approval": status.value,
    }
    if data_fingerprint:
        payload["retailops_data_fingerprint"] = data_fingerprint
    if metrics:
        for key, value in metrics.items():
            payload[f"metric_{key}"] = f"{value:.10g}"
    return payload


def _status_from(raw: dict[str, Any], meta: dict[str, str]) -> ApprovalStatus:
    marked = meta.get("retailops_approval")
    if marked:
        try:
            return ApprovalStatus(marked)
        except ValueError:
            pass
    mapped = _SAGEMAKER_TO_APPROVAL.get(str(raw.get("ModelApprovalStatus") or ""))
    return mapped or ApprovalStatus.candidate


def _metrics_from(meta: dict[str, str]) -> dict[str, float] | None:
    metrics: dict[str, float] = {}
    prefix = "metric_"
    for key, value in meta.items():
        if not key.startswith(prefix):
            continue
        try:
            metrics[key[len(prefix) :]] = float(value)
        except ValueError:
            continue
    return metrics or None


def _model_data_url(raw: dict[str, Any]) -> str | None:
    spec = raw.get("InferenceSpecification")
    if not isinstance(spec, dict):
        return None
    containers = spec.get("Containers")
    if not isinstance(containers, list) or not containers:
        return None
    first = containers[0]
    if not isinstance(first, dict):
        return None
    url = first.get("ModelDataUrl")
    return str(url) if url else None


def _version_from_package(raw: dict[str, Any]) -> str:
    number = raw.get("ModelPackageVersion")
    if isinstance(number, int) or (isinstance(number, str) and str(number).isdigit()):
        return f"v{int(number):03d}"
    raise RegistryError("model package is missing a version label")


def _as_str_map(raw: object) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items() if value is not None}
