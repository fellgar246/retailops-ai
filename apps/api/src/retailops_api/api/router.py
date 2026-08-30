from fastapi import APIRouter

from retailops_api.api.routes import health, reviews

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(reviews.router)
