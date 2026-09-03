"""S3 implementation of ``DocumentStorage``.

Callers keep using generated 32-hex keys. The bucket object key is
``{prefix}/{key}/source/payload``. Filename, media type and checksum live
in object metadata. The client is injected so tests never touch a live
bucket.
"""

from __future__ import annotations

import io
from typing import Any, BinaryIO, Protocol

from retailops_api.core.aws import AwsAdapterError
from retailops_api.core.limits import DEFAULT_MAX_UPLOAD_BYTES
from retailops_api.documents.keys import (
    DEFAULT_DOCUMENTS_PREFIX,
    SOURCE_LEAF,
    legacy_object_key,
    normalize_prefix,
    source_object_key,
    validate_logical_key,
)
from retailops_api.documents.storage import (
    CHECKSUM_ALGORITHM,
    ObjectMetadata,
    StoredObject,
    safe_filename,
    sha256_hex,
)
from retailops_api.documents.types import StorageError

_NOT_FOUND_CODES = frozenset({"404", "NoSuchKey", "NotFound", "NoSuchBucket"})


class S3Client(Protocol):
    """Subset of a boto3 S3 client used by this adapter."""

    def put_object(self, **kwargs: Any) -> dict[str, Any]: ...

    def get_object(self, **kwargs: Any) -> dict[str, Any]: ...

    def head_object(self, **kwargs: Any) -> dict[str, Any]: ...

    def delete_object(self, **kwargs: Any) -> dict[str, Any]: ...


class S3DocumentStorage:
    """Put / get / head / delete against an injectable S3-compatible client."""

    def __init__(
        self,
        client: S3Client,
        *,
        bucket: str,
        prefix: str = DEFAULT_DOCUMENTS_PREFIX,
        max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    ) -> None:
        if not bucket.strip():
            raise StorageError("S3 bucket name is required")
        self.client = client
        self.bucket = bucket.strip()
        self.prefix = normalize_prefix(prefix)
        self.max_upload_bytes = max_upload_bytes

    def save(self, data: bytes, *, filename: str, media_type: str) -> StoredObject:
        if len(data) > self.max_upload_bytes:
            raise StorageError(f"document exceeds max upload size ({self.max_upload_bytes} bytes)")
        key = self._unused_key()
        stored = StoredObject(
            key=key,
            checksum=sha256_hex(data),
            size=len(data),
            media_type=media_type,
            filename=safe_filename(filename),
        )
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=self._object_key(key),
                Body=data,
                ContentType=media_type,
                Metadata={
                    "filename": stored.filename,
                    "media-type": stored.media_type,
                    "checksum": stored.checksum,
                    "checksum-algorithm": CHECKSUM_ALGORITHM,
                    "logical-key": stored.key,
                },
            )
        except Exception as error:
            raise _wrap_client_error("put", key, error) from error
        return stored

    def read(self, key: str) -> bytes:
        object_key = self._resolve_object_key(key)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=object_key)
            return _read_body(response.get("Body"))
        except Exception as error:
            if _is_not_found(error):
                raise StorageError(f"unknown storage key {key!r}") from error
            raise _wrap_client_error("get", key, error) from error

    def open(self, key: str) -> BinaryIO:
        return io.BytesIO(self.read(key))

    def exists(self, key: str) -> bool:
        return self._locate_object_key(key) is not None

    def metadata(self, key: str) -> ObjectMetadata:
        object_key = self._resolve_object_key(key)
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=object_key)
        except Exception as error:
            if _is_not_found(error):
                raise StorageError(f"unknown storage key {key!r}") from error
            raise _wrap_client_error("head", key, error) from error
        meta = _metadata_map(response.get("Metadata"))
        size_raw = response.get("ContentLength")
        size = int(size_raw) if isinstance(size_raw, (int, str)) else 0
        checksum = meta.get("checksum") or ""
        if not checksum:
            checksum = sha256_hex(self.read(key))
        return ObjectMetadata(
            key=key,
            checksum=checksum,
            size=size,
            media_type=meta.get("media-type") or _as_optional_str(response.get("ContentType")),
            filename=meta.get("filename"),
        )

    def delete(self, key: str) -> None:
        object_key = self._resolve_object_key(key)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=object_key)
        except Exception as error:
            raise _wrap_client_error("delete", key, error) from error

    def object_key_for(self, key: str) -> str:
        return self._object_key(key)

    def _unused_key(self) -> str:
        from uuid import uuid4

        for _ in range(8):
            key = uuid4().hex
            if not self.exists(key):
                return key
        raise StorageError("could not allocate a unique storage key")

    def _object_key(self, key: str) -> str:
        return source_object_key(key, prefix=self.prefix, leaf=SOURCE_LEAF)

    def _candidate_keys(self, key: str) -> tuple[str, ...]:
        validate_logical_key(key)
        return (
            source_object_key(key, prefix=self.prefix, leaf=SOURCE_LEAF),
            legacy_object_key(key, prefix=self.prefix),
        )

    def _locate_object_key(self, key: str) -> str | None:
        for candidate in self._candidate_keys(key):
            try:
                self.client.head_object(Bucket=self.bucket, Key=candidate)
            except Exception as error:
                if _is_not_found(error):
                    continue
                raise _wrap_client_error("head", key, error) from error
            else:
                return candidate
        return None

    def _resolve_object_key(self, key: str) -> str:
        located = self._locate_object_key(key)
        if located is None:
            raise StorageError(f"unknown storage key {key!r}")
        return located


def _read_body(body: object) -> bytes:
    if body is None:
        return b""
    if isinstance(body, (bytes, bytearray)):
        return bytes(body)
    read = getattr(body, "read", None)
    if callable(read):
        payload = read()
        if isinstance(payload, (bytes, bytearray)):
            return bytes(payload)
        if isinstance(payload, str):
            return payload.encode("utf-8")
    raise AwsAdapterError("S3 get_object returned an unreadable body")


def _metadata_map(raw: object) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {str(key).lower(): str(value) for key, value in raw.items() if value is not None}


def _as_optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _client_error_code(error: BaseException) -> str | None:
    response = getattr(error, "response", None)
    if isinstance(response, dict):
        payload = response.get("Error")
        if isinstance(payload, dict):
            code = payload.get("Code")
            if code is not None:
                return str(code)
    code = getattr(error, "code", None)
    return str(code) if code is not None else None


def _is_not_found(error: BaseException) -> bool:
    return _client_error_code(error) in _NOT_FOUND_CODES


def _wrap_client_error(operation: str, key: str, error: BaseException) -> StorageError:
    code = _client_error_code(error) or type(error).__name__
    return StorageError(f"S3 {operation} failed for {key!r}: {code}")
