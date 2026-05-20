"""Vendor sync — pull SC users into our `vendors` table.

ServiceChannel's `users` table is the canonical list of people at the
Brenk provider account. Many of those users are actually sub-vendor
contacts that Brenk added (under `admin+N@brenkfacilityservices.com`
emails). We sync them into `vendors` so Daryl doesn't have to maintain
two lists.

Match strategy (in order):
1. **`sc_user_id` exact match** — the common case once sync has run
   in this environment before.
2. **Email match** — fallback for cross-environment moves. SC's
   sandbox and production are separate databases with separate ID
   sequences, so a vendor synced from sandbox has a different
   `sc_user_id` than the same person in production. Matching on
   email (which is environment-stable for Brenk) lets the production
   sync find existing rows and update their `sc_user_id` instead of
   creating duplicates. Critical so Daryl's curated notes survive the
   sandbox → production cutover.
3. Otherwise insert a new row.

Brenk-internal fields (markup_notes, payment_terms, contact_preference,
communication_notes, mobile_app_capable, trade_specializations, notes,
is_active) are **never overwritten** by sync — Daryl curates them; SC
has no opinion. Newly-created rows default to `is_active=NOT
user.Disabled`. Manually-created vendors (`sc_user_id IS NULL` AND no
matching email) are left untouched.

One-way sync. Edits in our app stay in our DB; nothing is pushed back
to SC.
"""

from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.work_order import Vendor
from app.services.servicechannel.client import ServiceChannelClient

logger = structlog.get_logger(__name__)


async def _upsert_user_as_vendor(
    session: AsyncSession,
    user: dict[str, Any],
) -> tuple[Vendor, bool]:
    """Get-or-create the vendor row for one SC user.

    Returns `(vendor, created)` where `created` is True when a new row
    was inserted (False for an update).
    """
    user_id = user.get("Id")
    if user_id is None:
        raise ValueError(f"SC user payload missing Id: {user}")

    name = (user.get("FullName") or user.get("UserName") or f"SC user {user_id}").strip()
    email = (user.get("Email") or user.get("UserName") or None)
    disabled = bool(user.get("Disabled", False))

    # Match strategy 1: exact sc_user_id.
    existing = (
        await session.execute(select(Vendor).where(Vendor.sc_user_id == user_id))
    ).scalar_one_or_none()

    # Match strategy 2: email fallback (case-insensitive). Covers the
    # sandbox -> production cutover, where the SAME human gets a
    # different SC user id but keeps their email. We update the
    # existing row's sc_user_id to the new value.
    if existing is None and email:
        existing = (
            await session.execute(
                select(Vendor).where(func.lower(Vendor.email) == email.lower())
            )
        ).scalar_one_or_none()
        if existing is not None:
            logger.info(
                "vendor matched by email; updating sc_user_id",
                vendor_id=existing.id,
                old_sc_user_id=existing.sc_user_id,
                new_sc_user_id=user_id,
                email=email,
            )
            existing.sc_user_id = user_id

    if existing is None:
        vendor = Vendor(
            sc_user_id=user_id,
            name=name,
            email=email,
            is_active=not disabled,
            raw_data=user,
        )
        session.add(vendor)
        await session.flush()
        return vendor, True

    # Update synced fields only. Brenk-internal fields are left alone.
    existing.name = name
    existing.email = email
    existing.raw_data = user
    await session.flush()
    return existing, False


async def sync_vendors_from_sc(
    sc_client: ServiceChannelClient | None = None,
) -> dict[str, Any]:
    """Pull all users from SC and upsert into vendors.

    Returns a summary dict: {"fetched", "created", "updated", "errors"}.
    Per-user failures are logged and counted; one bad row doesn't abort
    the batch.
    """
    client = sc_client or ServiceChannelClient()

    logger.info("vendor sync starting")
    users = await client.list_users()
    summary: dict[str, Any] = {
        "fetched": len(users),
        "created": 0,
        "updated": 0,
        "errors": [],
    }

    async with AsyncSessionLocal() as session:
        for user in users:
            try:
                _, created = await _upsert_user_as_vendor(session, user)
                if created:
                    summary["created"] += 1
                else:
                    summary["updated"] += 1
            except Exception as exc:
                logger.exception("vendor upsert failed", sc_user_id=user.get("Id"))
                summary["errors"].append(
                    {"sc_user_id": user.get("Id"), "error": str(exc)}
                )
        await session.commit()

    logger.info(
        "vendor sync complete",
        fetched=summary["fetched"],
        created=summary["created"],
        updated=summary["updated"],
        errors=len(summary["errors"]),
    )
    return summary
