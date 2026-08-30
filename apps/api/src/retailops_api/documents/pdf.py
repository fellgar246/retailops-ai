"""Text-based PDF adapter for supplier sheets.

Extracts page text and, when a header line maps onto the canonical columns,
parses the following lines as a delimited table. It does not reconstruct
tables from drawing positions or images. Scanned or layout-only PDFs need a
document-analysis service; this adapter exists so the storage and processing
contracts can be exercised with a controlled fixture.
"""

from __future__ import annotations

import io

from retailops_api.documents.parse import parse_delimited_table
from retailops_api.documents.schema import map_header
from retailops_api.documents.types import ParseError, ParseIssue, ParseResult


def parse_text_pdf(data: bytes) -> ParseResult:
    text = extract_pdf_text(data)
    if not text.strip():
        raise ParseError(
            "PDF has no extractable text; scanned pages need a document-analysis service",
            issues=[
                ParseIssue(
                    code="pdf_not_textual",
                    message="PDF has no extractable text",
                )
            ],
        )
    header_line = _first_tabular_header_line(text)
    if header_line is None:
        raise ParseError(
            "PDF text has no recognisable tabular header; "
            "this adapter does not infer table geometry",
            issues=[
                ParseIssue(
                    code="pdf_no_tabular_header",
                    message="PDF text has no recognisable tabular header",
                )
            ],
        )
    # Keep only the header and the lines after it so leading page chrome is dropped.
    lines = text.splitlines()
    start = next(index for index, line in enumerate(lines) if line.strip() == header_line.strip())
    body = "\n".join(lines[start:])
    return parse_delimited_table(body, source_row_offset=start + 1)


def extract_pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(pages)


def write_text_pdf(text: str) -> bytes:
    """Build a single-page text PDF for fixtures. Not a general publisher."""
    lines = text.splitlines() or [""]
    ops = ["BT", "/F1 10 Tf", "36 760 Td", "12 TL"]
    for index, line in enumerate(lines):
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if index:
            ops.append("T*")
        ops.append(f"({escaped}) Tj")
    ops.append("ET")
    content = "\n".join(ops).encode("latin-1", errors="replace")
    return _assemble_pdf(content)


def _first_tabular_header_line(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        tokens = [part.strip() for part in _split_loose(stripped) if part.strip()]
        mapped = [map_header(token) for token in tokens]
        if sum(1 for name in mapped if name is not None) >= 2:
            return stripped
    return None


def _split_loose(line: str) -> list[str]:
    for delimiter in (",", ";", "\t", "|"):
        if delimiter in line:
            return line.split(delimiter)
    return line.split()


def _assemble_pdf(content: bytes) -> bytes:
    """Minimal PDF 1.4 with one page and a Courier stream."""
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length "
        + str(len(content)).encode("ascii")
        + b" >>\nstream\n"
        + content
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
    ]
    parts = [b"%PDF-1.4\n"]
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(sum(len(part) for part in parts))
        parts.append(f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n")
    xref_at = sum(len(part) for part in parts)
    xref = [b"xref\n", f"0 {len(objects) + 1}\n".encode("ascii"), b"0000000000 65535 f \n"]
    for offset in offsets[1:]:
        xref.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    trailer = (
        b"trailer\n<< /Size "
        + str(len(objects) + 1).encode("ascii")
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref_at).encode("ascii")
        + b"\n%%EOF\n"
    )
    return b"".join(parts) + b"".join(xref) + trailer
