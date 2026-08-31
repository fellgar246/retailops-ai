from datetime import UTC, datetime, timedelta

import pytest

from retailops_api.review.cloud_workflow import (
    LocalCallbackWorkflow,
    WorkflowConflictError,
    WorkflowPhase,
    correlation_id_for,
    idempotency_key_for,
)


def test_start_issues_token_and_is_idempotent() -> None:
    workflow = LocalCallbackWorkflow(timeout_seconds=60)
    first = workflow.start(12, subject_reference="document_finding:4")
    second = workflow.start(12, subject_reference="document_finding:4")

    assert first.task_token == second.task_token
    assert first.correlation_id == correlation_id_for(12)
    assert first.idempotency_key == idempotency_key_for(12, "document_finding:4")
    assert [event.phase for event in workflow.events] == [
        WorkflowPhase.start,
        WorkflowPhase.task_token_issued,
    ]


def test_success_and_failure_callbacks_consume_the_token() -> None:
    workflow = LocalCallbackWorkflow(timeout_seconds=60)
    handle = workflow.start(1, subject_reference="reconciliation_exception:9")
    success = workflow.callback_success(
        handle.task_token,
        outcome="approved",
        payload={"reviewer": "alice"},
    )
    assert success.phase is WorkflowPhase.success
    assert success.outcome == "approved"
    with pytest.raises(WorkflowConflictError, match="already consumed"):
        workflow.callback_failure(handle.task_token, cause="duplicate")


def test_timeout_only_after_expiry() -> None:
    workflow = LocalCallbackWorkflow(timeout_seconds=30)
    started = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
    handle = workflow.start(3, subject_reference="document_finding:1", now=started)
    with pytest.raises(WorkflowConflictError, match="has not expired"):
        workflow.expire(handle.task_token, now=started + timedelta(seconds=10))
    timed_out = workflow.expire(handle.task_token, now=started + timedelta(seconds=31))
    assert timed_out.phase is WorkflowPhase.timeout


def test_unknown_token_is_rejected() -> None:
    workflow = LocalCallbackWorkflow()
    with pytest.raises(WorkflowConflictError, match="unknown task token"):
        workflow.callback_success("nope", outcome="approved")
