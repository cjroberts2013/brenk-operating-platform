"""Build and submit ServiceChannel invoices for work orders (Phase 1.5).

The submit path verified 2026-06-10 (see servicechannel-api.md "Spike
results"): POST /v3/invoices with marked-up amounts. Hard rules baked in:

- **Confidentiality**: vendor costs and markup % NEVER leave our DB. The
  payload carries only the marked-up, client-facing amounts.
- CubeSmart requires resolution text (`InvoiceText`) and an alphanumeric
  invoice number matching ^\\w*$ (no dashes/spaces), unique, no reuse.
- `InvoiceTotal` must be <= the WO's NTE.
- We always submit the Line Item form (one labor line / one material
  line at the marked-up amounts). CubeSmart's repair categories REQUIRE
  line items; for others they're optional, so including them is safe.
- 8.25% Texas sales tax is added on the marked-up subtotal — matches
  how Daryl invoices manually (verified against real invoices 101581
  and 101584, both exactly 8.25%). InvoiceTotal includes the tax and
  is the number checked against NTE.

The preview is computed server-side and shown verbatim in the confirm
dialog, so what Daryl approves is exactly what gets sent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice
from app.models.work_order import WorkOrder
from app.services.pipeline import classify

logger = structlog.get_logger(__name__)

# SC invoice states that block a new submit for the same WO. Void and
# Rejected don't block: voided is dead, and the documented fix-flow for
# rejected is correct-and-resubmit.
_BLOCKING_INVOICE_STATUSES = {
    "Open",
    "Approved",
    "On Hold",
    "Reviewed",
    "Disputed",
    "Paid",
}

_CENT = Decimal("0.01")

# Texas standard sales tax rate, applied to every invoice's marked-up
# subtotal — Daryl's real invoices all carry exactly this rate.
TX_SALES_TAX_RATE = Decimal("0.0825")


class InvoiceSubmitError(Exception):
    """Submit failed — message is operator-facing."""


def _q2(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def marked_up_amount(cost: Decimal | None, markup_percent: Decimal) -> Decimal:
    """Client-facing amount for one cost component: cost x (1 + markup%)."""
    if cost is None:
        return Decimal("0.00")
    return _q2(cost * (Decimal("1") + markup_percent / Decimal("100")))


def make_invoice_number(sc_number: str, prior_count: int) -> str:
    """BRENK{wo number}, alphanumeric only (CubeSmart's ^\\w*$ rule).
    Re-invoicing the same WO (after a void/reject) appends R2, R3, ..."""
    base = "BRENK" + re.sub(r"[^0-9A-Za-z_]", "", sc_number.strip())
    if prior_count > 0:
        return f"{base}R{prior_count + 1}"
    return base


@dataclass
class InvoicePreview:
    """Server-computed submit preview. `problems` non-empty = not submittable
    (the resolution-text problem clears when the dialog supplies text)."""

    invoice_number: str
    labor_amount: Decimal
    material_amount: Decimal
    subtotal: Decimal
    tax_amount: Decimal  # 8.25% TX sales tax on the marked-up subtotal
    invoice_total: Decimal  # subtotal + tax; checked against NTE
    nte: Decimal | None
    resolution_text: str | None  # prefill for the dialog's InvoiceText
    problems: list[str] = field(default_factory=list)

    @property
    def eligible(self) -> bool:
        return not self.problems


def compute_preview(
    wo: WorkOrder,
    prior_invoice_count: int,
    *,
    invoice_text: str | None = None,
) -> InvoicePreview:
    """Pure preview/validation from WO state. No I/O."""
    override = wo.brenk_total_override
    markup = wo.brenk_markup_percent

    if override is not None:
        # Daryl priced by the total. We have no labor/material split, so
        # the whole pre-tax total bills as a single labor line.
        labor = _q2(override)
        material = Decimal("0.00")
    else:
        labor = (
            marked_up_amount(wo.brenk_labor_cost, markup) if markup is not None else Decimal("0.00")
        )
        material = (
            marked_up_amount(wo.brenk_material_cost, markup)
            if markup is not None
            else Decimal("0.00")
        )
    subtotal = labor + material
    tax = _q2(subtotal * TX_SALES_TAX_RATE)
    total = subtotal + tax

    problems: list[str] = []

    stage = classify(wo.primary_status, wo.extended_status, wo.assigned_vendor_id is not None)
    if stage != "ready_to_invoice":
        status_str = wo.primary_status + (f" / {wo.extended_status}" if wo.extended_status else "")
        problems.append(
            f"Work order isn't ready to invoice in ServiceChannel (status: {status_str})."
        )

    if override is not None:
        if subtotal <= 0:
            problems.append("Total bill must be greater than zero.")
    elif markup is None:
        problems.append("No markup or total set. Price the invoice in the markup helper first.")
    elif (wo.brenk_labor_cost is None and wo.brenk_material_cost is None) or subtotal <= 0:
        problems.append("No vendor costs entered. Enter labor and/or material cost first.")

    if wo.nte is not None and total > wo.nte:
        problems.append(
            f"Total bill ${total} (incl. ${tax} sales tax) exceeds NTE ${wo.nte}. "
            "ServiceChannel will reject it — lower the markup or a cost."
        )

    if wo.sc_invoice_status in _BLOCKING_INVOICE_STATUSES:
        problems.append(
            f"An SC invoice already exists for this work order "
            f"(#{wo.sc_invoice_number}, status {wo.sc_invoice_status}). Void it in "
            "ServiceChannel before submitting a new one."
        )

    resolution = (invoice_text or "").strip() or (wo.resolution or "").strip() or None
    if not resolution:
        problems.append("Resolution text is required by the client. Describe the work completed.")

    return InvoicePreview(
        invoice_number=make_invoice_number(wo.sc_number, prior_invoice_count),
        labor_amount=labor,
        material_amount=material,
        subtotal=subtotal,
        tax_amount=tax,
        invoice_total=total,
        nte=wo.nte,
        resolution_text=resolution,
        problems=problems,
    )


def build_payload(preview: InvoicePreview, wo: WorkOrder) -> dict[str, Any]:
    """The exact POST /v3/invoices body. Marked-up amounts only."""
    now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload: dict[str, Any] = {
        "InvoiceNumber": preview.invoice_number,
        "WoIdentifier": wo.sc_number.strip(),
        "InvoiceText": preview.resolution_text,
        "InvoiceTotal": float(preview.invoice_total),
        "InvoiceTax": float(preview.tax_amount),
        "InvoiceDate": now_iso,
        "InvoiceDateDTO": now_iso,
        "InvoiceAmountsDetails": {
            "LaborAmount": float(preview.labor_amount),
            "MaterialAmount": float(preview.material_amount),
            "TravelAmount": 0,
            "FreightAmount": 0,
            "OtherAmount": 0,
        },
    }
    # Line-item form: category-gated WOs require it; harmless otherwise.
    # One synthetic line per component at the marked-up amount (Brenk pays
    # subs flat — we don't track real tech hours/rates).
    if preview.labor_amount > 0:
        payload["Labors"] = [
            {
                "SkillLevel": "2",  # Technician
                "LaborType": "1",  # Regular
                "NumOfTech": "1",
                "HourlyRate": float(preview.labor_amount),
                "Hours": 1,
                "Amount": float(preview.labor_amount),
            }
        ]
    if preview.material_amount > 0:
        payload["Materials"] = [
            {
                "Description": "Parts & materials",
                "PartNum": "",
                "UnitType": "1",  # Each
                "UnitPrice": float(preview.material_amount),
                "Quantity": 1,
                "Amount": float(preview.material_amount),
            }
        ]
    return payload


async def count_prior_invoices(db: AsyncSession, wo: WorkOrder, sc_env: str) -> int:
    """How many SC invoices already exist for this WO (any status) —
    drives the R2/R3 suffix so numbers stay unique after a void."""
    return (
        await db.execute(
            select(func.count(Invoice.id)).where(
                Invoice.sc_env == sc_env,
                Invoice.wo_tracking_number == wo.sc_work_order_id,
            )
        )
    ).scalar_one()


async def submit_invoice(
    db: AsyncSession,
    client: Any,  # ServiceChannelClient (Any avoids an import cycle in tests)
    wo: WorkOrder,
    *,
    sc_env: str,
    invoice_text: str | None = None,
) -> InvoicePreview:
    """Validate, POST to SC, and record the result on the WO.

    Raises InvoiceSubmitError with an operator-facing message on any
    validation problem or SC rejection. Caller commits.
    """
    prior = await count_prior_invoices(db, wo, sc_env)
    preview = compute_preview(wo, prior, invoice_text=invoice_text)
    if preview.problems:
        raise InvoiceSubmitError(" ".join(preview.problems))

    payload = build_payload(preview, wo)
    logger.info(
        "submitting_sc_invoice",
        wo=wo.sc_number,
        invoice_number=preview.invoice_number,
        total=str(preview.invoice_total),
    )
    try:
        response = await client.create_invoice(payload)
    except Exception as exc:
        # Surface SC's rejection text and remember it on the WO so the UI
        # can show "Last submit failed: ..." after the dialog closes.
        message = _humanize_sc_error(str(exc))
        wo.sc_invoice_last_error = message[:1000]
        logger.warning("sc_invoice_submit_rejected", wo=wo.sc_number, error=message)
        raise InvoiceSubmitError(message) from exc

    sc_invoice_id = response.get("Id") if isinstance(response, dict) else None
    wo.sc_invoice_id = sc_invoice_id
    wo.sc_invoice_number = preview.invoice_number
    wo.sc_invoice_status = "Open"
    wo.sc_invoice_total = preview.invoice_total
    wo.sc_invoice_submitted_at = datetime.now(UTC)
    wo.sc_invoice_last_error = None
    logger.info(
        "sc_invoice_submitted",
        wo=wo.sc_number,
        sc_invoice_id=sc_invoice_id,
        invoice_number=preview.invoice_number,
    )
    return preview


def _humanize_sc_error(raw: str) -> str:
    """Pull the ErrorMessage out of an SC error body when present."""
    match = re.search(r'"ErrorMessage"\s*:\s*"([^"]+)"', raw)
    if match:
        return f"ServiceChannel rejected the invoice: {match.group(1)}"
    return f"ServiceChannel rejected the invoice: {raw[:300]}"
