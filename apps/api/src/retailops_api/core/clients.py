"""Lazy constructors for boto3-compatible clients.

Adapters accept an injected client. These helpers are only used when AWS is
enabled and a caller did not supply a stub. They never run during automated
tests.
"""

from __future__ import annotations

from typing import Any

from retailops_api.core.aws import AwsAdapterError


def require_boto3() -> Any:
    try:
        import boto3
    except ImportError as error:
        raise AwsAdapterError(
            "boto3 is required to build a live AWS client; install the optional aws group"
        ) from error
    return boto3


def s3_client(region: str) -> Any:
    return require_boto3().client("s3", region_name=region)


def textract_client(region: str) -> Any:
    return require_boto3().client("textract", region_name=region)


def bedrock_runtime_client(region: str) -> Any:
    return require_boto3().client("bedrock-runtime", region_name=region)


def sagemaker_client(region: str) -> Any:
    return require_boto3().client("sagemaker", region_name=region)
