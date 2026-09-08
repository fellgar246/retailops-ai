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
from retailops_api.documents.paddleocr import PaddleOCRDocumentAnalyzer
from retailops_api.documents.parse import SheetAnalyzer
from retailops_api.documents.paths import default_document_root
from retailops_api.documents.s3 import S3DocumentStorage
from retailops_api.documents.storage import DocumentStorage, LocalDocumentStorage
from retailops_api.documents.textract import TextractDocumentAnalyzer
from retailops_api.forecasting.registry import LocalModelRegistry, ModelRegistry
from retailops_api.forecasting.sagemaker_registry import SageMakerModelRegistry
from retailops_api.forecasting.sources import default_registry_root
from retailops_api.identity.cognito import CognitoIdentityVerifier, https_key_source
from retailops_api.identity.contract import IdentityVerifier
from retailops_api.identity.local import LocalIdentityVerifier
from retailops_api.identity.types import IdentityConfigError
from retailops_api.review.bedrock import BedrockAIReviewer
from retailops_api.review.contract import AIReviewer
from retailops_api.review.mock import MockAIReviewer
from retailops_api.review.openai import OpenAIReviewer
from retailops_api.review.types import ReviewerError


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
    paddleocr: Any | None = None,
) -> SheetAnalyzer | None:
    if settings.document_ocr_provider == "paddleocr":
        return PaddleOCRDocumentAnalyzer(
            paddleocr,
            device=settings.paddleocr_device,
            max_pages=settings.paddleocr_max_pages,
            max_upload_bytes=settings.max_upload_bytes,
        )
    if settings.document_ocr_provider == "local":
        return None
    aws = settings.aws_config()
    if settings.document_ocr_provider == "textract":
        aws.require_textract()
    if not aws.textract_enabled():
        return None
    aws.require_textract()
    client = textract if textract is not None else textract_client(aws.region)
    return TextractDocumentAnalyzer(client, bounds=aws.document_bounds())


def ai_reviewer_for(
    settings: Settings,
    *,
    bedrock: Any | None = None,
    openai: Any | None = None,
) -> AIReviewer:
    if settings.ai_review_provider == "openai":
        if not settings.openai_model.strip():
            raise ReviewerError("OPENAI_MODEL is required when AI_REVIEW_PROVIDER=openai")
        if openai is None:
            from openai import OpenAI

            key = settings.openai_api_key.get_secret_value().strip()
            if not key:
                raise ReviewerError("OPENAI_API_KEY is required when AI_REVIEW_PROVIDER=openai")
            openai = OpenAI(api_key=key, timeout=settings.openai_timeout_seconds, max_retries=2)
        return OpenAIReviewer(
            openai,
            model_id=settings.openai_model,
            max_output_tokens=settings.openai_max_output_tokens,
            max_prompt_chars=settings.max_prompt_chars,
        )
    if settings.ai_review_provider == "mock":
        return MockAIReviewer()
    aws = settings.aws_config()
    if settings.ai_review_provider == "bedrock":
        aws.require_bedrock()
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


def identity_verifier_for(
    settings: Settings,
    *,
    key_source: Any | None = None,
) -> IdentityVerifier:
    """Build the configured verifier.

    Every provider is resolved from the same explicit setting and each branch
    validates its own configuration before returning. No branch falls through
    to another provider, so a misconfigured deployment fails loudly instead of
    quietly authenticating against a development key.
    """

    provider = settings.auth_provider
    if provider == "local":
        secret = settings.auth_local_secret.get_secret_value().strip()
        if not secret:
            raise IdentityConfigError("AUTH_LOCAL_SECRET is required when AUTH_PROVIDER=local")
        return LocalIdentityVerifier(secret, ttl_seconds=settings.auth_local_ttl_seconds)
    if provider == "cognito":
        issuer = settings.cognito_issuer
        if not issuer:
            raise IdentityConfigError(
                "COGNITO_USER_POOL_ID and a region are required when AUTH_PROVIDER=cognito"
            )
        audience = settings.cognito_client_id.strip()
        if not audience:
            raise IdentityConfigError("COGNITO_CLIENT_ID is required when AUTH_PROVIDER=cognito")
        source = (
            key_source if key_source is not None else https_key_source(settings.cognito_jwks_uri)
        )
        return CognitoIdentityVerifier(issuer=issuer, audience=audience, key_source=source)
    raise IdentityConfigError(f"unknown identity provider {provider!r}")


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
