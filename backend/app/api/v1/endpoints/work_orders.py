"""Work order endpoints.

Reads from the local database (populated by the sync worker). All
queries return data that's already been transformed from SC payloads
into our schema — see `app.services.sync` for the sync pipeline.
"""

import base64
import mimetypes
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.session import get_async_db
from app.models.invoice import Invoice
from app.models.work_order import (
    Client,
    GateCode,
    Location,
    Vendor,
    WorkOrder,
    WorkOrderNote,
)
from app.schemas.work_order import (
    InvoiceSubmitPreview,
    InvoiceSubmitRequest,
    InvoiceSummary,
    VendorMessage,
    WorkOrderAttachment,
    WorkOrderDetail,
    WorkOrderListResponse,
    WorkOrderNoteRef,
    WorkOrderSummary,
)
from app.services.email import is_valid_email, send_email
from app.services.invoice_submit import (
    InvoiceSubmitError,
    compute_preview,
    count_prior_invoices,
    submit_invoice,
)
from app.services.pipeline import (
    STAGE_BY_KEY,
    classify,
    is_stuck,
    stage_filter_clauses,
    stuck_filter_clause,
)
from app.services.servicechannel.client import ServiceChannelClient
from app.services.sync.work_orders import sync_all_work_orders
from app.services.vendor_message import (
    MAX_TOTAL_ATTACHMENT_BYTES,
    compose_vendor_message,
    text_to_html,
)

logger = structlog.get_logger(__name__)


class WorkOrderUpdate(BaseModel):
    """PATCH body for a work order. Only Brenk-internal fields are
    writable in Phase 1 — SC-owned fields (status, dates, etc.) are
    not exposed here.

    All fields are optional. Set a field to `null` to clear it; omit
    a field to leave the DB column untouched. We use Pydantic's
    `model_fields_set` in the endpoint to tell "absent" from "null"
    — without that, `field: int | None = None` collapses the two.
    """

    assigned_vendor_id: int | None = Field(default=None)
    brenk_labor_cost: Decimal | None = Field(
        default=None,
        ge=0,
        description=(
            "Labor portion of what Brenk pays the sub-vendor, in USD. Tracked "
            "separately from materials for analytics. Brenk-confidential — "
            "never pushed to SC."
        ),
    )
    brenk_material_cost: Decimal | None = Field(
        default=None,
        ge=0,
        description=(
            "Materials portion of what Brenk pays the sub-vendor, in USD. "
            "Tracked separately from labor for analytics. Brenk-confidential "
            "— never pushed to SC."
        ),
    )
    brenk_markup_percent: Decimal | None = Field(
        default=None,
        ge=0,
        le=1000,
        description=(
            "Brenk's chosen markup % on this WO. Range 0-1000 - Daryl's "
            "real-world band is 65-200, but we allow zero and outliers. "
            "Brenk-confidential — never pushed to SC."
        ),
    )
    brenk_total_override: Decimal | None = Field(
        default=None,
        ge=0,
        description=(
            "Directly-entered pre-tax total bill — used when Daryl prices a "
            "WO by the total instead of vendor cost + markup. When set, it is "
            "the source of truth for the total and the markup % is left "
            "unknown. Brenk-confidential — never pushed to SC as a breakdown."
        ),
    )
    # Frontend sends `paid: "now"` to stamp paid_at = now(), or
    # `paid: "clear"` to clear it back to null. Omitting the field
    # leaves the column untouched. We avoid a free-form datetime here
    # so backdating is intentional (would need a separate endpoint).
    paid: Literal["now", "clear"] | None = Field(default=None)
    # Same action shape as `paid`: `notified: "now"` stamps
    # `brenk_vendor_notified_at = now()` (Daryl texted/called the
    # assigned sub-vendor), `"clear"` resets it to null.
    notified: Literal["now", "clear"] | None = Field(default=None)


class WorkOrderSyncStatus(BaseModel):
    """When the work-order sync last touched the database.

    `last_synced_at` is the MAX of `work_orders.last_synced_at` — the
    UTC timestamp the sync upserter stamps onto every row it touches.
    Null only on a freshly-migrated, empty database.
    """

    last_synced_at: datetime | None
    work_order_count: int


class WorkOrderSyncSummary(BaseModel):
    """Result of POST /api/v1/work-orders/sync."""

    fetched: int
    upserted: int
    notes_synced: int
    errors: int


router = APIRouter()


_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 200

# SC invoice statuses that mean an invoice is live but not yet paid/terminal.
# Drives the "Sent" invoice tab. Terminal states (Paid/Void/Rejected) excluded.
_ACTIVE_INVOICE_STATUSES = ["Open", "Approved", "On Hold", "Reviewed", "Disputed"]


@router.get("/", response_model=WorkOrderListResponse)
async def list_work_orders(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    status: Annotated[
        str | None,
        Query(description="Filter by primary status (e.g., 'IN PROGRESS', 'COMPLETED')"),
    ] = None,
    client_id: Annotated[int | None, Query(description="Filter by internal client id")] = None,
    trade_id: Annotated[int | None, Query(description="Filter by internal trade id")] = None,
    assigned_vendor_id: Annotated[
        int | None,
        Query(description="Filter by assigned Brenk sub-vendor"),
    ] = None,
    updated_since: Annotated[
        datetime | None,
        Query(description="Only return WOs with sc_updated_date >= this ISO 8601 timestamp"),
    ] = None,
    q: Annotated[
        str | None,
        Query(
            description=(
                "Free-text search across WO number, SC purchase number, problem "
                "code, caller, description, store id, location name, and client "
                "name. Case-insensitive, substring match."
            ),
        ),
    ] = None,
    stage: Annotated[
        str | None,
        Query(
            description=(
                "Pipeline-funnel stage key (pending_acceptance, dispatched, "
                "work_complete, ready_to_invoice, invoiced). Applies the same "
                "composite filter the dashboard uses for counting — so a tile's "
                "count equals the list page's row count for that stage."
            ),
        ),
    ] = None,
    invoice_tab: Annotated[
        Literal["ready_to_markup", "marked_up", "sent", "rejected", "paid"] | None,
        Query(
            description=(
                "Invoice-queue tab filter. Post-submit tabs derive from the "
                "synced SC invoice state (sc_invoice_status), falling back to "
                "primary_status=INVOICED for WOs invoiced before webhooks. "
                "ready_to_markup / marked_up: ready_to_invoice stage with no "
                "active SC invoice. sent: an active SC invoice, not paid. "
                "rejected: sc_invoice_status=Rejected. paid: paid by SC or marked "
                "paid in our app."
            ),
        ),
    ] = None,
    stuck: Annotated[
        bool,
        Query(
            description=(
                "If true, return only work orders that are stuck: in a "
                "non-terminal stage past that stage's age threshold (same "
                "definition the dashboard uses)."
            ),
        ),
    ] = False,
    page: Annotated[int, Query(ge=1, description="1-indexed page number")] = 1,
    page_size: Annotated[
        int,
        Query(ge=1, le=_MAX_PAGE_SIZE, description="Records per page (max 200)"),
    ] = _DEFAULT_PAGE_SIZE,
) -> WorkOrderListResponse:
    """List work orders, filtered and paginated.

    Ordering: highest ServiceChannel work order id first. SC issues ids
    monotonically over time, so this puts the newest WOs at the top —
    matches how SC's own UI orders them, which is what Daryl is used to.
    """
    filters = []
    if status is not None:
        filters.append(WorkOrder.primary_status == status)
    if client_id is not None:
        filters.append(WorkOrder.client_id == client_id)
    if trade_id is not None:
        filters.append(WorkOrder.trade_id == trade_id)
    if assigned_vendor_id is not None:
        filters.append(WorkOrder.assigned_vendor_id == assigned_vendor_id)
    if updated_since is not None:
        filters.append(WorkOrder.sc_updated_date >= updated_since)
    if stage is not None:
        # Unknown stage keys fall through to a `false()` clause that
        # matches nothing — better than silently returning everything.
        if stage not in STAGE_BY_KEY:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(f"unknown stage {stage!r}; must be one of: {', '.join(STAGE_BY_KEY)}"),
            )
        filters.extend(stage_filter_clauses(stage))

    # Invoice-queue tab filters. The post-submit tabs derive from the
    # SC invoice state synced via webhooks (work_orders.sc_invoice_*),
    # with a fallback to primary_status=INVOICED for WOs invoiced before
    # webhooks. Conditions are written NULL-safely so each WO lands in
    # exactly one tab. Shared single source of truth with the frontend.
    if invoice_tab is not None:
        # Paid: by SC, or marked paid in our app (manual override).
        paid_cond = or_(
            WorkOrder.brenk_paid_at.is_not(None),
            WorkOrder.sc_paid_at.is_not(None),
            WorkOrder.sc_invoice_status == "Paid",
        )
        not_paid = and_(
            WorkOrder.brenk_paid_at.is_(None),
            WorkOrder.sc_paid_at.is_(None),
            WorkOrder.sc_invoice_status.is_distinct_from("Paid"),
        )
        # An active (non-terminal) SC invoice exists for this WO.
        active_invoice = or_(
            WorkOrder.sc_invoice_status.in_(_ACTIVE_INVOICE_STATUSES),
            and_(  # legacy: invoiced in SC before webhook sync existed
                WorkOrder.primary_status == "INVOICED",
                WorkOrder.sc_invoice_status.is_(None),
            ),
        )
        # No active/terminal SC invoice blocking re-invoicing (NULL-safe).
        no_open_invoice = and_(
            or_(
                WorkOrder.sc_invoice_status.is_(None),
                WorkOrder.sc_invoice_status.notin_([*_ACTIVE_INVOICE_STATUSES, "Rejected", "Paid"]),
            ),
            or_(
                WorkOrder.primary_status != "INVOICED",
                WorkOrder.sc_invoice_status.is_not(None),
            ),
        )

        # "Priced" = a markup % OR a directly-entered total. Either moves a
        # WO from "ready to mark up" into "marked up, ready to send".
        unpriced = and_(
            WorkOrder.brenk_markup_percent.is_(None),
            WorkOrder.brenk_total_override.is_(None),
        )
        priced = or_(
            WorkOrder.brenk_markup_percent.is_not(None),
            WorkOrder.brenk_total_override.is_not(None),
        )

        if invoice_tab == "ready_to_markup":
            filters.extend(stage_filter_clauses("ready_to_invoice"))
            filters.append(unpriced)
            filters.append(no_open_invoice)
            filters.append(not_paid)
        elif invoice_tab == "marked_up":
            filters.extend(stage_filter_clauses("ready_to_invoice"))
            filters.append(priced)
            filters.append(no_open_invoice)
            filters.append(not_paid)
        elif invoice_tab == "sent":
            filters.append(active_invoice)
            filters.append(not_paid)
        elif invoice_tab == "rejected":
            filters.append(WorkOrder.sc_invoice_status == "Rejected")
            filters.append(not_paid)
        elif invoice_tab == "paid":
            filters.append(paid_cond)

    # Stuck filter: WOs sitting in any stage past its age threshold.
    # Same source-of-truth thresholds as the dashboard's is_stuck().
    if stuck:
        filters.append(stuck_filter_clause())

    # Free-text search. We OR across columns the operator is likely to
    # type — WO number, SC purchase number, problem code, caller free
    # text, description, and the joined Location/Client name fields.
    # Outer joins so a WO with no client/location still matches on its
    # own columns. Substring match via ILIKE — postgres handles case
    # folding natively, no need to LOWER() both sides.
    needs_search_joins = False
    if q is not None and q.strip():
        needle = f"%{q.strip()}%"
        needs_search_joins = True
        filters.append(
            or_(
                WorkOrder.sc_number.ilike(needle),
                WorkOrder.sc_purchase_number.ilike(needle),
                WorkOrder.problem_code.ilike(needle),
                WorkOrder.caller.ilike(needle),
                WorkOrder.description.ilike(needle),
                Location.store_id.ilike(needle),
                Location.name.ilike(needle),
                Client.name.ilike(needle),
                Client.short_name.ilike(needle),
            )
        )

    def _apply_filters(stmt):
        if needs_search_joins:
            stmt = stmt.outerjoin(Location, WorkOrder.location_id == Location.id)
            stmt = stmt.outerjoin(Client, WorkOrder.client_id == Client.id)
        if filters:
            stmt = stmt.where(*filters)
        return stmt

    count_stmt = _apply_filters(select(func.count(WorkOrder.id)).select_from(WorkOrder))
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(WorkOrder)
        .options(
            selectinload(WorkOrder.client),
            selectinload(WorkOrder.location),
            selectinload(WorkOrder.trade),
            selectinload(WorkOrder.assigned_vendor),
        )
        .order_by(WorkOrder.sc_work_order_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    stmt = _apply_filters(stmt)
    rows = (await db.execute(stmt)).scalars().all()

    items: list[WorkOrderSummary] = []
    for row in rows:
        summary = WorkOrderSummary.model_validate(row)
        # Tag each row with whether it's stuck so the list can flag it
        # inline, using the same classify()/is_stuck() as the dashboard.
        stage_key = classify(
            row.primary_status,
            row.extended_status,
            row.assigned_vendor_id is not None,
        )
        summary.is_stuck = is_stuck(stage_key, row.sc_updated_date) if stage_key else False
        items.append(summary)

    return WorkOrderListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/sync-status", response_model=WorkOrderSyncStatus)
async def get_work_order_sync_status(
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> WorkOrderSyncStatus:
    """Return when the WO sync last touched the local DB.

    Cheap query (single MAX + COUNT), called by the WO list page header
    to render "Last synced 12 minutes ago · 341 work orders".

    NOTE: registered above the `/{work_order_id}` path-param route so
    `/sync-status` doesn't get swallowed as a numeric id parse error.
    """
    last, count = (
        await db.execute(select(func.max(WorkOrder.last_synced_at), func.count(WorkOrder.id)))
    ).one()
    return WorkOrderSyncStatus(last_synced_at=last, work_order_count=count)


@router.post("/sync", response_model=WorkOrderSyncSummary)
async def trigger_work_order_sync() -> WorkOrderSyncSummary:
    """Trigger an immediate sync from SC. Runs inline (not via the
    Procrastinate queue) so the operator sees the result in their
    response. The scheduled hourly sync still runs in the background.

    Idempotent. Calling repeatedly is fine — the upserter is keyed on
    `sc_work_order_id` and counts each WO once per call.
    """
    summary = await sync_all_work_orders()
    return WorkOrderSyncSummary(
        fetched=summary["fetched"],
        upserted=summary["upserted"],
        notes_synced=summary["notes_synced"],
        errors=len(summary["errors"]),
    )


async def _fetch_work_order(
    db: AsyncSession,
    work_order_id: int,
    *,
    populate_existing: bool = False,
) -> WorkOrder:
    """Load a WO with all relationships eager-loaded, or raise 404.

    Centralized so the GET and PATCH endpoints can't drift apart on which
    relationships they eager-load — both call this helper.

    `populate_existing=True` bypasses the session's identity-map cache —
    use it after a PATCH so the response reflects the freshly-updated
    relationships (otherwise SQLAlchemy returns the in-memory copy that
    still has the pre-update relationship snapshot).
    """
    stmt = (
        select(WorkOrder)
        .options(
            selectinload(WorkOrder.client),
            selectinload(WorkOrder.location),
            selectinload(WorkOrder.trade),
            selectinload(WorkOrder.assigned_vendor),
        )
        .where(WorkOrder.id == work_order_id)
    )
    if populate_existing:
        stmt = stmt.execution_options(populate_existing=True)
    wo = (await db.execute(stmt)).scalar_one_or_none()
    if wo is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"work order {work_order_id} not found",
        )
    return wo


@router.get("/{work_order_id}", response_model=WorkOrderDetail)
async def get_work_order(
    work_order_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> WorkOrderDetail:
    """Get a single work order by its internal database id.

    Returns 404 if no such work order exists.
    """
    wo = await _fetch_work_order(db, work_order_id)
    return await _to_detail(db, wo)


async def _to_detail(db: AsyncSession, wo: WorkOrder) -> WorkOrderDetail:
    """Validate the WO into a detail schema and attach its linked SC
    invoice record(s) (latest first), synced from invoice webhooks."""
    detail = WorkOrderDetail.model_validate(wo)
    if wo.sc_work_order_id is not None:
        invoices = (
            (
                await db.execute(
                    select(Invoice)
                    .where(Invoice.wo_tracking_number == wo.sc_work_order_id)
                    .order_by(Invoice.sc_updated_date.desc().nullslast(), Invoice.id.desc())
                )
            )
            .scalars()
            .all()
        )
        detail.sc_invoices = [InvoiceSummary.model_validate(inv) for inv in invoices]
    return detail


@router.get("/{work_order_id}/invoice-preview", response_model=InvoiceSubmitPreview)
async def get_invoice_preview(
    work_order_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> InvoiceSubmitPreview:
    """Preview exactly what submitting this WO's invoice to SC would send.

    Pure computation from local state — no SC call. The confirm dialog
    renders this verbatim; the submit endpoint recomputes it
    authoritatively, so the preview can't drift from what's sent.
    """
    wo = await _fetch_work_order(db, work_order_id)
    settings = get_settings()
    prior = await count_prior_invoices(db, wo, settings.SC_ENVIRONMENT)
    preview = compute_preview(wo, prior)
    return InvoiceSubmitPreview(
        eligible=preview.eligible,
        problems=preview.problems,
        invoice_number=preview.invoice_number,
        labor_amount=preview.labor_amount,
        material_amount=preview.material_amount,
        subtotal=preview.subtotal,
        tax_amount=preview.tax_amount,
        invoice_total=preview.invoice_total,
        nte=preview.nte,
        resolution_text=preview.resolution_text,
    )


@router.post("/{work_order_id}/submit-invoice", response_model=WorkOrderDetail)
async def submit_work_order_invoice(
    work_order_id: int,
    body: InvoiceSubmitRequest,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> WorkOrderDetail:
    """Submit this WO's invoice to ServiceChannel (POST /v3/invoices).

    Validates server-side (markup set, total <= NTE, resolution text,
    no active SC invoice), sends the marked-up amounts only — vendor
    costs and markup % never leave our DB — and records the resulting
    SC invoice id/number/status on the WO. The invoice webhook then
    confirms and materializes the full invoice record.

    Returns 400 with an operator-facing message on validation failure
    or SC rejection (the rejection is also stored on
    `sc_invoice_last_error`).
    """
    wo = await _fetch_work_order(db, work_order_id)
    settings = get_settings()
    client = ServiceChannelClient()
    try:
        await submit_invoice(
            db,
            client,
            wo,
            sc_env=settings.SC_ENVIRONMENT,
            invoice_text=body.invoice_text,
        )
    except InvoiceSubmitError as exc:
        # Persist sc_invoice_last_error when the rejection set it.
        await db.commit()
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await db.commit()
    fresh = await _fetch_work_order(db, work_order_id, populate_existing=True)
    return await _to_detail(db, fresh)


@router.patch("/{work_order_id}", response_model=WorkOrderDetail)
async def update_work_order(
    work_order_id: int,
    payload: WorkOrderUpdate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> WorkOrderDetail:
    """Update Brenk-internal fields on a work order.

    Writable in Phase 1:
      - `assigned_vendor_id` — pass null to unassign.
      - `brenk_labor_cost`, `brenk_material_cost` — labor + material
        components of what Brenk pays the sub-vendor. Tracked
        separately for analytics; total vendor cost = labor +
        material. Distinct from NTE (the client-side ceiling).
        Pass a decimal to set, null to clear. Brenk-confidential.
      - `brenk_markup_percent` — pass a decimal to set, null to clear.
        Setting (transitioning from null to a value) auto-stamps
        `brenk_marked_up_at = now()`. Re-setting (already non-null)
        leaves `brenk_marked_up_at` alone — the original markup
        moment is what we want to remember.
      - `paid` — pass "now" to stamp `brenk_paid_at = now()`, or
        "clear" to reset to null. Omit to leave alone.
      - `notified` — pass "now" to stamp
        `brenk_vendor_notified_at = now()` (Daryl texted/called the
        assigned sub-vendor), or "clear" to reset to null. Omit to
        leave alone.

    SC-owned fields (status, dates, notes_count, etc.) are never
    touched here — those flow in via the sync worker.
    """
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        # No-op PATCH: surface the current state, don't error.
        return await get_work_order(work_order_id, db)

    wo = await _fetch_work_order(db, work_order_id)

    if "assigned_vendor_id" in update_data:
        new_vendor_id = update_data["assigned_vendor_id"]
        if new_vendor_id is not None:
            exists = (
                await db.execute(select(Vendor.id).where(Vendor.id == new_vendor_id))
            ).scalar_one_or_none()
            if exists is None:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail=f"vendor {new_vendor_id} not found",
                )
        wo.assigned_vendor_id = new_vendor_id

    if "brenk_labor_cost" in update_data:
        wo.brenk_labor_cost = update_data["brenk_labor_cost"]
    if "brenk_material_cost" in update_data:
        wo.brenk_material_cost = update_data["brenk_material_cost"]

    # A WO is "priced" once it has either a markup % (cost-based path) or a
    # directly-entered total (override path). brenk_marked_up_at tracks the
    # first-priced moment across BOTH paths: stamp when the WO transitions
    # from unpriced -> priced, clear when it goes back to fully unpriced,
    # leave alone otherwise. Compute the before-state before mutating.
    was_priced = wo.brenk_markup_percent is not None or wo.brenk_total_override is not None

    if "brenk_markup_percent" in update_data:
        wo.brenk_markup_percent = update_data["brenk_markup_percent"]
    if "brenk_total_override" in update_data:
        wo.brenk_total_override = update_data["brenk_total_override"]

    if "brenk_markup_percent" in update_data or "brenk_total_override" in update_data:
        now_priced = wo.brenk_markup_percent is not None or wo.brenk_total_override is not None
        if not now_priced:
            wo.brenk_marked_up_at = None
        elif not was_priced:
            wo.brenk_marked_up_at = datetime.now(UTC)

    if "paid" in update_data:
        action = update_data["paid"]
        if action == "now":
            wo.brenk_paid_at = datetime.now(UTC)
        elif action == "clear":
            wo.brenk_paid_at = None

    if "notified" in update_data:
        action = update_data["notified"]
        if action == "now":
            wo.brenk_vendor_notified_at = datetime.now(UTC)
        elif action == "clear":
            wo.brenk_vendor_notified_at = None

    await db.commit()
    # populate_existing rebuilds the in-memory WO from the new SELECT
    # results — picks up the server-side onupdate (`updated_at`) plus
    # any relationship that changed. Without it, the session's identity
    # map returns the pre-PATCH copy of the WO.
    fresh = await _fetch_work_order(db, work_order_id, populate_existing=True)
    return await _to_detail(db, fresh)


@router.get("/{work_order_id}/notes", response_model=list[WorkOrderNoteRef])
async def list_work_order_notes(
    work_order_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> list[WorkOrderNoteRef]:
    """List notes for a single work order, oldest first.

    Returns 404 if the work order itself doesn't exist. Returns an empty
    list (not 404) if the WO exists but has no notes.
    """
    wo_exists = (
        await db.execute(select(WorkOrder.id).where(WorkOrder.id == work_order_id))
    ).scalar_one_or_none()
    if wo_exists is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"work order {work_order_id} not found",
        )

    stmt = (
        select(WorkOrderNote)
        .where(WorkOrderNote.work_order_id == work_order_id)
        .order_by(WorkOrderNote.note_number.asc().nullslast(), WorkOrderNote.id.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [WorkOrderNoteRef.model_validate(row) for row in rows]


async def _sc_work_order_id(db: AsyncSession, work_order_id: int) -> int:
    """Resolve our WO id to its SC numeric id, or raise 404."""
    sc_id = (
        await db.execute(select(WorkOrder.sc_work_order_id).where(WorkOrder.id == work_order_id))
    ).scalar_one_or_none()
    if sc_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"work order {work_order_id} not found",
        )
    return sc_id


def _sanitize_filename(name: str | None, fallback: str) -> str:
    """Strip header-breaking characters from a download filename."""
    cleaned = (name or "").replace("\r", "").replace("\n", "").replace('"', "").strip()
    return cleaned or fallback


async def _active_gate_codes(db: AsyncSession, location_id: int | None) -> list[GateCode]:
    """The active gate codes for a location, oldest first (empty if none)."""
    if location_id is None:
        return []
    return list(
        (
            await db.execute(
                select(GateCode)
                .where(GateCode.location_id == location_id, GateCode.is_active.is_(True))
                .order_by(GateCode.created_at.asc())
            )
        )
        .scalars()
        .all()
    )


@router.get("/{work_order_id}/attachments", response_model=list[WorkOrderAttachment])
async def list_work_order_attachments(
    work_order_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> list[WorkOrderAttachment]:
    """List a work order's attachments, fetched live from ServiceChannel.

    404 if the WO doesn't exist; empty list if it has none. The raw SC
    `Uri` (a short-lived presigned URL) is never returned — files are
    fetched through the download endpoint below.
    """
    sc_id = await _sc_work_order_id(db, work_order_id)
    client = ServiceChannelClient()
    try:
        raw = await client.get_work_order_attachments(sc_id)
    except Exception as exc:
        logger.warning("sc_attachments_list_failed", work_order_id=work_order_id, error=str(exc))
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail="Couldn't load attachments from ServiceChannel.",
        ) from exc

    items: list[WorkOrderAttachment] = []
    for att in raw:
        name = att.get("Name")
        items.append(
            WorkOrderAttachment(
                id=att["Id"],
                name=name,
                description=att.get("Description"),
                note_id=att.get("NoteId"),
                timestamp=att.get("TimeStamp"),
                is_invoice_digital_copy=bool(att.get("IsInvoiceDigitalCopy", False)),
                upload_by=att.get("UploadBy"),
                content_type=(mimetypes.guess_type(name)[0] if name else None),
            )
        )
    return items


@router.get("/{work_order_id}/attachments/{attachment_id}/download")
async def download_work_order_attachment(
    work_order_id: int,
    attachment_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    download: Annotated[bool, Query(description="Force a download (attachment) vs inline")] = False,
) -> Response:
    """Stream an attachment's bytes through our backend.

    Resolves a fresh presigned `Uri` from SC at request time (they expire
    ~30 min), fetches the bytes server-side, and returns them with the
    right content type + filename. Keeps the SC token + transient Uri off
    the client. 404 if the WO or attachment id is unknown.
    """
    sc_id = await _sc_work_order_id(db, work_order_id)
    client = ServiceChannelClient()
    try:
        raw = await client.get_work_order_attachments(sc_id)
    except Exception as exc:
        logger.warning("sc_attachments_list_failed", work_order_id=work_order_id, error=str(exc))
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail="Couldn't load attachments from ServiceChannel.",
        ) from exc

    match = next((a for a in raw if a.get("Id") == attachment_id), None)
    if match is None or not match.get("Uri"):
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"attachment {attachment_id} not found for work order {work_order_id}",
        )

    try:
        content, content_type = await client.fetch_attachment_bytes(match["Uri"])
    except Exception as exc:
        logger.warning("sc_attachment_fetch_failed", attachment_id=attachment_id, error=str(exc))
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail="Couldn't download the attachment from ServiceChannel.",
        ) from exc

    filename = _sanitize_filename(match.get("Name"), f"attachment-{attachment_id}")
    disposition = "attachment" if download else "inline"
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


@router.get("/{work_order_id}/vendor-message", response_model=VendorMessage)
async def get_vendor_message(
    work_order_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> VendorMessage:
    """Compose the ready-to-send vendor notification message for a WO.

    Gathers the WO + location (address) + active gate codes + attachment
    names + assigned vendor contact, and returns one plain-text body (for
    SMS or email) plus a suggested subject. Attachments are best-effort —
    an SC hiccup just drops the photo names, not the whole message.
    """
    wo = await _fetch_work_order(db, work_order_id)
    active_gate_codes = await _active_gate_codes(db, wo.location_id)

    attachments: list[dict] = []
    if wo.attachments_count > 0:
        try:
            attachments = await ServiceChannelClient().get_work_order_attachments(
                wo.sc_work_order_id
            )
        except Exception as exc:
            logger.warning(
                "vendor_message_attachments_failed", work_order_id=work_order_id, error=str(exc)
            )

    vendor = wo.assigned_vendor
    composed = compose_vendor_message(
        wo=wo,
        store_id=wo.location.store_id if wo.location else None,
        location_name=wo.location.name if wo.location else None,
        location_raw_data=wo.location.raw_data if wo.location else None,
        trade_name=wo.trade.name if wo.trade else None,
        active_gate_codes=active_gate_codes,
        attachments=attachments,
        vendor=vendor,
    )
    return VendorMessage(
        subject=composed.subject,
        body=composed.body,
        to_phone=vendor.phone if vendor else None,
        to_email=vendor.email if vendor else None,
        contact_preference=vendor.contact_preference if vendor else None,
        photo_count=len(attachments),
    )


class VendorEmailResult(BaseModel):
    """Result of POST /work-orders/{id}/send-vendor-email."""

    sent: bool
    to_email: str
    photos_attached: int
    photos_total: int


@router.post("/{work_order_id}/send-vendor-email", response_model=VendorEmailResult)
async def send_vendor_email(
    work_order_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> VendorEmailResult:
    """Email the composed vendor notification (photos attached) via Resend.

    Sends to the assigned vendor's email with Daryl as reply-to, attaches
    the WO's photos (best-effort, capped), then stamps
    `brenk_vendor_notified_at`. 400 if no vendor / no vendor email; 502 if
    the email fails to send.
    """
    wo = await _fetch_work_order(db, work_order_id)
    vendor = wo.assigned_vendor
    if vendor is None:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Assign a sub-vendor before emailing them.",
        )
    if not vendor.email:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"{vendor.name} has no email on file. Add one on the vendor record.",
        )
    if not is_valid_email(vendor.email):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{vendor.name}'s email ({vendor.email}) doesn't look valid. "
                "Fix it on the vendor record before sending."
            ),
        )

    active_gate_codes = await _active_gate_codes(db, wo.location_id)

    # Raw SC attachments (carry the Uri + Name we need to fetch the bytes).
    raw_attachments: list[dict] = []
    if wo.attachments_count > 0:
        try:
            raw_attachments = await ServiceChannelClient().get_work_order_attachments(
                wo.sc_work_order_id
            )
        except Exception as exc:
            logger.warning(
                "vendor_email_attachments_failed", work_order_id=work_order_id, error=str(exc)
            )

    composed = compose_vendor_message(
        wo=wo,
        store_id=wo.location.store_id if wo.location else None,
        location_name=wo.location.name if wo.location else None,
        location_raw_data=wo.location.raw_data if wo.location else None,
        trade_name=wo.trade.name if wo.trade else None,
        active_gate_codes=active_gate_codes,
        attachments=raw_attachments,
        vendor=vendor,
    )

    # Fetch + base64 the photo bytes, capped so a huge set degrades to
    # fewer attachments rather than a rejected send.
    client = ServiceChannelClient()
    attachments_payload: list[dict[str, str]] = []
    total_bytes = 0
    for att in raw_attachments:
        uri = att.get("Uri")
        if not uri:
            continue
        try:
            content, _ctype = await client.fetch_attachment_bytes(uri)
        except Exception as exc:
            logger.warning(
                "vendor_email_attachment_fetch_failed",
                attachment_id=att.get("Id"),
                error=str(exc),
            )
            continue
        if total_bytes + len(content) > MAX_TOTAL_ATTACHMENT_BYTES:
            logger.warning("vendor_email_attachment_cap_reached", work_order_id=work_order_id)
            break
        total_bytes += len(content)
        attachments_payload.append(
            {
                "filename": _sanitize_filename(att.get("Name"), f"photo-{att.get('Id')}"),
                "content": base64.b64encode(content).decode("ascii"),
            }
        )

    settings = get_settings()
    sent = await send_email(
        subject=composed.subject,
        html=text_to_html(composed.body),
        text=composed.body,
        to=vendor.email,
        from_email=settings.VENDOR_FROM_EMAIL,
        reply_to=settings.QUOTE_TO_EMAIL,  # vendor replies go to Daryl
        attachments=attachments_payload or None,
    )
    if not sent:
        raise HTTPException(
            status_code=http_status.HTTP_502_BAD_GATEWAY,
            detail="Couldn't send the email (check the Resend configuration).",
        )

    wo.brenk_vendor_notified_at = datetime.now(UTC)
    await db.commit()
    logger.info(
        "vendor_email_sent",
        work_order_id=work_order_id,
        to=vendor.email,
        photos_attached=len(attachments_payload),
    )
    return VendorEmailResult(
        sent=True,
        to_email=vendor.email,
        photos_attached=len(attachments_payload),
        photos_total=len(raw_attachments),
    )
