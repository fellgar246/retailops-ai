from fastapi import APIRouter, Depends

from retailops_api.api.deps import get_principal
from retailops_api.api.routes import (
    audit,
    documents,
    forecasts,
    health,
    jobs,
    ops,
    reconciliations,
    reviews,
)

#: Everything an authenticated caller may reach. Health checks are the only
#: endpoints served without a credential, so a load balancer can probe the
#: service without one.
authenticated = APIRouter(dependencies=[Depends(get_principal)])
authenticated.include_router(ops.router)
authenticated.include_router(forecasts.router)
authenticated.include_router(documents.router)
authenticated.include_router(reconciliations.router)
authenticated.include_router(reviews.router)
authenticated.include_router(audit.router)
authenticated.include_router(jobs.router)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(authenticated)
