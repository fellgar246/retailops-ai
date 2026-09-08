"""CLI for the human review queue."""

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from retailops_api.review import ops_cli
from retailops_api.review.ops_cli import main
from retailops_api.review.workflow import start_review
from tests.review_support import finding_case, person


def test_cli_requires_a_command() -> None:
    with pytest.raises(SystemExit) as error:
        main([])
    assert error.value.code == 2


@pytest.fixture
def cli_session(session: Session, monkeypatch: pytest.MonkeyPatch) -> Session:
    @contextmanager
    def _open() -> Iterator[Session]:
        yield session

    class _Factory:
        def __call__(self) -> AbstractContextManager[Session]:
            return _open()

    monkeypatch.setattr(ops_cli, "get_session_factory", lambda: _Factory())
    return session


def test_cli_queue_and_metrics(cli_session: Session, capsys: pytest.CaptureFixture[str]) -> None:
    case = finding_case(cli_session, supplier_code="SUP-CLI")

    assert main(["queue"]) == 0
    printed = capsys.readouterr().out
    assert f"id={case.id}" in printed

    assert main(["metrics"]) == 0
    metrics_out = capsys.readouterr().out
    assert "open_cases" in metrics_out


def test_cli_start_and_feedback(
    cli_session: Session, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    case = finding_case(cli_session, supplier_code="SUP-CLI2")
    start_review(cli_session, case.id, actor=person("alice"))

    assert main(["approve", str(case.id), "--reviewer", "alice", "--comment", "ok"]) == 0
    assert main(["feedback", "--output", str(tmp_path)]) == 0
    printed = capsys.readouterr().out
    assert "feedback.jsonl" in printed
    assert (tmp_path / "feedback.jsonl").is_file()
