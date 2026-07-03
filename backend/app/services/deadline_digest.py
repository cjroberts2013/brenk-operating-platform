"""Daily turnaround-deadline digest email for Daryl.

Builds one morning email listing every at-risk work order (overdue or
due within DUE_SOON_DAYS), split into two sections by who owes the
next move:

    Needs your action     WAITING FOR QUOTE, DISPATCH CONFIRMED, ...
    Waiting on CubeSmart  WAITING FOR APPROVAL (proposal sent)

Each row carries the WO number linked to our dashboard, the store,
the SC extended status, and how far past (or before) the deadline it
is, plus a ServiceChannel deep link. Classification comes from
`app.services.deadlines` — the same definitions the dashboard panel
and the `?deadline=` list filter use, so the email and the UI always
agree.

`build_digest_email` is a pure function over `DigestItem`s so it can
be unit-tested without a database; `fetch_digest_items` does the one
query + URL building (it, not deadlines.py, imports settings — keeps
the classification module dependency-free).
"""

from __future__ import annotations

import html as html_lib
import math
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.work_order import WorkOrder
from app.services.deadlines import (
    classify_urgency,
    days_past_deadline,
    deadline_filter_clauses,
    deadline_for,
    section_for,
)

# Keep the first digest (which inventories a months-old backlog)
# scannable: cap each section and point at the filtered list for the
# rest.
MAX_ROWS_PER_SECTION = 25

# Palette mirrors the storefront quote email (endpoints/storefront.py)
# so everything Daryl gets from the platform looks the same.
_NAVY = "#0e2a47"
_SIGNAL = "#1d5fb8"
_INK = "#16202b"
_SLATE = "#8a93a0"
_LINE = "#e3e7ec"
_MIST = "#f5f7f9"
_RED = "#b42318"
_AMBER = "#b54708"

_SECTION_TITLES = {
    "needs_action": "Needs your action",
    "waiting_on_cubesmart": "Waiting on CubeSmart",
}


@dataclass(frozen=True)
class DigestItem:
    """One at-risk WO, fully resolved for rendering (no ORM refs)."""

    sc_number: str
    location: str
    extended_status: str | None
    deadline: datetime
    days_past_deadline: float  # positive = overdue
    urgency: str  # 'overdue' | 'due_soon'
    section: str  # 'needs_action' | 'waiting_on_cubesmart'
    dashboard_url: str
    sc_url: str


def due_label(days_past: float) -> str:
    """Human bucket for a signed days-past-deadline value.

    >= 1 day past   ->  "Overdue 12d"
    within a day    ->  "Due today"
    >= 1 day out    ->  "Due in 2d"
    """
    if days_past >= 1:
        return f"Overdue {int(days_past)}d"
    if days_past > -1:
        return "Due today"
    return f"Due in {math.ceil(-days_past)}d"


async def fetch_digest_items(session: AsyncSession) -> list[DigestItem]:
    """Query every at-risk WO and resolve it to a renderable DigestItem.

    Sorted most-overdue-first within each section; needs_action rows
    sort ahead of waiting_on_cubesmart so the actionable work leads.
    """
    settings = get_settings()
    now = datetime.now(UTC)

    stmt = (
        select(WorkOrder)
        .options(selectinload(WorkOrder.location))
        .where(*deadline_filter_clauses("at_risk"))
    )
    rows = (await session.execute(stmt)).scalars().all()

    items: list[DigestItem] = []
    for wo in rows:
        deadline = deadline_for(wo.scheduled_date, wo.call_date)
        urgency = classify_urgency(deadline, now)
        if deadline is None or urgency not in {"overdue", "due_soon"}:
            continue  # SQL and Python must agree; belt-and-suspenders
        location = (wo.location.name if wo.location else None) or (
            wo.location.store_id if wo.location else None
        )
        items.append(
            DigestItem(
                sc_number=wo.sc_number or str(wo.sc_work_order_id),
                location=location or "Unknown location",
                extended_status=wo.extended_status,
                deadline=deadline,
                days_past_deadline=days_past_deadline(deadline, now),
                urgency=urgency,
                section=section_for(wo.extended_status),
                dashboard_url=f"{settings.DASHBOARD_BASE_URL}/work-orders/{wo.id}",
                sc_url=(f"{settings.SC_WEB_URL}/sc/wo/Workorders/index?id={wo.sc_work_order_id}"),
            )
        )

    items.sort(key=lambda i: (i.section != "needs_action", -i.days_past_deadline))
    return items


def _all_at_risk_url() -> str:
    return f"{get_settings().DASHBOARD_BASE_URL}/work-orders?deadline=at_risk"


def _section_rows_html(section_items: list[DigestItem]) -> str:
    esc = html_lib.escape
    rows: list[str] = []
    for item in section_items[:MAX_ROWS_PER_SECTION]:
        color = _RED if item.urgency == "overdue" else _AMBER
        status = esc((item.extended_status or "").title() or "No extended status")
        rows.append(
            f'<tr><td style="padding:10px 16px;border-top:1px solid {_LINE};">'
            f'<a href="{esc(item.dashboard_url)}" '
            f'style="color:{_SIGNAL};font-weight:600;text-decoration:none;">'
            f"WO #{esc(item.sc_number)}</a>"
            f'<span style="color:{_SLATE};"> · </span>'
            f'<span style="color:{_INK};">{esc(item.location)}</span>'
            f'<div style="font-size:13px;margin-top:2px;color:{_SLATE};">'
            f'{status} · <span style="color:{color};font-weight:600;">'
            f"{due_label(item.days_past_deadline)}</span>"
            f' · <a href="{esc(item.sc_url)}" '
            f'style="color:{_SIGNAL};text-decoration:none;">View in SC</a>'
            "</div></td></tr>"
        )
    overflow = len(section_items) - MAX_ROWS_PER_SECTION
    if overflow > 0:
        rows.append(
            f'<tr><td style="padding:10px 16px;border-top:1px solid {_LINE};'
            f'font-size:13px;color:{_SLATE};">'
            f'+{overflow} more — <a href="{html_lib.escape(_all_at_risk_url())}" '
            f'style="color:{_SIGNAL};text-decoration:none;">view all in the dashboard</a>'
            "</td></tr>"
        )
    return "".join(rows)


def build_digest_email(items: list[DigestItem], now: datetime) -> tuple[str, str, str]:
    """Render the digest. Returns (subject, html, text).

    Caller decides whether to send — an empty `items` list should not
    reach this function (the task skips sending instead).
    """
    overdue = sum(1 for i in items if i.urgency == "overdue")
    due_soon = sum(1 for i in items if i.urgency == "due_soon")

    parts = []
    if overdue:
        parts.append(f"{overdue} overdue")
    if due_soon:
        parts.append(f"{due_soon} due soon")
    subject = f"CubeSmart turnaround: {', '.join(parts) or 'status'}"

    sections_html: list[str] = []
    sections_text: list[str] = []
    for section_key in ("needs_action", "waiting_on_cubesmart"):
        section_items = [i for i in items if i.section == section_key]
        if not section_items:
            continue
        title = _SECTION_TITLES[section_key]
        sections_html.append(
            '<tr><td style="padding:20px 28px 0;">'
            f'<div style="font-size:12px;font-weight:700;color:{_INK};'
            'text-transform:uppercase;letter-spacing:0.04em;">'
            f"{title} ({len(section_items)})</div>"
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="margin-top:8px;border:1px solid {_LINE};border-radius:8px;">'
            f"{_section_rows_html(section_items)}"
            "</table></td></tr>"
        )
        text_lines = [f"{title} ({len(section_items)}):"]
        for item in section_items[:MAX_ROWS_PER_SECTION]:
            status = (item.extended_status or "").title() or "No extended status"
            text_lines.append(
                f"  WO #{item.sc_number} — {item.location} — {status} — "
                f"{due_label(item.days_past_deadline)}\n"
                f"    Dashboard: {item.dashboard_url}\n"
                f"    ServiceChannel: {item.sc_url}"
            )
        overflow = len(section_items) - MAX_ROWS_PER_SECTION
        if overflow > 0:
            text_lines.append(f"  +{overflow} more: {_all_at_risk_url()}")
        sections_text.append("\n".join(text_lines))

    date_label = now.astimezone(UTC).strftime("%b %-d, %Y")
    html = (
        f'<div style="background:{_MIST};padding:24px 0;'
        'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:{_MIST};"><tr><td align="center">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" '
        'style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;'
        f'overflow:hidden;border:1px solid {_LINE};">'
        f'<tr><td style="background:{_NAVY};padding:22px 28px;">'
        '<div style="color:#ffffff;font-size:18px;font-weight:700;letter-spacing:0.04em;">'
        "BRENK FACILITY SERVICES</div>"
        f'<div style="color:#9fb1c4;font-size:13px;margin-top:4px;">'
        f"Turnaround deadline digest · {date_label}</div>"
        "</td></tr>"
        f'<tr><td style="padding:20px 28px 0;"><div style="color:{_INK};font-size:15px;">'
        f"<strong>{overdue} overdue</strong> · {due_soon} due within 2 days"
        "</div></td></tr>"
        f"{''.join(sections_html)}"
        '<tr><td style="padding:20px 28px 24px;">'
        f'<div style="border-top:1px solid {_LINE};padding-top:14px;color:{_SLATE};'
        'font-size:12px;line-height:1.5;">'
        "Sent every morning while any CubeSmart work order is past or "
        "nearing its 3-5 day turnaround. "
        f'<a href="{html_lib.escape(_all_at_risk_url())}" '
        f'style="color:{_SIGNAL};text-decoration:none;">See all at-risk work orders</a>.'
        "</div></td></tr>"
        "</table></td></tr></table></div>"
    )

    text = (
        f"Turnaround deadline digest — {date_label}\n"
        f"{overdue} overdue · {due_soon} due within 2 days\n\n"
        + "\n\n".join(sections_text)
        + f"\n\nAll at-risk work orders: {_all_at_risk_url()}"
    )

    return subject, html, text
