from pathlib import Path

from retailops_api.core.adapters import ai_reviewer_for, document_analyzer_for, document_storage_for
from retailops_api.core.config import Settings
from retailops_api.documents.parse import parse_supplier_sheet
from retailops_api.documents.s3 import S3DocumentStorage
from retailops_api.documents.storage import LocalDocumentStorage
from retailops_api.documents.textract import TextractDocumentAnalyzer
from retailops_api.documents.textract_corpus import corpus_cases, synthetic_textract_table
from retailops_api.review.bedrock import BedrockAIReviewer
from retailops_api.review.mock import MockAIReviewer
from tests.aws_fakes import FakeS3, FakeTextract


def test_local_mode_keeps_filesystem_and_mock(tmp_path: Path) -> None:
    settings = Settings(
        aws_enabled=False,
        aws_use_s3_storage=True,
        aws_use_textract=True,
        aws_use_bedrock=True,
        document_storage_root=str(tmp_path),
    )
    assert isinstance(document_storage_for(settings), LocalDocumentStorage)
    assert document_analyzer_for(settings) is None
    assert isinstance(ai_reviewer_for(settings), MockAIReviewer)


def test_cloud_flags_select_hosted_adapters() -> None:
    settings = Settings(
        aws_enabled=True,
        aws_use_s3_storage=True,
        aws_use_textract=True,
        aws_use_bedrock=True,
        aws_documents_bucket="retailops-ai-dev-documents",
        aws_bedrock_model_id="anthropic.claude-haiku-4-5-20251001-v1:0",
        bedrock_inference_profile_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    )
    store = document_storage_for(settings, s3=FakeS3())
    analyzer = document_analyzer_for(settings, textract=FakeTextract({}))
    reviewer = ai_reviewer_for(settings, bedrock=object())
    assert isinstance(store, S3DocumentStorage)
    assert store.prefix == "supplier-documents"
    assert isinstance(analyzer, TextractDocumentAnalyzer)
    assert isinstance(reviewer, BedrockAIReviewer)
    assert reviewer.model_id == "us.anthropic.claude-haiku-4-5-20251001-v1:0"


def test_csv_stays_on_the_local_parser_when_textract_is_configured() -> None:
    from retailops_api.documents.corpus import VALID_ROWS, csv_bytes

    client = FakeTextract(synthetic_textract_table(VALID_ROWS))
    analyzer = TextractDocumentAnalyzer(client)
    parsed = parse_supplier_sheet(
        csv_bytes(VALID_ROWS[:1]),
        media_type="text/csv",
        filename="offer.csv",
        analyzer=analyzer,
    )
    assert client.calls == []
    assert parsed.rows[0].supplier_sku == "NW-SODA-330"


def test_pdf_uses_the_injected_analyzer() -> None:
    case = corpus_cases()[0]
    client = FakeTextract(synthetic_textract_table(case.rows))
    analyzer = TextractDocumentAnalyzer(client)
    parsed = parse_supplier_sheet(
        b"%PDF-fixture",
        media_type="application/pdf",
        filename="offer.pdf",
        analyzer=analyzer,
    )
    assert client.calls
    assert client.calls[0]["FeatureTypes"] == ["TABLES", "FORMS"]
    assert parsed.rows[0].supplier_sku == "NW-SODA-330"
