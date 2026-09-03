from retailops_api.ops.live import EXPECTED_ACCOUNT_ID, preflight, smoke_s3
from tests.aws_fakes import FakeClientError, FakeS3


class _FakeSts:
    def get_caller_identity(self) -> dict[str, str]:
        return {"Account": EXPECTED_ACCOUNT_ID, "Arn": "arn:aws:iam::168629931092:user/test"}


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


def test_s3_smoke_roundtrip_uses_the_storage_adapter() -> None:
    result = smoke_s3(s3=_HeadBucketS3(), bucket="retailops-test", cleanup=True)
    assert result.ok
    assert result.name == "s3_roundtrip"
