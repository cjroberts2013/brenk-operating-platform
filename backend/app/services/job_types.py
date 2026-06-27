"""Brenk job-type taxonomy — the DB-backed shared vocabulary.

Single source of truth for job categories (AI categorization + profit reports)
AND vendor skills. Read from the `job_types` table so Daryl can add/rename
types from the dashboard. `DEFAULT_JOB_TYPES` is the initial seed (also applied
by the creating migration) and the fallback when the table is empty.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.work_order import JobType

# (name, description, is_catchall) in display order. The description guides the
# Gemini categorizer. Mirrors the migration seed; also the empty-table fallback.
DEFAULT_JOB_TYPES: list[tuple[str, str, bool]] = [
    ("Electrical", "Wiring, outlets, lighting, panels, electrical repairs.", False),
    ("Plumbing", "Leaks, drains, pipes, water heaters, fixtures, backflow.", False),
    ("Roofing", "Roof leaks, membrane, flashing, roof repair/replacement.", False),
    ("Doors", "Doors — roll-up, overhead, swing, hardware, openers.", False),
    ("Windows & Glass", "Windows, storefront glass, glazing, broken panes.", False),
    ("Gates & Access", "Gates, keypads, access control, gate motors/operators.", False),
    ("Fencing", "Fences, posts, perimeter repair (chain-link, wood).", False),
    ("HVAC", "Heating, cooling, ventilation, thermostats, AC units.", False),
    ("Appliance Repair", "Appliances — refrigeration, laundry, kitchen equipment.", False),
    ("Flooring", "Floors, tile, carpet, concrete floor finishes.", False),
    ("Painting", "Interior/exterior painting, coatings, surface prep.", False),
    ("Drywall", "Drywall / sheet rock — hang, patch, texture, repair.", False),
    ("General Building", "General carpentry/handyman/interior building repairs.", False),
    ("Exterior Building", "Exterior walls, siding, gutters, soffit, stucco.", False),
    ("Trash Removal", "Bulk trash, junk hauling, debris/dumpster removal.", False),
    ("Concrete & Asphalt", "Concrete, asphalt, sidewalks, curbs (not striping).", False),
    ("Parking Lot Striping", "Pavement striping, markings, stenciling.", False),
    ("Landscaping", "Landscaping, grounds, irrigation, tree/shrub work.", False),
    ("Pest Control", "Pest, rodent, insect control and exclusion.", False),
    ("Locksmith", "Locks, rekeying, keys, lock hardware.", False),
    ("Security", "Cameras, alarms, security systems, monitoring.", False),
    ("Other", "Anything that doesn't clearly fit another type.", True),
]


async def list_job_types(session: AsyncSession, *, include_inactive: bool = False) -> list[JobType]:
    """All job types in display order (active only by default)."""
    stmt = select(JobType)
    if not include_inactive:
        stmt = stmt.where(JobType.is_active.is_(True))
    stmt = stmt.order_by(JobType.position.asc(), JobType.name.asc())
    return list((await session.execute(stmt)).scalars().all())


async def list_job_type_names(
    session: AsyncSession, *, include_inactive: bool = False
) -> list[str]:
    """Job-type names in display order."""
    return [jt.name for jt in await list_job_types(session, include_inactive=include_inactive)]


async def is_valid_job_type(session: AsyncSession, name: str | None) -> bool:
    """True if `name` is an active job type (used to validate manual overrides)."""
    if not name:
        return False
    return name in set(await list_job_type_names(session))
