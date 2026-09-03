"""Choose local or cloud implementations from settings.

AWS remains off unless ``aws_enabled`` and the matching feature flag are
both set. Callers receive the same protocols they already use.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from retailops_api.core.aws import AwsConfig
from retailops_api.core.clients import (
    bedrock_runtime_client,
    s3_client,
    sagemaker_client,
    textract_client,
)
from retailops_api.core.config import Settings
from retailops_api.documents.paths import default_document_root
from retailops_api.documents.s3 import S3DocumentStorage
from retailops_api.documents.storage import DocumentStorage, LocalDocumentStorage
from retailops_api.documents.textract import TextractDocumentAnalyzer
from retailops_api.forecasting.registry import LocalModelRegistry, ModelRegistry
from retailops_api.forecasting.sagemaker_registry import SageMakerModelRegistry
from retailops_api.forecasting.sources import default_registry_root
from retailops_api.review.bedrock import BedrockAIReviewer
from retailops_api.review.contract import AIReviewer
from retailops_api.review.mock import MockAIReviewer


def document_storage_for(
    settings: Settings,
    *,
    s3: Any | None = None,
    root: Path | None = None,
) -> DocumentStorage:
    aws = settings.aws_config()
    if not aws.s3_enabled():
        return LocalDocumentStorage(root or _document_root(settings))
    aws.require_s3()
    client = s3 if s3 is not None else s3_client(aws.region)
    return S3DocumentStorage(
        client,
        bucket=aws.documents_bucket,
        prefix=aws.documents_prefix,
        max_upload_bytes=aws.max_upload_bytes,
    )


def document_analyzer_for(
    settings: Settings,
    *,
    textract: Any | None = None,
) -> TextractDocumentAnalyzer | None:
    aws = settings.aws_config()
    if not aws.textract_enabled():
        return None
    aws.require_textract()
    client = textract if textract is not None else textract_client(aws.region)
    return TextractDocumentAnalyzer(client, bounds=aws.document_bounds())


def ai_reviewer_for(
    settings: Settings,
    *,
    bedrock: Any | None = None,
) -> AIReviewer:
    aws = settings.aws_config()
    if not aws.bedrock_enabled():
        return MockAIReviewer()
    aws.require_bedrock()
    client = (
        bedrock
        if bedrock is not None
        else bedrock_runtime_client(aws.region, timeout_seconds=aws.bedrock_timeout_seconds)
    )
    return BedrockAIReviewer(
        client,
        model_id=aws.invocation_model_id(),
        region=aws.region,
        max_tokens=aws.bedrock_max_tokens,
        temperature=aws.bedrock_temperature,
        max_prompt_chars=aws.max_prompt_chars,
    )


def model_registry_for(
    settings: Settings,
    *,
    sagemaker: Any | None = None,
    root: Path | None = None,
) -> ModelRegistry:
    aws = settings.aws_config()
    if not aws.sagemaker_registry_enabled():
        return LocalModelRegistry(root or default_registry_root())
    aws.require_sagemaker()
    client = sagemaker if sagemaker is not None else sagemaker_client(aws.region)
    return SageMakerModelRegistry(
        client,
        model_package_group=aws.sagemaker_model_group,
        artifact_bucket=aws.documents_bucket,
        artifact_prefix=aws.sagemaker_artifact_prefix,
        region=aws.region,
        account_id=aws.account_id,
    )


def _document_root(settings: Settings) -> Path:
    configured = settings.document_storage_root.strip()
    if configured:
        return Path(configured)
    return default_document_root()


def aws_from_settings(settings: Settings) -> AwsConfig:
    return settings.aws_config()
