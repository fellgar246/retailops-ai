"""Filtered, stably ordered review queue with offset pagination."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session

from retailops_api.domain.models.review import ReviewCase, ReviewPriority
from retailops_api.review.cases import PRIORITY_RANK, ReviewFilters, ReviewPage
from retailops_api.review.persist import case_view

DEFAULT_LIMIT = 50
MAX_LIMIT = 200

_PRIORITY_ORDER = case(
    (ReviewCase.priority == ReviewPriority.urgent.value, PRIORITY_RANK[ReviewPriority.urgent]),
    (ReviewCase.priority == ReviewPriority.high.value, PRIORITY_RANK[ReviewPriority.high]),
    (ReviewCase.priority == ReviewPriority.medium.value, PRIORITY_RANK[ReviewPriority.medium]),
    else_=PRIORITY_RANK[ReviewPriority.low],
)


def list_cases(
    session: Session,
    filters: ReviewFilters | None = None,
    *,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> ReviewPage:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if offset < 0:
        raise ValueError("offset must be at least 0")
    page_size = min(limit, MAX_LIMIT)
    stmt = _apply_filters(select(ReviewCase), filters or ReviewFilters())
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(
        stmt.order_by(_PRIORITY_ORDER.desc(), ReviewCase.created_at.asc(), ReviewCase.id.asc())
        .limit(page_size)
        .offset(offset)
    ).all()
    return ReviewPage(
        items=tuple(case_view(row) for row in rows),
        total=total,
        limit=page_size,
        offset=offset,
    )


def _apply_filters(
    stmt: Select[tuple[ReviewCase]], filters: ReviewFilters
) -> Select[tuple[ReviewCase]]:
    if filters.statuses:
        stmt = stmt.where(ReviewCase.status.in_([item.value for item in filters.statuses]))
    if filters.priorities:
        stmt = stmt.where(ReviewCase.priority.in_([item.value for item in filters.priorities]))
    if filters.subject_types:
        stmt = stmt.where(
            ReviewCase.subject_type.in_([item.value for item in filters.subject_types])
        )
    if filters.supplier_id is not None:
        stmt = stmt.where(ReviewCase.supplier_id == filters.supplier_id)
    if filters.risks:
        stmt = stmt.where(ReviewCase.risk.in_([item.value for item in filters.risks]))
    start = _range_start(filters.created_from)
    if start is not None:
        stmt = stmt.where(ReviewCase.created_at >= start)
    end = _range_end_exclusive(filters.created_to)
    if end is not None:
        stmt = stmt.where(ReviewCase.created_at < end)
    return stmt


def _range_start(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return datetime.combine(value, time.min, tzinfo=UTC)


def _range_end_exclusive(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        instant = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return instant + timedelta(microseconds=1)
    return datetime.combine(value + timedelta(days=1), time.min, tzinfo=UTC)
