"""v1 API router — aggregates all v1 endpoints.

All v1 endpoints require a valid Supabase JWT in the Authorization header.
The `/health` endpoint at the top level remains unauthenticated for
deployment health probes.
"""

from fastapi import APIRouter, Depends

from app.api.v1.endpoints import vendors, work_orders
from app.core.auth import get_current_user

api_router = APIRouter(dependencies=[Depends(get_current_user)])
api_router.include_router(work_orders.router, prefix="/work-orders", tags=["work-orders"])
api_router.include_router(vendors.router, prefix="/vendors", tags=["vendors"])
