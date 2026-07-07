"""Work-order notes sync.

Fetches the full notes thread for a single work order from SC's
/v3/workorders/{id}/notes endpoint and upserts each note into wo_notes.

Called from the WO orchestrator whenever an incoming WO payload's
`Notes.Count.Total` differs from what we have stored. Also exposed as a
standalone Procrastinate task so notes can be re-synced for a specific WO
on demand (e.g., from a future "refresh" button in the dashboard).
"""

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.work_order import WorkOrder, WorkOrderNote
from app.services.access_flags import apply_note_flag
from app.services.servicechannel.client import ServiceChannelClient
from app.services.sync.transformers import extract_note_fields

logger = structlog.get_logger(__name__)


async def upsert_note(
    session: AsyncSession,
    payload: dict[str, Any],
    work_order_id: int,
) -> tuple[WorkOrderNote, bool]:
    """Get-or-create a WorkOrderNote row from an SC note payload.

    Natural key is `sc_note_id`. If absent (shouldn't happen for
    SC-sourced notes, but the column is nullable to leave room for
    Brenk-originated notes later), inserts a new row unconditionally.
    Returns (note, created) — created is True only for genuinely new
    rows, which is what gates access-flag scanning (an old note that
    re-syncs must not re-open a dismissed flag).
    """
    fields = extract_note_fields(payload)
    sc_note_id = fields["sc_note_id"]

    if sc_note_id is not None:
        stmt = select(WorkOrderNote).where(WorkOrderNote.sc_note_id == sc_note_id)
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            for key, value in fields.items():
                setattr(existing, key, value)
            existing.work_order_id = work_order_id
            await session.flush()
            return existing, False

    note = WorkOrderNote(work_order_id=work_order_id, **fields)
    session.add(note)
    await session.flush()
    return note, True


async def sync_notes_for_work_order(
    session: AsyncSession,
    sc_client: ServiceChannelClient,
    work_order: WorkOrder,
) -> int:
    """Pull every note for the given WO from SC and upsert each.

    Returns the number of notes upserted. The caller is responsible for
    committing the session.

    Note: this does NOT delete local notes when SC reports fewer notes
    than we have. If SC ever shrinks a thread (rare but possible —
    e.g., a user deletes a note), we'll be left with stale rows. Revisit
    if it becomes a real issue.
    """
    response = await sc_client.get_work_order_notes(work_order.sc_work_order_id)
    notes_payload: list[dict[str, Any]] = response.get("Notes", []) if response else []

    for note in notes_payload:
        row, created = await upsert_note(session, note, work_order.id)
        if created:
            # New human note — the "store manager added a note days later
            # saying wait for the unit key" case lands here.
            apply_note_flag(work_order, row)

    logger.info(
        "notes synced for work order",
        sc_work_order_id=work_order.sc_work_order_id,
        count=len(notes_payload),
    )
    return len(notes_payload)


async def sync_notes_for_sc_work_order_id(
    session: AsyncSession,
    sc_client: ServiceChannelClient,
    sc_work_order_id: int,
) -> int:
    """Look up the WO by its SC id and sync its notes. Raises if the WO
    isn't in our DB yet (run a WO sync first).
    """
    stmt = select(WorkOrder).where(WorkOrder.sc_work_order_id == sc_work_order_id)
    wo = (await session.execute(stmt)).scalar_one_or_none()
    if wo is None:
        raise ValueError(
            f"work order sc_id={sc_work_order_id} not found locally; "
            "sync the WO before syncing its notes"
        )
    return await sync_notes_for_work_order(session, sc_client, wo)
