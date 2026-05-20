"""Trade endpoints.

GET — populates the Vendor form's trade-specializations multi-select.
The list is small (~20 trades sourced from SC) so we return everything
in one shot, no pagination.

POST — lets the user create a Brenk-internal trade (no `sc_trade_id`)
when SC's catalog is missing one. Case-insensitive uniqueness check
prevents creating "Roofing" alongside SC's "ROOFING".
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.models.work_order import Trade
from app.schemas.work_order import TradeRef

router = APIRouter()


class TradeCreate(BaseModel):
    """Body for POST /api/v1/trades."""

    name: str = Field(min_length=1, max_length=100)


@router.get("/", response_model=list[TradeRef])
async def list_trades(
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> list[TradeRef]:
    """List all trades, ordered alphabetically by name."""
    stmt = select(Trade).order_by(Trade.name.asc())
    rows = (await db.execute(stmt)).scalars().all()
    return [TradeRef.model_validate(row) for row in rows]


@router.post(
    "/",
    response_model=TradeRef,
    status_code=http_status.HTTP_201_CREATED,
)
async def create_trade(
    payload: TradeCreate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> TradeRef:
    """Create a Brenk-internal trade (no `sc_trade_id`).

    Returns 409 if a trade with the same name (case-insensitive) already
    exists — keeps the catalog clean and avoids 'Roofing' / 'ROOFING'
    duplicates.
    """
    name = payload.name.strip()

    existing = (
        await db.execute(
            select(Trade).where(func.lower(Trade.name) == name.lower())
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"trade '{existing.name}' already exists",
        )

    trade = Trade(name=name, sc_trade_id=None)
    db.add(trade)
    await db.commit()
    await db.refresh(trade)
    return TradeRef.model_validate(trade)
