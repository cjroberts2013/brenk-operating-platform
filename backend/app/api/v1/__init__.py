"""v1 API router — aggregates all v1 endpoints."""

from fastapi import APIRouter

from app.api.v1.endpoints import work_orders

api_router = APIRouter()
api_router.include_router(work_orders.router, prefix="/work-orders", tags=["work-orders"])
