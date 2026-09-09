from collections.abc import Iterator

import pytest

from retailops_api.core.aws import AwsConfigError
from retailops_api.core.config import get_settings
from retailops_api.ops.live import preflight, smoke_s3
from tests.aws_fakes import FakeClientError, FakeS3

#: Stand-in for the account an operator states they are pointing at.
TEST_ACCOUNT_ID = "000000000000"
TEST_BUCKET = "retailops-test-documents"


@pytest.fixture(autouse=True)
def smoke_configuration(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The smoke run reads the account and bucket from configuration."""

    monkeypatch.setenv("AWS_ACCOUNT_ID", TEST_ACCOUNT_ID)
    monkeypatch.setenv("AWS_DOCUMENTS_BUCKET", TEST_BUCKET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _FakeSts:
    def get_caller_identity(self) -> dict[str, str]:
        return {
            "Account": TEST_ACCOUNT_ID,
            "Arn": f"arn:aws:iam::{TEST_ACCOUNT_ID}:user/test",
        }


class _FakeStsOtherAccount:
    def get_caller_identity(self) -> dict[str, str]:
        return {"Account": "999999999999", "Arn": "arn:aws:iam::999999999999:user/test"}


class _FakeTextractReady:
    def get_document_analysis(self, **_kwargs: object) -> dict[str, object]:
        raise FakeClientError("InvalidJobIdException", "unknown job")


class _FakeTextractBlocked:
    def get_document_analysis(self, **_kwargs: object) -> dict[str, object]:
        raise FakeClientError("SubscriptionRequiredException", "needs a subscription")


class _FakeBedrockCatalog:
    def list_foundation_models(self) -> dict[str, object]:
        return {"modelSummaries": [{"modelId": "anthropic.claude-haiku-4-5-20251001-v1:0"}]}

    def list_inference_profiles(self) -> dict[str, object]:
        return {
            "inferenceProfileSummaries": [
                {"inferenceProfileId": "us.anthropic.claude-haiku-4-5-20251001-v1:0"}
            ]
        }


class _HeadBucketS3(FakeS3):
    def head_bucket(self, **_kwargs: object) -> dict[str, object]:
        return {}


def test_preflight_reports_account_bucket_and_service_catalog() -> None:
    results = {
        item.name: item
        for item in preflight(
            sts=_FakeSts(),
            s3=_HeadBucketS3(),
            textract=_FakeTextractReady(),
            bedrock=_FakeBedrockCatalog(),
        )
    }
    assert results["caller_identity"].ok
    assert results["documents_bucket"].ok
    assert results["textract_access"].ok
    assert results["bedrock_model_access"].ok


def test_preflight_flags_textract_subscription() -> None:
    results = {
        item.name: item
        for item in preflight(
            sts=_FakeSts(),
            s3=_HeadBucketS3(),
            textract=_FakeTextractBlocked(),
            bedrock=_FakeBedrockCatalog(),
        )
    }
    assert results["textract_access"].ok is False
    assert "SubscriptionRequiredException" in results["textract_access"].detail


def test_preflight_refuses_to_vouch_for_another_account() -> None:
    """The guard is the point of the check: a run against the wrong account
    must be reported, not quietly accepted."""

    results = {
        item.name: item
        for item in preflight(
            sts=_FakeStsOtherAccount(),
            s3=_HeadBucketS3(),
            textract=_FakeTextractReady(),
            bedrock=_FakeBedrockCatalog(),
        )
    }
    assert results["caller_identity"].ok is False
    assert "999999999999" in results["caller_identity"].detail


def test_the_account_must_be_stated_before_a_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_ACCOUNT_ID", "")
    get_settings.cache_clear()

    with pytest.raises(AwsConfigError, match="AWS_ACCOUNT_ID"):
        preflight(sts=_FakeSts(), s3=_HeadBucketS3())


def test_the_bucket_must_be_stated_before_a_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_DOCUMENTS_BUCKET", "")
    get_settings.cache_clear()

    with pytest.raises(AwsConfigError, match="AWS_DOCUMENTS_BUCKET"):
        smoke_s3(s3=_HeadBucketS3())


def test_s3_smoke_roundtrip_uses_the_storage_adapter() -> None:
    result = smoke_s3(s3=_HeadBucketS3(), bucket="retailops-test", cleanup=True)
    assert result.ok
    assert result.name == "s3_roundtrip"
