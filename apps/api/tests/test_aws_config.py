from pathlib import Path

import pytest

from retailops_api.core.adapters import ai_reviewer_for, document_storage_for, model_registry_for
from retailops_api.core.aws import AwsConfig, AwsConfigError
from retailops_api.core.config import Settings
from retailops_api.documents.s3 import S3DocumentStorage
from retailops_api.documents.storage import LocalDocumentStorage
from retailops_api.forecasting.registry import LocalModelRegistry
from retailops_api.forecasting.sagemaker_registry import SageMakerModelRegistry
from retailops_api.review.bedrock import BedrockAIReviewer
from retailops_api.review.mock import MockAIReviewer
from tests.aws_fakes import FakeS3, FakeSageMaker


def test_aws_field_defaults_keep_cloud_adapters_off() -> None:
    fields = Settings.model_fields
    assert fields["aws_enabled"].default is False
    assert fields["aws_use_s3_storage"].default is False
    assert fields["aws_use_textract"].default is False
    assert fields["aws_use_bedrock"].default is False
    assert fields["aws_use_sagemaker_registry"].default is False
    assert fields["aws_region"].default == "us-east-1"
    assert fields["aws_resource_prefix"].default == "retailops"


def test_aws_config_builds_resource_names() -> None:
    config = AwsConfig(
        enabled=True,
        environment_name="dev",
        resource_prefix="retailops",
        account_id="123456789012",
    )
    assert config.resource_name("documents") == "retailops-dev-documents"
    assert config.s3_enabled() is False


def test_feature_flags_do_nothing_when_aws_is_disabled(tmp_path: Path) -> None:
    settings = Settings(
        aws_enabled=False,
        aws_use_s3_storage=True,
        aws_use_bedrock=True,
        aws_use_sagemaker_registry=True,
        aws_documents_bucket="bucket",
        aws_bedrock_model_id="model",
        document_storage_root=str(tmp_path),
    )
    assert isinstance(document_storage_for(settings), LocalDocumentStorage)
    assert isinstance(ai_reviewer_for(settings), MockAIReviewer)
    assert isinstance(model_registry_for(settings, root=tmp_path), LocalModelRegistry)


def test_s3_factory_requires_a_bucket_when_enabled() -> None:
    settings = Settings(aws_enabled=True, aws_use_s3_storage=True, aws_documents_bucket="")
    with pytest.raises(AwsConfigError, match="aws_documents_bucket"):
        document_storage_for(settings, s3=FakeS3())


def test_s3_factory_uses_injected_client_when_enabled() -> None:
    settings = Settings(
        aws_enabled=True,
        aws_use_s3_storage=True,
        aws_documents_bucket="retailops-dev-documents",
        aws_documents_prefix="docs",
    )
    store = document_storage_for(settings, s3=FakeS3())
    assert isinstance(store, S3DocumentStorage)
    assert store.bucket == "retailops-dev-documents"
    assert store.prefix == "docs"


def test_bedrock_factory_requires_a_model_id() -> None:
    settings = Settings(aws_enabled=True, aws_use_bedrock=True, aws_bedrock_model_id="")
    with pytest.raises(AwsConfigError, match="aws_bedrock_model_id"):
        ai_reviewer_for(settings, bedrock=object())


def test_bedrock_factory_returns_bedrock_reviewer() -> None:
    settings = Settings(
        aws_enabled=True,
        aws_use_bedrock=True,
        aws_bedrock_model_id="anthropic.claude-sonnet-4-20250514-v1:0",
    )
    reviewer = ai_reviewer_for(settings, bedrock=object())
    assert isinstance(reviewer, BedrockAIReviewer)
    assert reviewer.provider_id == "bedrock"


def test_sagemaker_factory_uses_injected_client(tmp_path: Path) -> None:
    settings = Settings(
        aws_enabled=True,
        aws_use_sagemaker_registry=True,
        aws_documents_bucket="retailops-dev-documents",
        aws_sagemaker_model_group="category-forecast",
    )
    registry = model_registry_for(settings, sagemaker=FakeSageMaker(), root=tmp_path)
    assert isinstance(registry, SageMakerModelRegistry)
