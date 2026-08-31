from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from retailops_api.api.deps import get_db
from retailops_api.api.paging import DEFAULT_LIMIT, validate_page
from retailops_api.procurement.query import get_run, list_exceptions, list_runs

router = APIRouter(tags=["reconciliation"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/reconciliations")
def reconciliation_runs(
    session: DbSession,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> dict[str, Any]:
    limit, offset = validate_page(limit, offset)
    return list_runs(session, limit=limit, offset=offset)


@router.get("/reconciliations/{run_id}")
def reconciliation_run(run_id: int, session: DbSession) -> dict[str, Any]:
    payload = get_run(session, run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"reconciliation run {run_id} not found")
    return payload


@router.get("/exceptions")
def reconciliation_exceptions(
    session: DbSession,
    severity: Annotated[list[str] | None, Query()] = None,
    resolution: Annotated[list[str] | None, Query()] = None,
    code: str | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> dict[str, Any]:
    limit, offset = validate_page(limit, offset)
    return list_exceptions(
        session,
        limit=limit,
        offset=offset,
        severity=tuple(severity or ()),
        resolution=tuple(resolution or ()),
        code=code,
    )
