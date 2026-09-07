"""PP-StructureV3 tables mapped to the existing supplier sheet contract."""

from __future__ import annotations

import io
from dataclasses import replace
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Any

from retailops_api.core.limits import DEFAULT_MAX_UPLOAD_BYTES
from retailops_api.documents.parse import parse_cell_table
from retailops_api.documents.types import (
    ExtractionMeta,
    ParseError,
    ParseIssue,
    ParseResult,
    SupplierSheetRow,
)

_INFERENCE_LOCK = Lock()
_SUFFIXES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/tiff": ".tiff",
}


@lru_cache(maxsize=2)
def _pipeline(device: str) -> Any:
    try:
        from paddleocr import PPStructureV3
    except ImportError as error:
        raise ParseError(
            "PaddleOCR is not installed; install the paddleocr project extra"
        ) from error
    return PPStructureV3(
        device=device,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        use_formula_recognition=False,
        use_seal_recognition=False,
        use_chart_recognition=False,
    )


class PaddleOCRDocumentAnalyzer:
    def __init__(
        self,
        pipeline: Any = None,
        *,
        device: str = "cpu",
        max_pages: int = 10,
        max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    ) -> None:
        self.pipeline = pipeline
        self.device = device
        self.max_pages = max_pages
        self.max_upload_bytes = max_upload_bytes

    def analyze(
        self,
        data: bytes,
        *,
        media_type: str = "application/pdf",
        filename: str = "document",
    ) -> ParseResult:
        del filename  # Never use an uploaded filename as a filesystem path.
        if not data:
            raise ParseError("document is empty")
        if len(data) > self.max_upload_bytes:
            raise ParseError("document exceeds max upload size")
        suffix = _SUFFIXES.get(media_type)
        if suffix is None:
            raise ParseError("unsupported PaddleOCR media type")
        try:
            pages = _page_count(data, media_type)
            if pages > self.max_pages:
                raise ParseError(f"document has {pages} pages; OCR limit is {self.max_pages}")
            with TemporaryDirectory(prefix="retailops-ocr-") as directory:
                path = Path(directory) / ("document" + suffix)
                path.write_bytes(data)
                # Shared cached pipelines must not run concurrent inference.
                with _INFERENCE_LOCK:
                    pipeline = (
                        self.pipeline if self.pipeline is not None else _pipeline(self.device)
                    )
                    results: list[dict[str, Any]] = []
                    if media_type == "image/tiff":
                        from PIL import Image, ImageSequence

                        with Image.open(io.BytesIO(data)) as source:
                            for index, frame in enumerate(ImageSequence.Iterator(source)):
                                frame_path = Path(directory) / f"page-{index}.png"
                                frame.convert("RGB").save(frame_path)
                                results.extend(
                                    item.json for item in pipeline.predict(str(frame_path))
                                )
                    else:
                        results = [item.json for item in pipeline.predict(str(path))]
                if len(results) != pages:
                    raise ParseError("PaddleOCR did not return all document pages")
                return paddleocr_results_to_parse_result(results)
        except ParseError:
            raise
        except Exception as error:
            raise ParseError(f"PaddleOCR analysis failed ({type(error).__name__})") from error


def _page_count(data: bytes, media_type: str) -> int:
    if media_type == "application/pdf":
        from pypdf import PdfReader

        return len(PdfReader(io.BytesIO(data)).pages)
    from PIL import Image

    with Image.open(io.BytesIO(data)) as source:
        return int(getattr(source, "n_frames", 1))


def paddleocr_results_to_parse_result(results: list[dict[str, Any]]) -> ParseResult:
    rows: list[SupplierSheetRow] = []
    issues = []
    table_count = 0
    for page_number, item in enumerate(results, start=1):
        page = item.get("res", item)
        tables = page.get("table_res_list", [])
        if not tables:
            issues.append(
                ParseIssue(
                    code="ocr_no_table",
                    message=f"No supplier table extracted on page {page_number}",
                )
            )
        for table in tables:
            table_count += 1
            try:
                parser = _TableParser()
                parser.feed(table["pred_html"])
                if parser.merged:
                    raise ParseError("Merged table cells require human review")
                parsed = parse_cell_table(parser.rows, source_row_offset=len(rows) + 1)
                rows.extend(replace(row, page=page_number) for row in parsed.rows)
                issues.extend(parsed.issues)
            except (ParseError, KeyError, TypeError) as error:
                issues.append(
                    ParseIssue(
                        code="ocr_table_unreadable",
                        message=f"Table {table_count}, page {page_number}: {error}",
                    )
                )
    if not rows:
        raise ParseError("PaddleOCR found no readable supplier rows", issues=issues)
    return ParseResult(
        rows=tuple(rows),
        issues=tuple(issues),
        extraction=ExtractionMeta(
            analyzer="paddleocr",
            page_count=len(results),
            table_count=table_count,
            ambiguous=bool(issues),
        ),
    )


class _TableParser(HTMLParser):
    """Read cell text only; ambiguous merged cells are never guessed."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self.row: list[str] = []
        self.cell: list[str] | None = None
        self.merged = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self.row = []
        elif tag in {"td", "th"}:
            self.cell = []
            self.merged |= any(
                key in {"rowspan", "colspan"} and value not in {None, "1"} for key, value in attrs
            )
        elif tag == "br" and self.cell is not None:
            self.cell.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self.cell is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.row:
            self.rows.append(self.row)
            self.row = []

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)
