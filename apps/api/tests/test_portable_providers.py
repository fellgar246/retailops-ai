import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from openai import OpenAI
from pydantic import ValidationError

from retailops_api.core.adapters import ai_reviewer_for, document_analyzer_for
from retailops_api.core.config import Settings
from retailops_api.documents.paddleocr import (
    PaddleOCRDocumentAnalyzer,
    paddleocr_results_to_parse_result,
)
from retailops_api.documents.parse import parse_supplier_sheet
from retailops_api.documents.pdf import write_text_pdf
from retailops_api.documents.types import ParseError
from retailops_api.review import cli as review_cli
from retailops_api.review.mock import canned_output
from retailops_api.review.openai import OpenAIReviewer
from retailops_api.review.types import ReviewerError, ReviewSchemaError, ReviewType
from tests.test_bedrock_reviewer import _request


class FakeResponses:
    def __init__(self) -> None:
        self.responses = self
        self.calls: list[dict[str, Any]] = []
        self.error: Exception | None = None
        self.response = SimpleNamespace(
            status="completed",
            output=[],
            output_text=json.dumps(canned_output(ReviewType.category_suggestion)),
            usage=SimpleNamespace(input_tokens=20, output_tokens=10, total_tokens=30),
        )

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


@pytest.mark.parametrize("aws_enabled", [False, True])
def test_explicit_portable_providers_override_legacy_flags(aws_enabled: bool) -> None:
    settings = Settings(
        _env_file=None,
        aws_enabled=aws_enabled,
        aws_use_bedrock=True,
        aws_use_textract=True,
        ai_review_provider="openai",
        document_ocr_provider="paddleocr",
        openai_model="test-model",
    )
    client = FakeResponses()
    reviewer = ai_reviewer_for(settings, openai=client)
    assert isinstance(reviewer, OpenAIReviewer)
    assert isinstance(document_analyzer_for(settings), PaddleOCRDocumentAnalyzer)
    result = reviewer.review(_request())
    assert result.provider == "openai"
    assert result.model == "test-model"
    assert result.prompt_id == _request().prompt_id
    assert reviewer.last_usage is not None
    assert reviewer.last_usage.total_tokens == 30
    call = client.calls[0]
    assert call["store"] is False
    schema = call["text"]["format"]["schema"]
    assert set(schema["required"]) == set(schema["properties"])
    assert "provider" not in schema["properties"]
    finding = schema["properties"]["findings"]["items"]
    assert set(finding["required"]) == set(finding["properties"])


def test_missing_openai_configuration_and_invalid_provider() -> None:
    with pytest.raises(ReviewerError, match="OPENAI_MODEL"):
        ai_reviewer_for(Settings(_env_file=None, ai_review_provider="openai"))
    with pytest.raises(ReviewerError, match="OPENAI_API_KEY"):
        ai_reviewer_for(
            Settings(
                _env_file=None,
                ai_review_provider="openai",
                openai_model="test",
                openai_api_key="",
            )
        )
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ai_review_provider="typo")
    assert "secret-value" not in repr(Settings(_env_file=None, openai_api_key="secret-value"))


def test_openai_errors_do_not_return_partial_reviews_or_leak_bodies() -> None:
    client = FakeResponses()
    reviewer = OpenAIReviewer(client, model_id="test")
    client.response.status = "incomplete"
    with pytest.raises(ReviewerError, match="incomplete"):
        reviewer.review(_request())
    client.response.status = "completed"
    client.response.output = [SimpleNamespace(content=[SimpleNamespace(type="refusal")])]
    with pytest.raises(ReviewerError, match="declined"):
        reviewer.review(_request())
    client.response.output = []
    client.response.output_text = '{"confidence": 99}'
    with pytest.raises(ReviewSchemaError):
        reviewer.review(_request())
    client.error = RuntimeError("sensitive provider body")
    with pytest.raises(ReviewerError) as caught:
        reviewer.review(_request())
    assert "sensitive" not in str(caught.value)
    assert reviewer.last_usage is None


def test_openai_payload_limit_prevents_call() -> None:
    client = FakeResponses()
    with pytest.raises(ReviewerError, match="max payload"):
        OpenAIReviewer(client, model_id="test", max_prompt_chars=1).review(_request())
    assert client.calls == []


def test_evaluation_cli_accepts_openai_without_aws(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(review_cli, "get_settings", lambda: Settings(_env_file=None))
    selected = []

    def reviewer(settings: Settings) -> OpenAIReviewer:
        selected.append(settings.ai_review_provider)
        assert not settings.aws_enabled
        return OpenAIReviewer(FakeResponses(), model_id="test")

    monkeypatch.setattr(review_cli, "ai_reviewer_for", reviewer)
    assert (
        review_cli.main(
            [
                "--provider",
                "openai",
                "--compare",
                "--output",
                str(tmp_path),
            ]
        )
        == 0
    )
    assert selected == ["openai"]
    assert list((tmp_path / "openai").rglob("evaluation.json"))


def test_real_openai_sdk_serializes_responses_request() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/responses"
        payload = json.loads(request.content)
        assert payload["text"]["format"]["strict"] is True
        assert payload["store"] is False
        result = canned_output(ReviewType.category_suggestion)
        schema = payload["text"]["format"]["schema"]["properties"]
        output = {key: result.get(key) for key in schema}
        return httpx.Response(
            200,
            json={
                "id": "resp_fixture",
                "object": "response",
                "created_at": 0,
                "model": "test",
                "status": "completed",
                "output": [
                    {
                        "id": "msg_fixture",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(output),
                                "annotations": [],
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
            },
        )

    with OpenAI(
        api_key="fixture-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handle)),
    ) as client:
        result = OpenAIReviewer(client, model_id="test").review(_request())
    assert result.provider == "openai"
    assert result.suggested_value == "BEV-SOFT"


TABLE = (
    "<table><tr><th>Supplier SKU</th><th>Unit Cost</th></tr>"
    "<tr><td>SKU-1</td><td>12.50</td></tr></table>"
)


def test_paddle_tables_keep_all_pages_and_report_unreadable_tables() -> None:
    result = paddleocr_results_to_parse_result(
        [
            {"res": {"table_res_list": [{"pred_html": TABLE}]}},
            {"res": {"table_res_list": [{"pred_html": TABLE}, {"pred_html": "bad"}]}},
            {"res": {"table_res_list": []}},
        ]
    )
    assert [row.page for row in result.rows] == [1, 2]
    assert [row.row_number for row in result.rows] == [2, 3]
    assert str(result.rows[0].cost) == "12.50"
    assert result.extraction is not None
    assert result.extraction.ambiguous
    assert result.extraction.page_count == 3
    assert {issue.code for issue in result.issues} == {"ocr_table_unreadable", "ocr_no_table"}


def test_paddle_rejects_ambiguous_merged_cells() -> None:
    with pytest.raises(ParseError):
        paddleocr_results_to_parse_result(
            [
                {"table_res_list": [{"pred_html": TABLE.replace("<td>", '<td colspan="2">', 1)}]},
            ]
        )


class FakePipeline:
    def __init__(self) -> None:
        self.paths: list[Path] = []

    def predict(self, path: str) -> list[SimpleNamespace]:
        self.paths.append(Path(path))
        assert Path(path).read_bytes().startswith(b"%PDF")
        return [SimpleNamespace(json={"res": {"table_res_list": [{"pred_html": TABLE}]}})]


def test_paddle_dispatch_and_temporary_file_cleanup() -> None:
    pipeline = FakePipeline()
    analyzer = PaddleOCRDocumentAnalyzer(pipeline)
    result = parse_supplier_sheet(
        write_text_pdf("fixture"),
        media_type="application/pdf",
        filename="../../escape.pdf",
        analyzer=analyzer,
    )
    assert result.rows[0].supplier_sku == "SKU-1"
    assert not pipeline.paths[0].exists()
    # CSV must never invoke OCR.
    parse_supplier_sheet(b"Supplier SKU,Unit Cost\nA,1", media_type="text/csv", analyzer=analyzer)
    assert len(pipeline.paths) == 1


def test_paddle_bounds_reject_before_inference() -> None:
    pipeline = FakePipeline()
    with pytest.raises(ParseError, match="max upload"):
        PaddleOCRDocumentAnalyzer(pipeline, max_upload_bytes=1).analyze(b"pdf")
    with pytest.raises(ParseError, match="OCR limit"):
        PaddleOCRDocumentAnalyzer(pipeline, max_pages=0).analyze(write_text_pdf("fixture"))
    assert pipeline.paths == []
