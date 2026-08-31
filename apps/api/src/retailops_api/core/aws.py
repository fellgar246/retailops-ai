"""Typed AWS configuration boundary.

Cloud adapters stay off unless ``enabled`` is true *and* the matching
feature flag is set. Local development never needs an account, region
credentials or a live client.
"""

from __future__ import annotations

from dataclasses import dataclass


class AwsConfigError(ValueError):
    """AWS settings are inconsistent or missing a required reference."""


class AwsAdapterError(RuntimeError):
    """A cloud adapter could not be constructed or a client call failed."""


@dataclass(frozen=True)
class AwsConfig:
    """Resolved AWS names, storage references and adapter feature flags."""

    enabled: bool = False
    region: str = "us-east-1"
    account_id: str = ""
    environment_name: str = "local"
    resource_prefix: str = "retailops"
    documents_bucket: str = ""
    documents_prefix: str = "documents"
    bedrock_model_id: str = ""
    sagemaker_model_group: str = "category-forecast"
    sagemaker_artifact_prefix: str = "models"
    use_s3_storage: bool = False
    use_textract: bool = False
    use_bedrock: bool = False
    use_sagemaker_registry: bool = False

    def resource_name(self, suffix: str) -> str:
        """``{prefix}-{environment}-{suffix}`` for buckets, queues and roles."""
        parts = [part for part in (self.resource_prefix, self.environment_name, suffix) if part]
        return "-".join(parts)

    def s3_enabled(self) -> bool:
        return self.enabled and self.use_s3_storage

    def textract_enabled(self) -> bool:
        return self.enabled and self.use_textract

    def bedrock_enabled(self) -> bool:
        return self.enabled and self.use_bedrock

    def sagemaker_registry_enabled(self) -> bool:
        return self.enabled and self.use_sagemaker_registry

    def require_s3(self) -> None:
        if not self.s3_enabled():
            raise AwsConfigError("S3 document storage is disabled")
        if not self.documents_bucket.strip():
            raise AwsConfigError("aws_documents_bucket is required when S3 storage is enabled")

    def require_bedrock(self) -> None:
        if not self.bedrock_enabled():
            raise AwsConfigError("Bedrock review is disabled")
        if not self.bedrock_model_id.strip():
            raise AwsConfigError("aws_bedrock_model_id is required when Bedrock review is enabled")

    def require_sagemaker(self) -> None:
        if not self.sagemaker_registry_enabled():
            raise AwsConfigError("SageMaker model registry is disabled")
        if not self.sagemaker_model_group.strip():
            raise AwsConfigError(
                "aws_sagemaker_model_group is required when the SageMaker registry is enabled"
            )
        if not self.documents_bucket.strip():
            raise AwsConfigError(
                "aws_documents_bucket is required when the SageMaker registry is enabled "
                "(artifact URI prefix only; this adapter does not upload files)"
            )
