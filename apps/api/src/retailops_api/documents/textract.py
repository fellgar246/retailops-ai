"""Translate Textract-style response JSON into a canonical supplier sheet.

``analyze_response`` is the mapping used by tests with fixture JSON.
``analyze`` / ``analyze_s3`` call an injected client. Automated tests use stubs.
"""

from __future__ import annotations

import io
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from enum import StrEnum
from typing import Any, Protocol

from retailops_api.core.aws import AwsAdapterError
from retailops_api.core.limits import DocumentBounds
from retailops_api.core.retry import RetryPolicy
from retailops_api.documents.parse import parse_cell_table, parse_delimited_table
from retailops_api.documents.types import (
    ExtractionMeta,
    ParseError,
    ParseIssue,
    ParseResult,
    StorageError,
)

SleepFn = Callable[[float], None]

TEXTRACT_FEATURE_TYPES = ("TABLES", "FORMS")


class TextractClient(Protocol):
    """Subset of a boto3 Textract client used by this adapter."""

    def analyze_document(self, **kwargs: Any) -> dict[str, Any]: ...


class TextractErrorClass(StrEnum):
    throttled = "throttled"
    timeout = "timeout"
    access_denied = "access_denied"
    missing_object = "missing_object"
    unsupported = "unsupported"
    validation = "validation"
    unavailable = "unavailable"
    unknown = "unknown"


_RETRYABLE = frozenset(
    {TextractErrorClass.throttled, TextractErrorClass.unavailable, TextractErrorClass.timeout}
)

_CODE_CLASSES: dict[str, TextractErrorClass] = {
    "ThrottlingException": TextractErrorClass.throttled,
    "ProvisionedThroughputExceededException": TextractErrorClass.throttled,
    "AccessDeniedException": TextractErrorClass.access_denied,
    "UnrecognizedClientException": TextractErrorClass.access_denied,
    "InvalidS3ObjectException": TextractErrorClass.missing_object,
    "NoSuchKey": TextractErrorClass.missing_object,
    "UnsupportedDocumentException": TextractErrorClass.unsupported,
    "BadDocumentException": TextractErrorClass.unsupported,
    "DocumentTooLargeException": TextractErrorClass.validation,
    "InvalidParameterException": TextractErrorClass.validation,
    "ValidationException": TextractErrorClass.validation,
    "ServiceUnavailableException": TextractErrorClass.unavailable,
    "InternalServerError": TextractErrorClass.unavailable,
    "InternalServerException": TextractErrorClass.unavailable,
    "ReadTimeoutError": TextractErrorClass.timeout,
    "ConnectTimeoutError": TextractErrorClass.timeout,
    "Timeout": TextractErrorClass.timeout,
}


class TextractDocumentAnalyzer:
    """Map AnalyzeDocument / DetectDocumentText JSON onto ``ParseResult``."""

    def __init__(
        self,
        client: TextractClient | None = None,
        *,
        bounds: DocumentBounds | None = None,
        retry: RetryPolicy | None = None,
        sleep: SleepFn | None = None,
    ) -> None:
        self.client = client
        self.bounds = bounds or DocumentBounds()
        self.retry = retry or RetryPolicy()
        self._sleep = sleep or time.sleep

    def analyze_response(self, payload: Mapping[str, Any]) -> ParseResult:
        return textract_response_to_parse_result(payload)

    def analyze(
        self,
        data: bytes,
        *,
        media_type: str = "application/pdf",
        filename: str = "document",
    ) -> ParseResult:
        self._require_client()
        _reject_empty(data)
        self._enforce_bounds(data, media_type=media_type, filename=filename)
        response = self._invoke(
            document={"Bytes": data},
            filename=filename,
        )
        return self.analyze_response(response)

    def analyze_s3(
        self,
        *,
        bucket: str,
        key: str,
        filename: str = "document",
    ) -> ParseResult:
        self._require_client()
        if not bucket.strip() or not key.strip():
            raise ParseError(
                "S3 object reference is incomplete",
                issues=[
                    ParseIssue(
                        code="empty_document",
                        message="S3 object reference is incomplete",
                    )
                ],
            )
        response = self._invoke(
            document={"S3Object": {"Bucket": bucket.strip(), "Name": key.strip()}},
            filename=filename,
        )
        return self.analyze_response(response)

    def _require_client(self) -> TextractClient:
        if self.client is None:
            raise AwsAdapterError("Textract client is not configured")
        return self.client

    def _enforce_bounds(self, data: bytes, *, media_type: str, filename: str) -> None:
        if len(data) > self.bounds.max_upload_bytes:
            raise ParseError(
                f"{filename} exceeds max upload size ({self.bounds.max_upload_bytes} bytes)",
                issues=[
                    ParseIssue(
                        code="document_too_large",
                        message=f"document exceeds {self.bounds.max_upload_bytes} bytes",
                    )
                ],
            )
        pages = _page_count(data, media_type=media_type)
        if pages is not None and pages > self.bounds.max_textract_sync_pages:
            raise ParseError(
                f"{filename} has {pages} pages; sync Textract allows "
                f"{self.bounds.max_textract_sync_pages}",
                issues=[
                    ParseIssue(
                        code="too_many_pages",
                        message=(
                            f"{pages} pages exceeds sync limit "
                            f"{self.bounds.max_textract_sync_pages}"
                        ),
                    )
                ],
            )

    def _invoke(self, *, document: dict[str, Any], filename: str) -> dict[str, Any]:
        client = self._require_client()
        last_error: AwsAdapterError | None = None
        attempts = max(1, self.retry.max_attempts)
        for attempt in range(1, attempts + 1):
            try:
                response = client.analyze_document(
                    Document=document,
                    FeatureTypes=list(TEXTRACT_FEATURE_TYPES),
                )
            except Exception as error:
                classified = classify_textract_error(error)
                if classified is TextractErrorClass.missing_object:
                    raise StorageError(
                        f"Textract could not read S3 object for {filename}"
                    ) from error
                if classified is TextractErrorClass.unsupported:
                    raise ParseError(
                        f"Textract rejected {filename}",
                        issues=[
                            ParseIssue(
                                code="unsupported_media_type",
                                message=f"Textract rejected {filename}: {error}",
                            )
                        ],
                    ) from error
                last_error = AwsAdapterError(
                    f"Textract analyze failed for {filename} ({classified.value}): {error}"
                )
                if classified not in _RETRYABLE or attempt >= attempts:
                    raise last_error from error
                self._sleep(self.retry.delay_for(attempt))
                continue
            if not isinstance(response, dict):
                raise ParseError(
                    "Textract response is not an object",
                    issues=[
                        ParseIssue(
                            code="unrecognised_header",
                            message="Textract response is not an object",
                        )
                    ],
                )
            return response
        raise last_error or AwsAdapterError(f"Textract analyze failed for {filename}")


def textract_response_to_parse_result(payload: Mapping[str, Any]) -> ParseResult:
    """Turn a Textract Blocks document into the canonical sheet representation."""

    blocks = payload.get("Blocks")
    if not isinstance(blocks, list) or not blocks:
        raise ParseError(
            "Textract response has no blocks",
            issues=[ParseIssue(code="empty_document", message="Textract response has no blocks")],
        )
    by_id = {
        str(block["Id"]): block for block in blocks if isinstance(block, dict) and block.get("Id")
    }
    tables, table_pages, table_confidences = _tables_from_blocks(blocks, by_id)
    forms = _forms_as_table(blocks, by_id)
    lines = _lines_from_blocks(blocks)
    confidences = _block_confidences(blocks)
    pages = _page_numbers(blocks)
    extraction = ExtractionMeta(
        analyzer="textract",
        page_count=max(pages) if pages else None,
        table_count=len(tables),
        line_count=len(lines),
        form_count=1 if forms else 0,
        min_confidence=min(confidences) if confidences else None,
        max_confidence=max(confidences) if confidences else None,
        ambiguous=not tables and not forms,
    )
    if tables:
        result = parse_cell_table(tables[0])
        return _attach_row_geometry(
            result,
            extraction=extraction,
            page=table_pages[0] if table_pages else None,
            row_confidences=table_confidences[0] if table_confidences else (),
        )
    if forms:
        try:
            result = parse_cell_table(forms)
            return replace(result, extraction=extraction)
        except ParseError:
            pass
    if not lines:
        raise ParseError(
            "Textract response has no table or line text",
            issues=[
                ParseIssue(
                    code="empty_document",
                    message="Textract response has no table or line text",
                )
            ],
        )
    result = parse_delimited_table("\n".join(lines))
    return replace(result, extraction=extraction)


def classify_textract_error(error: BaseException) -> TextractErrorClass:
    response = getattr(error, "response", None)
    if isinstance(response, dict):
        payload = response.get("Error")
        if isinstance(payload, dict) and payload.get("Code") is not None:
            return _CODE_CLASSES.get(str(payload["Code"]), TextractErrorClass.unknown)
    code = getattr(error, "code", None)
    if code is not None:
        return _CODE_CLASSES.get(str(code), TextractErrorClass.unknown)
    name = type(error).__name__
    if name in _CODE_CLASSES:
        return _CODE_CLASSES[name]
    if "Timeout" in name:
        return TextractErrorClass.timeout
    return TextractErrorClass.unknown


def _tables_from_blocks(
    blocks: Sequence[object],
    by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[list[list[list[str]]], list[int | None], list[tuple[float | None, ...]]]:
    tables: list[list[list[str]]] = []
    pages: list[int | None] = []
    confidences: list[tuple[float | None, ...]] = []
    for block in blocks:
        if not isinstance(block, dict) or block.get("BlockType") != "TABLE":
            continue
        cells = _child_blocks(block, by_id, "CELL")
        if not cells:
            continue
        max_row = max(int(cell.get("RowIndex") or 1) for cell in cells)
        max_col = max(int(cell.get("ColumnIndex") or 1) for cell in cells)
        grid = [["" for _ in range(max_col)] for _ in range(max_row)]
        cell_confidence: list[list[float | None]] = [
            [None for _ in range(max_col)] for _ in range(max_row)
        ]
        for cell in cells:
            row = int(cell.get("RowIndex") or 1) - 1
            col = int(cell.get("ColumnIndex") or 1) - 1
            if 0 <= row < max_row and 0 <= col < max_col:
                grid[row][col] = _block_text(cell, by_id)
                cell_confidence[row][col] = _optional_confidence(cell)
        tables.append(grid)
        pages.append(_optional_int(block.get("Page")))
        # Skip the header row when attaching per-data-row confidence.
        data_rows = cell_confidence[1:] if len(cell_confidence) > 1 else []
        row_scores: list[float | None] = []
        for row_vals in data_rows:
            known = [value for value in row_vals if isinstance(value, float)]
            row_scores.append(min(known) if known else None)
        confidences.append(tuple(row_scores))
    return tables, pages, confidences


def _forms_as_table(
    blocks: Sequence[object],
    by_id: Mapping[str, Mapping[str, Any]],
) -> list[list[str]]:
    pairs: list[tuple[str, str]] = []
    for block in blocks:
        if not isinstance(block, dict) or block.get("BlockType") != "KEY_VALUE_SET":
            continue
        if "KEY" in (block.get("EntityTypes") or []):
            key_text = _block_text(block, by_id)
            value_text = ""
            for relation in block.get("Relationships") or []:
                if not isinstance(relation, dict) or relation.get("Type") != "VALUE":
                    continue
                for value_id in relation.get("Ids") or []:
                    value_block = by_id.get(str(value_id))
                    if value_block is not None:
                        value_text = _block_text(value_block, by_id)
            if key_text:
                pairs.append((key_text, value_text))
    if not pairs:
        return []
    headers = [key for key, _ in pairs]
    values = [value for _, value in pairs]
    return [headers, values]


def _lines_from_blocks(blocks: Sequence[object]) -> list[str]:
    lines: list[tuple[tuple[float, float, float], str]] = []
    for block in blocks:
        if not isinstance(block, dict) or block.get("BlockType") != "LINE":
            continue
        text = str(block.get("Text") or "").strip()
        if not text:
            continue
        lines.append((_geometry_key(block), text))
    lines.sort(key=lambda item: item[0])
    return [text for _, text in lines]


def _child_blocks(
    block: Mapping[str, Any],
    by_id: Mapping[str, Mapping[str, Any]],
    block_type: str,
) -> list[Mapping[str, Any]]:
    found: list[Mapping[str, Any]] = []
    for relation in block.get("Relationships") or []:
        if not isinstance(relation, dict) or relation.get("Type") != "CHILD":
            continue
        for child_id in relation.get("Ids") or []:
            child = by_id.get(str(child_id))
            if child is not None and child.get("BlockType") == block_type:
                found.append(child)
    return found


def _block_text(block: Mapping[str, Any], by_id: Mapping[str, Mapping[str, Any]]) -> str:
    direct = str(block.get("Text") or "").strip()
    if direct:
        return direct
    words = [_block_text(child, by_id) for child in _child_blocks(block, by_id, "WORD")]
    return " ".join(word for word in words if word).strip()


def _geometry_key(block: Mapping[str, Any]) -> tuple[float, float, float]:
    page = float(block.get("Page") or 1)
    box = (block.get("Geometry") or {}).get("BoundingBox") or {}
    if not isinstance(box, dict):
        return (page, 0.0, 0.0)
    return (page, float(box.get("Top") or 0), float(box.get("Left") or 0))


def _block_confidences(blocks: Sequence[object]) -> list[float]:
    values: list[float] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        value = _optional_confidence(block)
        if value is not None:
            values.append(value)
    return values


def _page_numbers(blocks: Sequence[object]) -> list[int]:
    pages: list[int] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        page = _optional_int(block.get("Page"))
        if page is not None:
            pages.append(page)
    return pages


def _optional_confidence(block: Mapping[str, Any]) -> float | None:
    raw = block.get("Confidence")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _attach_row_geometry(
    result: ParseResult,
    *,
    extraction: ExtractionMeta,
    page: int | None,
    row_confidences: Sequence[float | None],
) -> ParseResult:
    rows = []
    for index, row in enumerate(result.rows):
        confidence = row_confidences[index] if index < len(row_confidences) else None
        if confidence is not None:
            confidence = confidence / 100.0 if confidence > 1 else confidence
        rows.append(replace(row, page=page, confidence=confidence))
    return replace(result, rows=tuple(rows), extraction=extraction)


def _reject_empty(data: bytes) -> None:
    if not data:
        raise ParseError(
            "document is empty",
            issues=[ParseIssue(code="empty_document", message="document is empty")],
        )


def _page_count(data: bytes, *, media_type: str) -> int | None:
    if media_type.startswith("image/"):
        return 1
    if media_type != "application/pdf":
        return None
    try:
        from pypdf import PdfReader

        return len(PdfReader(io.BytesIO(data)).pages)
    except Exception:
        return None
