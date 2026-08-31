from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from retailops_api.api.deps import get_db
from retailops_api.api.paging import DEFAULT_LIMIT, validate_page
from retailops_api.review.audit import list_recent_events

router = APIRouter(prefix="/audit", tags=["audit"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("")
def recent_audit(session: DbSession, limit: int = DEFAULT_LIMIT, offset: int = 0) -> dict[str, Any]:
    limit, offset = validate_page(limit, offset)
    events, total = list_recent_events(session, limit=limit, offset=offset)
    return {
        "items": [
            {
                "id": event.id,
                "review_case_id": event.review_case_id,
                "event_type": event.event_type,
                "actor": event.actor,
                "from_status": event.from_status,
                "to_status": event.to_status,
                "payload": event.payload,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
