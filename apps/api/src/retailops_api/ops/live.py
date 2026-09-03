"""Bounded live AWS smoke checks for S3, Textract and Bedrock.

These helpers stay unused unless a caller opts in. Automated tests inject
stubs. The CLI never runs as part of ``make check-app``.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from retailops_api.core.aws import (
    DEFAULT_BEDROCK_INFERENCE_PROFILE_ID,
    DEFAULT_BEDROCK_MODEL_ID,
    AwsConfig,
)
from retailops_api.core.clients import (
    bedrock_client,
    bedrock_runtime_client,
    s3_client,
    textract_client,
)
from retailops_api.documents.keys import LIVE_SMOKE_PREFIX, source_object_key
from retailops_api.documents.s3 import S3DocumentStorage
from retailops_api.documents.textract import TextractDocumentAnalyzer
from retailops_api.documents.textract_corpus import (
    CORPUS_CASES,
    case_bytes,
    synthetic_textract_table,
)
from retailops_api.review.bedrock import BedrockAIReviewer
from retailops_api.review.contract import build_request
from retailops_api.review.types import ReconciliationExplanationInput, ReviewType

EXPECTED_ACCOUNT_ID = "168629931092"
DEFAULT_DOCUMENTS_BUCKET = "retailops-ai-dev-documents-168629931092"
DEFAULT_REGION = "us-east-1"
SMOKE_FILENAME = "block13-smoke.txt"


@dataclass(frozen=True)
class SmokeResult:
    name: str
    ok: bool
    detail: str


def preflight(
    *,
    region: str = DEFAULT_REGION,
    bucket: str = DEFAULT_DOCUMENTS_BUCKET,
    sts: Any | None = None,
    s3: Any | None = None,
    textract: Any | None = None,
    bedrock: Any | None = None,
) -> list[SmokeResult]:
    results: list[SmokeResult] = []
    client = sts or _sts_client(region)
    identity = client.get_caller_identity()
    account = str(identity.get("Account") or "")
    results.append(
        SmokeResult(
            "caller_identity",
            account == EXPECTED_ACCOUNT_ID,
            f"account={account} arn={identity.get('Arn')}",
        )
    )
    s3_client_obj = s3 or s3_client(region)
    s3_client_obj.head_bucket(Bucket=bucket)
    results.append(SmokeResult("documents_bucket", True, f"bucket={bucket} region={region}"))
    results.append(_probe_textract(textract or textract_client(region)))
    results.append(_probe_bedrock_catalog(bedrock or bedrock_client(region)))
    return results


def smoke_s3(
    *,
    bucket: str = DEFAULT_DOCUMENTS_BUCKET,
    region: str = DEFAULT_REGION,
    prefix: str = LIVE_SMOKE_PREFIX,
    s3: Any | None = None,
    cleanup: bool = True,
) -> SmokeResult:
    store = S3DocumentStorage(s3 or s3_client(region), bucket=bucket, prefix=prefix)
    payload = b"retailops-block13-s3-smoke\n"
    stored = store.save(payload, filename=SMOKE_FILENAME, media_type="text/plain")
    try:
        meta = store.metadata(stored.key)
        body = store.read(stored.key)
        checksum = hashlib.sha256(body).hexdigest()
        ok = body == payload and meta.checksum == stored.checksum == checksum
        return SmokeResult(
            "s3_roundtrip",
            ok,
            f"key={stored.key} object={store.object_key_for(stored.key)} checksum={checksum}",
        )
    finally:
        if cleanup:
            store.delete(stored.key)


def smoke_textract(
    *,
    bucket: str = DEFAULT_DOCUMENTS_BUCKET,
    region: str = DEFAULT_REGION,
    prefix: str = LIVE_SMOKE_PREFIX,
    s3: Any | None = None,
    textract: Any | None = None,
    cleanup: bool = True,
) -> SmokeResult:
    case = CORPUS_CASES[0]
    data = case_bytes(case)
    store = S3DocumentStorage(s3 or s3_client(region), bucket=bucket, prefix=prefix)
    stored = store.save(data, filename="clean-supplier.pdf", media_type="application/pdf")
    analyzer = TextractDocumentAnalyzer(textract or textract_client(region))
    try:
        parsed = analyzer.analyze_s3(
            bucket=bucket,
            key=store.object_key_for(stored.key),
            filename="clean-supplier.pdf",
        )
        ok = len(parsed.rows) >= 1 and parsed.extraction is not None
        sku = parsed.rows[0].supplier_sku if parsed.rows else None
        return SmokeResult("textract_analyze", ok, f"rows={len(parsed.rows)} sku={sku}")
    finally:
        if cleanup:
            store.delete(stored.key)


def smoke_bedrock(
    *,
    region: str = DEFAULT_REGION,
    model_id: str = DEFAULT_BEDROCK_INFERENCE_PROFILE_ID,
    bedrock: Any | None = None,
) -> SmokeResult:
    reviewer = BedrockAIReviewer(
        bedrock or bedrock_runtime_client(region),
        model_id=model_id,
        region=region,
        max_tokens=256,
        temperature=0.0,
    )
    request = build_request(
        ReviewType.reconciliation_explanation,
        ReconciliationExplanationInput(
            exception_code="qty_invoice_over",
            severity="warning",
            message="Invoiced quantity exceeds received quantity.",
            expected_value="10",
            actual_value="12",
            financial_impact=Decimal("20.00"),
        ),
        case_id="block13-smoke",
    )
    result = reviewer.review(request)
    usage = reviewer.last_usage
    tokens = usage.total_tokens if usage else None
    return SmokeResult(
        "bedrock_converse",
        bool(result.summary) and result.provider == "bedrock",
        f"model={result.model} action={result.recommended_action} tokens={tokens}",
    )


def default_aws_config(
    *,
    enabled: bool = True,
    bucket: str = DEFAULT_DOCUMENTS_BUCKET,
    prefix: str = LIVE_SMOKE_PREFIX,
    model_id: str = DEFAULT_BEDROCK_MODEL_ID,
    inference_profile_id: str = DEFAULT_BEDROCK_INFERENCE_PROFILE_ID,
) -> AwsConfig:
    return AwsConfig(
        enabled=enabled,
        region=DEFAULT_REGION,
        account_id=EXPECTED_ACCOUNT_ID,
        environment_name="dev",
        resource_prefix="retailops-ai",
        documents_bucket=bucket,
        documents_prefix=prefix,
        bedrock_model_id=model_id,
        bedrock_inference_profile_id=inference_profile_id,
        use_s3_storage=True,
        use_textract=True,
        use_bedrock=True,
    )


def source_key_example(logical_key: str, *, prefix: str = LIVE_SMOKE_PREFIX) -> str:
    return source_object_key(logical_key, prefix=prefix)


def offline_textract_payload() -> dict[str, Any]:
    return synthetic_textract_table(CORPUS_CASES[0].rows)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.command == "preflight":
            items = preflight(region=args.region, bucket=args.bucket)
            for item in items:
                _print(item)
            return 0 if all(item.ok for item in items) else 1
        if args.command == "s3":
            result = smoke_s3(bucket=args.bucket, region=args.region, cleanup=not args.keep)
            _print(result)
            return 0 if result.ok else 1
        if args.command == "textract":
            result = smoke_textract(bucket=args.bucket, region=args.region, cleanup=not args.keep)
            _print(result)
            return 0 if result.ok else 1
        if args.command == "bedrock":
            result = smoke_bedrock(region=args.region, model_id=args.model_id)
            _print(result)
            return 0 if result.ok else 1
        raise ValueError(f"unknown command {args.command}")
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


_TEXTRACT_REACHABLE_CODES = frozenset(
    {
        "InvalidJobIdException",
        "InvalidParameterException",
        "ValidationException",
        "ProvisionedThroughputExceededException",
    }
)
_SERVICE_NOT_READY_CODES = frozenset(
    {
        "SubscriptionRequiredException",
        "AccessDeniedException",
        "UnrecognizedClientException",
    }
)
_HAIKU_MARKER = "claude-haiku-4-5"


def _probe_textract(textract: Any) -> SmokeResult:
    try:
        textract.get_document_analysis(JobId="00000000-0000-0000-0000-000000000000")
    except Exception as error:
        code = _client_error_code(error)
        if code in _SERVICE_NOT_READY_CODES:
            return SmokeResult("textract_access", False, f"{code}: {error}")
        if code in _TEXTRACT_REACHABLE_CODES:
            return SmokeResult("textract_access", True, f"reachable ({code})")
        return SmokeResult("textract_access", False, f"{code or 'unknown'}: {error}")
    return SmokeResult("textract_access", True, "GetDocumentAnalysis accepted a probe job id")


def _probe_bedrock_catalog(bedrock: Any) -> SmokeResult:
    try:
        models = bedrock.list_foundation_models()
        profiles = bedrock.list_inference_profiles()
    except Exception as error:
        code = _client_error_code(error)
        return SmokeResult("bedrock_model_access", False, f"{code or 'unknown'}: {error}")
    model_ok = _catalog_contains(models.get("modelSummaries"), "modelId", _HAIKU_MARKER)
    profile_ok = _catalog_contains(
        profiles.get("inferenceProfileSummaries"), "inferenceProfileId", _HAIKU_MARKER
    )
    return SmokeResult(
        "bedrock_model_access",
        model_ok and profile_ok,
        f"foundation={model_ok} inference_profile={profile_ok}",
    )


def _catalog_contains(items: object, field: str, marker: str) -> bool:
    if not isinstance(items, list):
        return False
    return any(isinstance(item, dict) and marker in str(item.get(field) or "") for item in items)


def _client_error_code(error: Exception) -> str:
    response = getattr(error, "response", None)
    if isinstance(response, dict):
        payload = response.get("Error")
        if isinstance(payload, dict):
            return str(payload.get("Code") or "")
    return ""


def _sts_client(region: str) -> Any:
    from retailops_api.core.clients import require_boto3

    return require_boto3().client("sts", region_name=region)


def _print(result: SmokeResult) -> None:
    flag = "ok" if result.ok else "fail"
    print(f"{flag}  {result.name}  {result.detail}")


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="retailops-aws-smoke")
    parser.add_argument("command", choices=("preflight", "s3", "textract", "bedrock"))
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--bucket", default=DEFAULT_DOCUMENTS_BUCKET)
    parser.add_argument("--model-id", default=DEFAULT_BEDROCK_INFERENCE_PROFILE_ID)
    parser.add_argument("--keep", action="store_true", help="Leave smoke objects in the bucket.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
