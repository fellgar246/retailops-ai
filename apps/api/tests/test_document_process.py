from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from retailops_api.db.seed import seed_reference_data
from retailops_api.documents.catalog_rules import COST_INCREASE
from retailops_api.documents.corpus import VALID_ROWS, xlsx_bytes
from retailops_api.documents.pdf import write_text_pdf
from retailops_api.documents.process import process_document
from retailops_api.documents.rules import (
    DUPLICATE_SUPPLIER_SKU,
    INVALID_EAN,
    INVALID_VAT,
    REQUIRED_FIELD,
)
from retailops_api.documents.storage import LocalDocumentStorage
from retailops_api.documents.types import DocumentProcessError, ProcessResult
from retailops_api.domain.models import DocumentFinding, SupplierDocument
from retailops_api.domain.models.document import DocumentStatus

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "supplier_documents"


def _process(
    session: Session, tmp_path: Path, filename: str, data: bytes | None = None
) -> ProcessResult:
    seed_reference_data(session)
    storage = LocalDocumentStorage(tmp_path)
    payload = data if data is not None else (FIXTURES / filename).read_bytes()
    return process_document(
        session,
        storage,
        supplier_code="SUP-BEVCO",
        filename=filename,
        data=payload,
    )


def test_valid_csv_reaches_review_ready_without_errors(session: Session, tmp_path: Path) -> None:
    result = _process(session, tmp_path, "valid.csv")

    assert result.status == DocumentStatus.review_ready.value
    assert result.row_count == 2
    assert all(item.severity.value != "error" for item in result.findings)
    stored = session.get(SupplierDocument, result.document_id)
    assert stored is not None
    assert stored.checksum == result.checksum
    assert (tmp_path / result.storage_key).is_file()


def test_invalid_ean_fixture(session: Session, tmp_path: Path) -> None:
    result = _process(session, tmp_path, "invalid_ean.csv")

    assert result.status == DocumentStatus.review_ready.value
    assert any(item.code == INVALID_EAN for item in result.findings)


def test_missing_field_fixture(session: Session, tmp_path: Path) -> None:
    result = _process(session, tmp_path, "missing_field.csv")

    assert any(
        item.code == REQUIRED_FIELD and item.field == "description" for item in result.findings
    )


def test_duplicate_sku_fixture(session: Session, tmp_path: Path) -> None:
    result = _process(session, tmp_path, "duplicate_sku.csv")

    assert any(item.code == DUPLICATE_SUPPLIER_SKU for item in result.findings)


def test_cost_increase_fixture(session: Session, tmp_path: Path) -> None:
    result = _process(session, tmp_path, "cost_increase.csv")

    finding = next(item for item in result.findings if item.code == COST_INCREASE)
    assert finding.proposed_value == "7.4500"
    persisted = session.scalars(select(DocumentFinding)).all()
    assert any(row.code == COST_INCREASE for row in persisted)


def test_invalid_vat_fixture(session: Session, tmp_path: Path) -> None:
    result = _process(session, tmp_path, "invalid_vat.csv")

    assert any(item.code == INVALID_VAT for item in result.findings)


def test_malformed_row_fixture(session: Session, tmp_path: Path) -> None:
    result = _process(session, tmp_path, "malformed_row.csv")

    assert any(item.code == "malformed_value" for item in result.findings)
    assert result.status == DocumentStatus.review_ready.value


def test_xlsx_and_text_pdf_follow_the_same_pipeline(session: Session, tmp_path: Path) -> None:
    xlsx = _process(session, tmp_path / "xlsx", "offer.xlsx", xlsx_bytes(VALID_ROWS))
    pdf = _process(
        session,
        tmp_path / "pdf",
        "offer.pdf",
        write_text_pdf((FIXTURES / "valid.csv").read_text(encoding="utf-8")),
    )

    assert xlsx.status == DocumentStatus.review_ready.value
    assert pdf.status == DocumentStatus.review_ready.value
    assert xlsx.row_count == pdf.row_count == 2


def test_unreadable_pdf_is_parse_failed(session: Session, tmp_path: Path) -> None:
    result = _process(session, tmp_path, "letter.pdf", write_text_pdf("Dear buyer,\nsee attached."))

    assert result.status == DocumentStatus.parse_failed.value
    assert result.row_count == 0
    document = session.get(SupplierDocument, result.document_id)
    assert document is not None
    assert document.status == DocumentStatus.parse_failed.value


def test_unknown_supplier_does_not_store_bytes(session: Session, tmp_path: Path) -> None:
    storage = LocalDocumentStorage(tmp_path)

    with pytest.raises(DocumentProcessError, match="unknown supplier"):
        process_document(
            session,
            storage,
            supplier_code="SUP-NOPE",
            filename="valid.csv",
            data=(FIXTURES / "valid.csv").read_bytes(),
        )

    assert list(tmp_path.iterdir()) == []


def test_pdf_intake_can_use_an_injected_analyzer(session: Session, tmp_path: Path) -> None:
    from retailops_api.documents.textract import TextractDocumentAnalyzer
    from retailops_api.documents.textract_corpus import synthetic_textract_table
    from tests.aws_fakes import FakeTextract

    seed_reference_data(session)
    analyzer = TextractDocumentAnalyzer(FakeTextract(synthetic_textract_table(VALID_ROWS[:1])))
    result = process_document(
        session,
        LocalDocumentStorage(tmp_path),
        supplier_code="SUP-BEVCO",
        filename="offer.pdf",
        data=b"%PDF-fixture",
        analyzer=analyzer,
    )
    assert result.status == DocumentStatus.review_ready.value
    assert result.row_count == 1
