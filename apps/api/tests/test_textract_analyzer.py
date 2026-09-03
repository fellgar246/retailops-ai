import json
from decimal import Decimal
from pathlib import Path

import pytest

from retailops_api.core.aws import AwsAdapterError
from retailops_api.core.retry import RetryPolicy
from retailops_api.documents.textract import (
    TextractDocumentAnalyzer,
    textract_response_to_parse_result,
)
from retailops_api.documents.types import ParseError, StorageError
from tests.aws_fakes import FakeClientError, FakeTextract

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "textract"


def test_textract_table_fixture_becomes_a_canonical_sheet() -> None:
    payload = json.loads((FIXTURES / "supplier_sheet_table.json").read_text(encoding="utf-8"))
    result = TextractDocumentAnalyzer().analyze_response(payload)

    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.supplier_sku == "NW-SODA-330"
    assert row.ean == "7501999000011"
    assert row.description == "New Cola 330ml"
    assert row.category == "BEV-SOFT"
    assert row.cost == Decimal("6.5000")
    assert row.vat == Decimal("16")
    assert row.case_pack == 24
    assert row.minimum_order_quantity == 1
    assert row.lead_time_days == 5


def test_textract_line_fixture_parses_delimited_text() -> None:
    payload = json.loads((FIXTURES / "supplier_sheet_lines.json").read_text(encoding="utf-8"))
    result = textract_response_to_parse_result(payload)

    assert len(result.rows) == 1
    assert result.rows[0].supplier_sku == "NW-WATER-500"
    assert result.rows[0].category == "BEV-WATER"


def test_textract_empty_response_is_a_parse_error() -> None:
    with pytest.raises(ParseError, match="no blocks"):
        textract_response_to_parse_result({"Blocks": []})


def test_textract_analyze_uses_injected_client() -> None:
    payload = json.loads((FIXTURES / "supplier_sheet_table.json").read_text(encoding="utf-8"))
    client = FakeTextract(payload)
    analyzer = TextractDocumentAnalyzer(client)
    result = analyzer.analyze(b"%PDF-fixture", media_type="application/pdf", filename="offer.pdf")

    assert client.calls
    assert result.rows[0].supplier_sku == "NW-SODA-330"


def test_textract_analyze_without_client_is_an_error() -> None:
    with pytest.raises(AwsAdapterError, match="not configured"):
        TextractDocumentAnalyzer().analyze(b"bytes")


def test_textract_analyze_s3_uses_object_reference() -> None:
    payload = json.loads((FIXTURES / "supplier_sheet_table.json").read_text(encoding="utf-8"))
    client = FakeTextract(payload)
    analyzer = TextractDocumentAnalyzer(client)
    result = analyzer.analyze_s3(bucket="docs", key="block13/a/source/payload")
    assert client.calls[0]["Document"] == {
        "S3Object": {"Bucket": "docs", "Name": "block13/a/source/payload"}
    }
    assert result.rows[0].supplier_sku == "NW-SODA-330"


def test_textract_missing_object_is_a_storage_error() -> None:
    analyzer = TextractDocumentAnalyzer(
        FakeTextract(error=FakeClientError("InvalidS3ObjectException"))
    )
    with pytest.raises(StorageError, match="could not read S3 object"):
        analyzer.analyze_s3(bucket="docs", key="missing")


def test_textract_access_denied_is_not_retried() -> None:
    client = FakeTextract(error=FakeClientError("AccessDeniedException"))
    analyzer = TextractDocumentAnalyzer(
        client,
        retry=RetryPolicy(max_attempts=3, base_delay_seconds=0),
        sleep=lambda _: None,
    )
    with pytest.raises(AwsAdapterError, match="access_denied"):
        analyzer.analyze(b"%PDF-fixture", filename="offer.pdf")
    assert len(client.calls) == 1
