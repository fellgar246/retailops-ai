from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from retailops_api.api.deps import get_db
from retailops_api.ops.overview import collect_overview
from retailops_api.ops.search import search_operations

router = APIRouter(tags=["operations"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/ops/overview")
def operations_overview(session: DbSession) -> dict[str, Any]:
    return collect_overview(session)


@router.get("/search")
def operations_search(
    session: DbSession,
    q: Annotated[str, Query(min_length=0, max_length=200)] = "",
) -> dict[str, Any]:
    return search_operations(session, q)
