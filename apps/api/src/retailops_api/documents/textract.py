"""Translate Textract-style response JSON into a canonical supplier sheet.

This adapter does not call a live document-analysis API. Tests pass fixture
JSON. A client may be injected for ``analyze``; automated tests use stubs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from retailops_api.core.aws import AwsAdapterError
from retailops_api.documents.parse import parse_cell_table, parse_delimited_table
from retailops_api.documents.types import ParseError, ParseIssue, ParseResult


class TextractClient(Protocol):
    """Subset of a boto3 Textract client used by this adapter."""

    def analyze_document(self, **kwargs: Any) -> dict[str, Any]: ...


class TextractDocumentAnalyzer:
    """Map AnalyzeDocument / DetectDocumentText JSON onto ``ParseResult``."""

    def __init__(self, client: TextractClient | None = None) -> None:
        self.client = client

    def analyze_response(self, payload: Mapping[str, Any]) -> ParseResult:
        return textract_response_to_parse_result(payload)

    def analyze(
        self,
        data: bytes,
        *,
        media_type: str = "application/pdf",
        filename: str = "document",
    ) -> ParseResult:
        if self.client is None:
            raise AwsAdapterError("Textract client is not configured")
        if not data:
            raise ParseError(
                "document is empty",
                issues=[ParseIssue(code="empty_document", message="document is empty")],
            )
        try:
            response = self.client.analyze_document(
                Document={"Bytes": data},
                FeatureTypes=["TABLES"],
            )
        except Exception as error:
            raise AwsAdapterError(f"Textract analyze failed for {filename}: {error}") from error
        if not isinstance(response, dict):
            raise ParseError(
                "Textract response is not an object",
                issues=[
                    ParseIssue(
                        code="unrecognised_header",
                        message=f"Textract response is not an object for {media_type}",
                    )
                ],
            )
        return self.analyze_response(response)


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
    tables = _tables_from_blocks(blocks, by_id)
    if tables:
        return parse_cell_table(tables[0])
    lines = _lines_from_blocks(blocks)
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
    return parse_delimited_table("\n".join(lines))


def _tables_from_blocks(
    blocks: Sequence[object],
    by_id: Mapping[str, Mapping[str, Any]],
) -> list[list[list[str]]]:
    tables: list[list[list[str]]] = []
    for block in blocks:
        if not isinstance(block, dict) or block.get("BlockType") != "TABLE":
            continue
        cells = _child_blocks(block, by_id, "CELL")
        if not cells:
            continue
        max_row = max(int(cell.get("RowIndex") or 1) for cell in cells)
        max_col = max(int(cell.get("ColumnIndex") or 1) for cell in cells)
        grid = [["" for _ in range(max_col)] for _ in range(max_row)]
        for cell in cells:
            row = int(cell.get("RowIndex") or 1) - 1
            col = int(cell.get("ColumnIndex") or 1) - 1
            if 0 <= row < max_row and 0 <= col < max_col:
                grid[row][col] = _block_text(cell, by_id)
        tables.append(grid)
    return tables


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
