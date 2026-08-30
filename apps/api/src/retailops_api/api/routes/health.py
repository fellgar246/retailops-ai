from fastapi import APIRouter
from pydantic import BaseModel

from retailops_api.db.session import check_database_connection

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str


class DatabaseHealthResponse(BaseModel):
    status: str
    database: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/health/db", response_model=DatabaseHealthResponse)
def database_health() -> DatabaseHealthResponse:
    connected = check_database_connection()
    return DatabaseHealthResponse(
        status="ok" if connected else "degraded",
        database="connected" if connected else "unavailable",
    )
