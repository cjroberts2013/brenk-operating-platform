"""v1 API router — aggregates all v1 endpoints.

All v1 endpoints require a valid Supabase JWT in the Authorization header.
The `/health` endpoint at the top level remains unauthenticated for
deployment health probes.
"""

from fastapi import APIRouter, Depends

from app.api.v1.endpoints import (
    categories,
    dashboard,
    invoices,
    locations,
    reports,
    storefront,
    trades,
    vendors,
    webhooks,
    work_orders,
)
from app.core.auth import get_current_user

# Authenticated routes — every request needs a valid Supabase JWT.
api_router = APIRouter(dependencies=[Depends(get_current_user)])
api_router.include_router(work_orders.router, prefix="/work-orders", tags=["work-orders"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
api_router.include_router(vendors.router, prefix="/vendors", tags=["vendors"])
api_router.include_router(locations.router, prefix="/locations", tags=["locations"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_router.include_router(trades.router, prefix="/trades", tags=["trades"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(storefront.admin_router, prefix="/storefront", tags=["storefront-admin"])

# Public routes — no auth dep. Mounted separately by `main.py` so
# the dependency chain on `api_router` doesn't apply. Keep this
# list very short; everything else should require auth.
public_router = APIRouter()
public_router.include_router(
    storefront.public_router, prefix="/storefront", tags=["storefront-public"]
)
# SC webhook receiver — authenticity is the HMAC signature, not a JWT.
public_router.include_router(
    webhooks.router, prefix="/webhooks", tags=["webhooks"]
)
