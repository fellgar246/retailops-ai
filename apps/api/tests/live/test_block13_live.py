"""Opt-in live AWS checks. Skipped unless RETAILOPS_LIVE_AWS=1."""

from __future__ import annotations

import pytest

from retailops_api.ops.live import (
    documents_bucket,
    expected_account_id,
    preflight,
    smoke_bedrock,
    smoke_s3,
    smoke_textract,
)

pytestmark = pytest.mark.live_aws


def _require_boto3() -> None:
    pytest.importorskip("boto3")


def test_preflight_account_and_bucket() -> None:
    _require_boto3()
    results = {item.name: item for item in preflight()}
    assert results["caller_identity"].ok, results["caller_identity"].detail
    assert expected_account_id() in results["caller_identity"].detail
    assert results["documents_bucket"].ok
    assert documents_bucket() in results["documents_bucket"].detail


def test_s3_roundtrip() -> None:
    _require_boto3()
    result = smoke_s3()
    assert result.ok, result.detail


def test_textract_analyze() -> None:
    _require_boto3()
    result = smoke_textract()
    assert result.ok, result.detail


def test_bedrock_structured_review() -> None:
    _require_boto3()
    result = smoke_bedrock()
    assert result.ok, result.detail
