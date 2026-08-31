"""Callback-token mapping for the local human-review workflow.

The persisted transitions in ``workflow.py`` remain the implementation.
This module records the events a hosted wait-for-callback orchestrator
would emit: start, task token, success, failure, timeout. It does not
call a remote workflow service.

Correlation id is ``review-case:{id}``. Idempotency key is
``{subject_reference}:{case_id}``. The task token is issued at start and
consumed by exactly one terminal callback.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from retailops_api.review.cases import ReviewValidationError


class WorkflowPhase(StrEnum):
    start = "start"
    task_token_issued = "task_token_issued"
    success = "success"
    failure = "failure"
    timeout = "timeout"


class WorkflowConflictError(ReviewValidationError):
    """The token was already consumed or does not match the case."""


@dataclass(frozen=True)
class WorkflowEvent:
    phase: WorkflowPhase
    case_id: int
    correlation_id: str
    idempotency_key: str
    task_token: str | None = None
    outcome: str | None = None
    detail: dict[str, Any] | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class WorkflowHandle:
    case_id: int
    correlation_id: str
    idempotency_key: str
    task_token: str
    timeout_seconds: int
    expires_at: datetime


def correlation_id_for(case_id: int) -> str:
    return f"review-case:{case_id}"


def idempotency_key_for(case_id: int, subject_reference: str) -> str:
    return f"{subject_reference}:{case_id}"


class LocalCallbackWorkflow:
    """In-memory callback-token lifecycle. Local review stays authoritative."""

    def __init__(self, *, timeout_seconds: int = 7 * 24 * 3600) -> None:
        if timeout_seconds <= 0:
            raise ReviewValidationError("workflow timeout must be positive")
        self.timeout_seconds = timeout_seconds
        self._handles: dict[int, WorkflowHandle] = {}
        self._consumed: set[str] = set()
        self.events: list[WorkflowEvent] = []

    def start(
        self,
        case_id: int,
        *,
        subject_reference: str,
        now: datetime | None = None,
    ) -> WorkflowHandle:
        existing = self._handles.get(case_id)
        if existing is not None and existing.task_token not in self._consumed:
            return existing
        when = now or datetime.now(UTC)
        token = secrets.token_urlsafe(32)
        handle = WorkflowHandle(
            case_id=case_id,
            correlation_id=correlation_id_for(case_id),
            idempotency_key=idempotency_key_for(case_id, subject_reference),
            task_token=token,
            timeout_seconds=self.timeout_seconds,
            expires_at=when + timedelta(seconds=self.timeout_seconds),
        )
        self._handles[case_id] = handle
        self._record(
            WorkflowPhase.start,
            handle,
            occurred_at=when,
            detail={"timeout_seconds": self.timeout_seconds},
        )
        self._record(WorkflowPhase.task_token_issued, handle, occurred_at=when)
        return handle

    def callback_success(
        self,
        task_token: str,
        *,
        outcome: str,
        payload: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> WorkflowEvent:
        handle = self._require_open(task_token, now=now)
        self._consumed.add(task_token)
        return self._record(
            WorkflowPhase.success,
            handle,
            outcome=outcome,
            detail=payload,
            occurred_at=now,
        )

    def callback_failure(
        self,
        task_token: str,
        *,
        cause: str,
        now: datetime | None = None,
    ) -> WorkflowEvent:
        handle = self._require_open(task_token, now=now)
        self._consumed.add(task_token)
        return self._record(
            WorkflowPhase.failure,
            handle,
            outcome="failure",
            detail={"cause": cause},
            occurred_at=now,
        )

    def expire(self, task_token: str, *, now: datetime | None = None) -> WorkflowEvent:
        handle = self._handle_for_token(task_token)
        when = now or datetime.now(UTC)
        if handle.task_token in self._consumed:
            raise WorkflowConflictError(f"task token already consumed for case {handle.case_id}")
        if when < handle.expires_at:
            raise WorkflowConflictError(f"task token for case {handle.case_id} has not expired")
        self._consumed.add(task_token)
        return self._record(
            WorkflowPhase.timeout,
            handle,
            outcome="timeout",
            occurred_at=when,
        )

    def handle_for(self, case_id: int) -> WorkflowHandle | None:
        return self._handles.get(case_id)

    def _require_open(self, task_token: str, *, now: datetime | None) -> WorkflowHandle:
        handle = self._handle_for_token(task_token)
        when = now or datetime.now(UTC)
        if handle.task_token in self._consumed:
            raise WorkflowConflictError(f"task token already consumed for case {handle.case_id}")
        if when >= handle.expires_at:
            raise WorkflowConflictError(f"task token for case {handle.case_id} has expired")
        return handle

    def _handle_for_token(self, task_token: str) -> WorkflowHandle:
        for handle in self._handles.values():
            if handle.task_token == task_token:
                return handle
        raise WorkflowConflictError("unknown task token")

    def _record(
        self,
        phase: WorkflowPhase,
        handle: WorkflowHandle,
        *,
        outcome: str | None = None,
        detail: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
    ) -> WorkflowEvent:
        event = WorkflowEvent(
            phase=phase,
            case_id=handle.case_id,
            correlation_id=handle.correlation_id,
            idempotency_key=handle.idempotency_key,
            task_token=handle.task_token,
            outcome=outcome,
            detail=detail,
            occurred_at=occurred_at or datetime.now(UTC),
        )
        self.events.append(event)
        return event
