"""Storefront endpoints.

Two routers in one module, mounted separately by `app.api.v1.__init__`:

- `public_router` — `GET /storefront`. **No auth.** Serves the
  marketing site at the bare domain (`brenkfacilityservices.com`).
- `admin_router` — `PATCH /storefront`, `PUT /storefront/services`.
  Authenticated. Mounted under the standard `api_router` so
  Supabase JWT auth applies.

The content table is treated as a **singleton** — there's always
exactly one row with `id = 1`. The GET endpoint auto-creates it
on first call if missing (so a fresh database still serves valid
JSON to the public site). PATCH operates on the same singleton.
"""

from __future__ import annotations

import html as html_lib
from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_async_db
from app.models.storefront import StorefrontContent, StorefrontService
from app.schemas.storefront import (
    QuoteRequest,
    QuoteResponse,
    StorefrontResponse,
    StorefrontServicesReplace,
    StorefrontUpdate,
)
from app.services.email import send_email

logger = structlog.get_logger(__name__)

public_router = APIRouter()
admin_router = APIRouter()


SINGLETON_ID = 1


async def _fetch_content(db: AsyncSession, *, populate_existing: bool = False) -> StorefrontContent:
    """Fetch the singleton row with services eagerly loaded.

    `populate_existing=True` after a commit forces SQLAlchemy to
    rebuild the in-memory object from the SELECT instead of
    returning the identity-map cached one — necessary because the
    `updated_at` server-onupdate value lives only in the DB until
    we re-select. Same pattern as the WO PATCH handler.
    """
    stmt = (
        select(StorefrontContent)
        .options(selectinload(StorefrontContent.services))
        .where(StorefrontContent.id == SINGLETON_ID)
    )
    if populate_existing:
        stmt = stmt.execution_options(populate_existing=True)
    return (await db.execute(stmt)).scalar_one()


async def _get_or_create_content(db: AsyncSession) -> StorefrontContent:
    """Fetch the singleton row, creating it if it doesn't exist yet.

    The public storefront page hits this endpoint on every request,
    so a fresh database (one before the first editor save) should
    still respond with valid JSON — all nullable fields just come
    back as null. The frontend renderer handles missing fields.
    """
    stmt = (
        select(StorefrontContent)
        .options(selectinload(StorefrontContent.services))
        .where(StorefrontContent.id == SINGLETON_ID)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        row = StorefrontContent(id=SINGLETON_ID)
        db.add(row)
        await db.commit()
        row = await _fetch_content(db, populate_existing=True)
    return row


@public_router.get("/", response_model=StorefrontResponse)
async def get_storefront(
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> StorefrontResponse:
    """Public — returns the current storefront content + services.

    Both the dashboard editor (initial form values) and the public
    marketing site consume this. No auth; the page is meant to be
    crawlable.
    """
    content = await _get_or_create_content(db)
    return StorefrontResponse.model_validate(content)


# Brand palette (mirrors frontend app/globals.css). Inline only —
# email clients (Outlook especially) drop <style> blocks, so every
# rule lives on the element. Table-based layout for the same reason.
_NAVY = "#0e2a47"
_SIGNAL = "#1d5fb8"
_INK = "#16202b"
_SLATE = "#8a93a0"
_LINE = "#e3e7ec"
_MIST = "#f5f7f9"


def _submitted_label() -> str:
    """Submission time in Brenk's local zone (Central), human-readable."""
    now = datetime.now(ZoneInfo("America/Chicago"))
    return now.strftime("%b %-d, %Y at %-I:%M %p CT")


def _phone_digits(phone: str | None) -> str:
    """Digits only, for a tel: href."""
    return "".join(c for c in (phone or "") if c.isdigit())


def _quote_email_html(payload: QuoteRequest, submitted: str) -> str:
    """Branded, inline-styled, table-based HTML lead notification."""
    esc = html_lib.escape
    name = esc(payload.name)
    email = esc(payload.email)
    message = esc(payload.message).replace("\n", "<br>")
    digits = _phone_digits(payload.phone)
    phone_cell = (
        f'<a href="tel:{digits}" style="color:{_SIGNAL};text-decoration:none;">'
        f"{esc(payload.phone)}</a>"
        if digits
        else '<span style="color:#586572;">Not provided</span>'
    )

    # Action buttons: reply (always) + call (only when a phone is given).
    reply_btn = (
        f'<a href="mailto:{email}" style="display:inline-block;background:{_SIGNAL};'
        "color:#ffffff;text-decoration:none;font-weight:600;font-size:15px;"
        f'padding:12px 22px;border-radius:6px;">Reply to {name}</a>'
    )
    call_btn = (
        f'<a href="tel:{digits}" style="display:inline-block;background:#ffffff;'
        f"color:{_NAVY};text-decoration:none;font-weight:600;font-size:15px;"
        f"padding:11px 22px;border-radius:6px;border:1.5px solid {_NAVY};"
        f'margin-left:10px;">Call {esc(payload.phone)}</a>'
        if digits
        else ""
    )

    return (
        f'<div style="background:{_MIST};padding:24px 0;'
        'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:{_MIST};"><tr><td align="center">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" '
        'style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;'
        f'overflow:hidden;border:1px solid {_LINE};">'
        # header
        f'<tr><td style="background:{_NAVY};padding:22px 28px;">'
        '<div style="color:#ffffff;font-size:18px;font-weight:700;letter-spacing:0.04em;">'
        "BRENK FACILITY SERVICES</div>"
        '<div style="color:#9fb1c4;font-size:13px;margin-top:4px;">New quote request</div>'
        "</td></tr>"
        # timestamp
        f'<tr><td style="padding:20px 28px 0;"><div style="color:{_SLATE};font-size:12.5px;">'
        f"Submitted {submitted}</div></td></tr>"
        # action buttons
        f'<tr><td style="padding:16px 28px 4px;">{reply_btn}{call_btn}</td></tr>'
        # details card
        '<tr><td style="padding:16px 28px 0;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border:1px solid {_LINE};border-radius:8px;"><tr>'
        f'<td style="padding:14px 16px;font-size:15px;color:{_INK};line-height:1.7;">'
        f"<strong>Name:</strong> {name}<br>"
        f'<strong>Email:</strong> <a href="mailto:{email}" '
        f'style="color:{_SIGNAL};text-decoration:none;">{email}</a><br>'
        f"<strong>Phone:</strong> {phone_cell}"
        "</td></tr></table></td></tr>"
        # message
        '<tr><td style="padding:18px 28px 0;">'
        f'<div style="font-size:12px;font-weight:700;color:{_INK};'
        'text-transform:uppercase;letter-spacing:0.04em;">Message</div>'
        f'<div style="margin-top:8px;padding:12px 16px;background:{_MIST};'
        f"border-left:3px solid {_SIGNAL};border-radius:4px;font-size:15px;"
        f'color:{_INK};line-height:1.55;">{message}</div></td></tr>'
        # footer
        '<tr><td style="padding:20px 28px 24px;">'
        f'<div style="border-top:1px solid {_LINE};padding-top:14px;color:{_SLATE};'
        'font-size:12px;line-height:1.5;">'
        f"Reply to this email to respond directly to {name}. "
        "Sent from the brenkfacilityservices.com quote form.</div></td></tr>"
        "</table></td></tr></table></div>"
    )


def _quote_email_text(payload: QuoteRequest, submitted: str) -> str:
    """Plain-text alternative. Always send alongside HTML: it improves
    deliverability and covers text-only clients."""
    return (
        "New quote request\n"
        f"Submitted {submitted}\n\n"
        f"Name: {payload.name}\n"
        f"Email: {payload.email}\n"
        f"Phone: {payload.phone or 'Not provided'}\n\n"
        f"Message:\n{payload.message}\n\n"
        "--\nReply to this email to respond directly to "
        f"{payload.name}.\nSent from the brenkfacilityservices.com quote form."
    )


@public_router.post("/quote", response_model=QuoteResponse)
async def submit_quote(payload: QuoteRequest) -> QuoteResponse:
    """Public — accept a 'Request a Quote' submission and email Daryl.

    No auth and no DB write: this is a stateless contact form. We always
    log the lead (so it survives even if email is down or unconfigured),
    then attempt the Resend send. A tripped honeypot is silently
    accepted without sending so bots don't learn they were filtered.
    """
    if payload.website:
        logger.info("storefront.quote.honeypot_tripped", email=payload.email)
        return QuoteResponse(ok=True, emailed=False)

    logger.info(
        "storefront.quote.received",
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        message_len=len(payload.message),
    )

    submitted = _submitted_label()
    emailed = await send_email(
        subject=f"Quote request from {payload.name}",
        html=_quote_email_html(payload, submitted),
        text=_quote_email_text(payload, submitted),
        reply_to=payload.email,
    )
    return QuoteResponse(ok=True, emailed=emailed)


@admin_router.patch("/", response_model=StorefrontResponse)
async def update_storefront(
    payload: StorefrontUpdate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> StorefrontResponse:
    """Authenticated — partial update of page-level content fields.

    Omit a field to leave it alone; set to `null` to clear. Same
    "absent vs explicit-null" handling as the WO PATCH — Pydantic's
    `model_fields_set` is the discriminator.
    """
    content = await _get_or_create_content(db)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(content, field, value)
    await db.commit()
    # Re-select with populate_existing so the server-side onupdate
    # `updated_at` value comes back live (Pydantic's model_validate
    # would otherwise lazy-load it and fail across async contexts).
    fresh = await _fetch_content(db, populate_existing=True)
    return StorefrontResponse.model_validate(fresh)


@admin_router.put("/services", response_model=StorefrontResponse)
async def replace_services(
    payload: StorefrontServicesReplace,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> StorefrontResponse:
    """Authenticated — replaces the entire services list.

    Editor sends the full desired list on every save. We delete +
    re-insert via cascade rather than diffing — simpler and at
    list sizes <20 the row churn doesn't matter.
    """
    content = await _get_or_create_content(db)

    # Wipe existing — cascade isn't going to fire on a relationship
    # `clear()` without flush, so we delete by setting the list to
    # empty and let SQLAlchemy's delete-orphan cascade do the work.
    content.services = []
    await db.flush()

    # Re-insert from the payload, preserving the client's sort_order.
    for item in payload.services:
        content.services.append(
            StorefrontService(
                content_id=content.id,
                sort_order=item.sort_order,
                title=item.title,
                description=item.description,
                icon=item.icon,
            )
        )
    await db.commit()
    fresh = await _fetch_content(db, populate_existing=True)
    return StorefrontResponse.model_validate(fresh)
