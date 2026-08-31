from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from retailops_api.api.deps import get_db
from retailops_api.api.paging import DEFAULT_LIMIT, validate_page
from retailops_api.forecasting.query import get_run, list_runs

router = APIRouter(prefix="/forecasts", tags=["forecasts"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("")
def forecast_runs(
    session: DbSession,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> dict[str, Any]:
    limit, offset = validate_page(limit, offset)
    return list_runs(session, limit=limit, offset=offset)


@router.get("/{run_id}")
def forecast_run(run_id: int, session: DbSession) -> dict[str, Any]:
    payload = get_run(session, run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"forecast run {run_id} not found")
    return payload
