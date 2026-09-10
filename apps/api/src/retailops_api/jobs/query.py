"""Reading jobs for the API and the console."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from retailops_api.domain.models.job import JobKind, JobState, ProcessingJob
from retailops_api.jobs.store import job_view


def list_jobs(
    session: Session,
    *,
    limit: int,
    offset: int,
    kinds: tuple[JobKind, ...] = (),
    states: tuple[JobState, ...] = (),
) -> dict[str, Any]:
    statement = select(ProcessingJob)
    if kinds:
        statement = statement.where(ProcessingJob.kind.in_([kind.value for kind in kinds]))
    if states:
        statement = statement.where(ProcessingJob.state.in_([state.value for state in states]))

    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    # Newest first: an operator is looking for what they just started.
    rows = session.scalars(
        statement.order_by(ProcessingJob.id.desc()).limit(limit).offset(offset)
    ).all()
    return {
        "items": [job_view(row).to_dict() for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
