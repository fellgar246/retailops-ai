"""Lazy constructors for boto3-compatible clients.

Adapters accept an injected client. These helpers are only used when AWS is
enabled and a caller did not supply a stub. They never run during automated
tests.
"""

from __future__ import annotations

from typing import Any

from retailops_api.core.aws import DEFAULT_BEDROCK_TIMEOUT_SECONDS, AwsAdapterError


def require_boto3() -> Any:
    try:
        import boto3
    except ImportError as error:
        raise AwsAdapterError(
            "boto3 is required to build a live AWS client; install the optional aws group"
        ) from error
    return boto3


def _client_config(*, timeout_seconds: float, extra_retries: int = 0) -> Any:
    from botocore.config import Config

    return Config(
        connect_timeout=min(3.0, timeout_seconds),
        read_timeout=timeout_seconds,
        retries={"max_attempts": extra_retries, "mode": "standard"},
    )


def s3_client(region: str, *, timeout_seconds: float = 10.0) -> Any:
    return require_boto3().client(
        "s3",
        region_name=region,
        config=_client_config(timeout_seconds=timeout_seconds),
    )


def sqs_client(region: str, *, timeout_seconds: float = 25.0) -> Any:
    """Long polling waits up to twenty seconds, so the read timeout allows it."""

    return require_boto3().client(
        "sqs",
        region_name=region,
        config=_client_config(timeout_seconds=timeout_seconds),
    )


def textract_client(region: str, *, timeout_seconds: float = 30.0) -> Any:
    return require_boto3().client(
        "textract",
        region_name=region,
        config=_client_config(timeout_seconds=timeout_seconds),
    )


def bedrock_client(region: str, *, timeout_seconds: float = 10.0) -> Any:
    return require_boto3().client(
        "bedrock",
        region_name=region,
        config=_client_config(timeout_seconds=timeout_seconds),
    )


def bedrock_runtime_client(
    region: str, *, timeout_seconds: float = DEFAULT_BEDROCK_TIMEOUT_SECONDS
) -> Any:
    return require_boto3().client(
        "bedrock-runtime",
        region_name=region,
        config=_client_config(timeout_seconds=timeout_seconds),
    )


def sagemaker_client(region: str, *, timeout_seconds: float = 30.0) -> Any:
    return require_boto3().client(
        "sagemaker",
        region_name=region,
        config=_client_config(timeout_seconds=timeout_seconds),
    )
