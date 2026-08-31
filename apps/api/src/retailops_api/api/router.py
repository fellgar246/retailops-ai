from fastapi import APIRouter

from retailops_api.api.routes import (
    audit,
    documents,
    forecasts,
    health,
    ops,
    reconciliations,
    reviews,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(ops.router)
api_router.include_router(forecasts.router)
api_router.include_router(documents.router)
api_router.include_router(reconciliations.router)
api_router.include_router(reviews.router)
api_router.include_router(audit.router)
