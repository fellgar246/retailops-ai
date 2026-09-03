"""Typed AWS configuration boundary.

Cloud adapters stay off unless ``enabled`` is true *and* the matching
feature flag is set. Local development never needs an account, region
credentials or a live client. Domain services read this object; they do
not inspect environment variables.
"""

from __future__ import annotations

from dataclasses import dataclass

from retailops_api.core.limits import (
    DEFAULT_DOCUMENTS_PREFIX,
    DEFAULT_MAX_PROMPT_CHARS,
    DEFAULT_MAX_TEXTRACT_SYNC_PAGES,
    DEFAULT_MAX_UPLOAD_BYTES,
    DocumentBounds,
)


class AwsConfigError(ValueError):
    """AWS settings are inconsistent or missing a required reference."""


class AwsAdapterError(RuntimeError):
    """A cloud adapter could not be constructed or a client call failed."""


DEFAULT_BEDROCK_MODEL_ID = "anthropic.claude-haiku-4-5-20251001-v1:0"
DEFAULT_BEDROCK_INFERENCE_PROFILE_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
DEFAULT_BEDROCK_MAX_TOKENS = 1024
DEFAULT_BEDROCK_TEMPERATURE = 0.0
DEFAULT_BEDROCK_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class AwsConfig:
    """Resolved AWS names, storage references and adapter feature flags."""

    enabled: bool = False
    region: str = "us-east-1"
    account_id: str = ""
    environment_name: str = "local"
    resource_prefix: str = "retailops"
    documents_bucket: str = ""
    documents_prefix: str = DEFAULT_DOCUMENTS_PREFIX
    bedrock_model_id: str = ""
    bedrock_inference_profile_id: str = ""
    bedrock_max_tokens: int = DEFAULT_BEDROCK_MAX_TOKENS
    bedrock_temperature: float = DEFAULT_BEDROCK_TEMPERATURE
    bedrock_timeout_seconds: float = DEFAULT_BEDROCK_TIMEOUT_SECONDS
    sagemaker_model_group: str = "category-forecast"
    sagemaker_artifact_prefix: str = "models"
    use_s3_storage: bool = False
    use_textract: bool = False
    use_bedrock: bool = False
    use_sagemaker_registry: bool = False
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES
    max_textract_sync_pages: int = DEFAULT_MAX_TEXTRACT_SYNC_PAGES
    max_prompt_chars: int = DEFAULT_MAX_PROMPT_CHARS

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

    def invocation_model_id(self) -> str:
        """Inference profile wins; otherwise the foundation-model id."""
        return self.bedrock_inference_profile_id.strip() or self.bedrock_model_id.strip()

    def document_bounds(self) -> DocumentBounds:
        return DocumentBounds(
            max_upload_bytes=self.max_upload_bytes,
            max_textract_sync_pages=self.max_textract_sync_pages,
            max_prompt_chars=self.max_prompt_chars,
        )

    def require_s3(self) -> None:
        if not self.s3_enabled():
            raise AwsConfigError("S3 document storage is disabled")
        if not self.documents_bucket.strip():
            raise AwsConfigError("aws_documents_bucket is required when S3 storage is enabled")

    def require_textract(self) -> None:
        if not self.textract_enabled():
            raise AwsConfigError("Textract analysis is disabled")

    def require_bedrock(self) -> None:
        if not self.bedrock_enabled():
            raise AwsConfigError("Bedrock review is disabled")
        if not self.invocation_model_id():
            raise AwsConfigError(
                "bedrock_model_id or bedrock_inference_profile_id is required "
                "when Bedrock review is enabled"
            )

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
