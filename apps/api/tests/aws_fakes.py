"""In-memory boto3-compatible clients for adapter tests. No network."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from typing import Any


class FakeClientError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        self.response = {"Error": {"Code": code, "Message": message or code}}
        super().__init__(message or code)


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict[str, Any]] = {}

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        bucket = str(kwargs["Bucket"])
        key = str(kwargs["Key"])
        body = kwargs.get("Body", b"")
        if isinstance(body, str):
            body = body.encode("utf-8")
        elif not isinstance(body, (bytes, bytearray)):
            body = bytes(body)
        self.objects[(bucket, key)] = {
            "Body": bytes(body),
            "ContentType": kwargs.get("ContentType"),
            "Metadata": {str(k).lower(): str(v) for k, v in (kwargs.get("Metadata") or {}).items()},
            "ContentLength": len(body),
        }
        return {"ETag": "etag"}

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        stored = self._require(kwargs)
        return {
            "Body": io.BytesIO(stored["Body"]),
            "ContentType": stored.get("ContentType"),
            "Metadata": dict(stored.get("Metadata") or {}),
            "ContentLength": stored["ContentLength"],
        }

    def head_object(self, **kwargs: Any) -> dict[str, Any]:
        stored = self._require(kwargs)
        return {
            "ContentType": stored.get("ContentType"),
            "Metadata": dict(stored.get("Metadata") or {}),
            "ContentLength": stored["ContentLength"],
        }

    def delete_object(self, **kwargs: Any) -> dict[str, Any]:
        bucket = str(kwargs["Bucket"])
        key = str(kwargs["Key"])
        self.objects.pop((bucket, key), None)
        return {}

    def _require(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        pair = (str(kwargs["Bucket"]), str(kwargs["Key"]))
        stored = self.objects.get(pair)
        if stored is None:
            raise FakeClientError("NoSuchKey", f"missing {pair[1]}")
        return stored


class FakeTextract:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def analyze_document(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.response


class FakeBedrock:
    def __init__(
        self,
        payload: object | None = None,
        *,
        error: Exception | None = None,
        fail_times: int = 0,
        fail_error: Exception | None = None,
        wrap_in_content: bool = True,
    ) -> None:
        self.payload = payload
        self.error = error
        self.fail_times = fail_times
        self.fail_error = fail_error
        self.wrap_in_content = wrap_in_content
        self.calls: list[dict[str, Any]] = []

    def invoke_model(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        if self.fail_times > 0:
            self.fail_times -= 1
            raise self.fail_error or FakeClientError("ThrottlingException")
        body: object
        if self.wrap_in_content:
            text = json.dumps(self.payload)
            body = {"content": [{"type": "text", "text": text}]}
        else:
            body = self.payload
        if isinstance(body, (bytes, bytearray)):
            encoded = bytes(body)
        else:
            encoded = json.dumps(body).encode("utf-8")
        return {"body": io.BytesIO(encoded), "contentType": "application/json"}


class FakeSageMaker:
    def __init__(self) -> None:
        self.packages: list[dict[str, Any]] = []

    def create_model_package(self, **kwargs: Any) -> dict[str, Any]:
        version = len(self.packages) + 1
        group = str(kwargs["ModelPackageGroupName"])
        arn = f"arn:aws:sagemaker:us-east-1:123456789012:model-package/{group}/{version}"
        record = {
            **kwargs,
            "ModelPackageArn": arn,
            "ModelPackageVersion": version,
            "CreationTime": datetime.now(UTC),
            "CustomerMetadataProperties": dict(kwargs.get("CustomerMetadataProperties") or {}),
            "ModelApprovalStatus": kwargs.get("ModelApprovalStatus"),
            "InferenceSpecification": kwargs.get("InferenceSpecification"),
        }
        self.packages.append(record)
        return {"ModelPackageArn": arn}

    def list_model_packages(self, **kwargs: Any) -> dict[str, Any]:
        group = kwargs.get("ModelPackageGroupName")
        summaries = []
        for package in self.packages:
            if group and package.get("ModelPackageGroupName") != group:
                continue
            summaries.append(
                {
                    "ModelPackageArn": package["ModelPackageArn"],
                    "ModelPackageVersion": package["ModelPackageVersion"],
                    "ModelApprovalStatus": package.get("ModelApprovalStatus"),
                }
            )
        return {"ModelPackageSummaryList": summaries}

    def describe_model_package(self, **kwargs: Any) -> dict[str, Any]:
        name = str(kwargs.get("ModelPackageName") or "")
        for package in self.packages:
            if package["ModelPackageArn"] == name:
                return dict(package)
        raise FakeClientError("ValidationException", f"unknown package {name}")

    def update_model_package(self, **kwargs: Any) -> dict[str, Any]:
        arn = str(kwargs["ModelPackageArn"])
        for package in self.packages:
            if package["ModelPackageArn"] == arn:
                if "ModelApprovalStatus" in kwargs:
                    package["ModelApprovalStatus"] = kwargs["ModelApprovalStatus"]
                if "CustomerMetadataProperties" in kwargs:
                    package["CustomerMetadataProperties"] = dict(
                        kwargs["CustomerMetadataProperties"]
                    )
                return {"ModelPackageArn": arn}
        raise FakeClientError("ValidationException", f"unknown package {arn}")
