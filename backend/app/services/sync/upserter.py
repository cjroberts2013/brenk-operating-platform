"""Async upsert helpers that turn ServiceChannel payloads into ORM rows.

Each upsert function:
1. Looks up an existing row by its SC natural key (sc_subscriber_id, etc.)
2. If found, updates its columns from the payload
3. If not, creates a new row
4. Returns the (flushed, id-assigned) ORM instance

Commits are the caller's responsibility — these functions flush so that
generated PKs are available, but they do not commit.
"""

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.work_order import (
    Client,
    Location,
    Trade,
    WorkOrder,
    WorkOrderStatusHistory,
)
from app.services.sync.transformers import (
    extract_client_fields,
    extract_location_fields,
    extract_trade_fields,
    extract_work_order_fields,
)

logger = structlog.get_logger(__name__)


async def upsert_client(session: AsyncSession, subscriber: dict[str, Any]) -> Client:
    """Get-or-create a Client row from a payload's Subscriber sub-object."""
    fields = extract_client_fields(subscriber)
    stmt = select(Client).where(Client.sc_subscriber_id == fields["sc_subscriber_id"])
    existing = (await session.execute(stmt)).scalar_one_or_none()

    if existing is None:
        client = Client(**fields)
        session.add(client)
        await session.flush()
        return client

    for key, value in fields.items():
        setattr(existing, key, value)
    await session.flush()
    return existing


async def upsert_trade(session: AsyncSession, payload: dict[str, Any]) -> Trade | None:
    """Get-or-create a Trade row from a work order payload.

    Returns None if the payload has neither a Trade name nor a TradeId.
    Prefers sc_trade_id for lookup (numeric, stable), falls back to name.
    """
    fields = extract_trade_fields(payload)
    if fields is None:
        return None

    if fields.get("sc_trade_id") is not None:
        stmt = select(Trade).where(Trade.sc_trade_id == fields["sc_trade_id"])
    else:
        stmt = select(Trade).where(Trade.name == fields["name"])
    existing = (await session.execute(stmt)).scalar_one_or_none()

    if existing is None:
        trade = Trade(**fields)
        session.add(trade)
        await session.flush()
        return trade

    if fields.get("name") and existing.name != fields["name"]:
        existing.name = fields["name"]
    if fields.get("sc_trade_id") and existing.sc_trade_id != fields["sc_trade_id"]:
        existing.sc_trade_id = fields["sc_trade_id"]
    await session.flush()
    return existing


async def upsert_location(
    session: AsyncSession, location: dict[str, Any], client_id: int
) -> Location:
    """Get-or-create a Location row, linking it to the given client."""
    fields = extract_location_fields(location)
    stmt = select(Location).where(Location.sc_location_id == fields["sc_location_id"])
    existing = (await session.execute(stmt)).scalar_one_or_none()

    if existing is None:
        loc = Location(client_id=client_id, **fields)
        session.add(loc)
        await session.flush()
        return loc

    existing.client_id = client_id
    for key, value in fields.items():
        setattr(existing, key, value)
    await session.flush()
    return existing


async def upsert_work_order(session: AsyncSession, payload: dict[str, Any]) -> WorkOrder:
    """Upsert a work order and all its dependent reference rows.

    Orchestrates upserts of the Client, Location, and Trade rows that the
    work order references, then upserts the work order itself. Detects
    status changes against the existing row (if any) and emits a
    WorkOrderStatusHistory entry when the primary or extended status moves.
    """
    fields = extract_work_order_fields(payload)

    # Resolve reference rows first so we have FK ids
    client = await upsert_client(session, payload["Subscriber"])
    location = await upsert_location(session, payload["Location"], client.id)
    trade = await upsert_trade(session, payload)

    stmt = select(WorkOrder).where(WorkOrder.sc_work_order_id == fields["sc_work_order_id"])
    existing = (await session.execute(stmt)).scalar_one_or_none()

    if existing is None:
        wo = WorkOrder(
            client_id=client.id,
            location_id=location.id,
            trade_id=trade.id if trade else None,
            last_synced_at=datetime.now(UTC),
            **fields,
        )
        session.add(wo)
        await session.flush()
        logger.info(
            "work_order created",
            sc_work_order_id=wo.sc_work_order_id,
            sc_number=wo.sc_number,
        )
        return wo

    status_changed = (
        existing.primary_status != fields["primary_status"]
        or existing.extended_status != fields["extended_status"]
    )
    if status_changed:
        session.add(
            WorkOrderStatusHistory(
                work_order_id=existing.id,
                primary_status=fields["primary_status"],
                extended_status=fields["extended_status"],
                source="servicechannel",
            )
        )
        logger.info(
            "work_order status changed",
            sc_work_order_id=existing.sc_work_order_id,
            from_status=f"{existing.primary_status}/{existing.extended_status}",
            to_status=f"{fields['primary_status']}/{fields['extended_status']}",
        )

    existing.client_id = client.id
    existing.location_id = location.id
    existing.trade_id = trade.id if trade else None
    existing.last_synced_at = datetime.now(UTC)
    for key, value in fields.items():
        setattr(existing, key, value)
    await session.flush()
    return existing
