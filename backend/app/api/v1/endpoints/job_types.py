"""Job-type taxonomy management endpoints.

The shared vocabulary behind AI categorization and vendor skills. Daryl
manages it from Settings — add a type as a new trade arises, rename one
(which cascades to existing work orders so profit history stays intact),
or retire one (soft, so history is preserved).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.models.work_order import JobType, WorkOrder
from app.schemas.job_type import JobTypeCreate, JobTypeRef, JobTypeUpdate

router = APIRouter()


async def _fetch(db: AsyncSession, job_type_id: int) -> JobType:
    jt = (await db.execute(select(JobType).where(JobType.id == job_type_id))).scalar_one_or_none()
    if jt is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"job type {job_type_id} not found",
        )
    return jt


async def _name_conflict(db: AsyncSession, name: str, *, exclude_id: int | None = None) -> bool:
    stmt = select(JobType.id).where(func.lower(JobType.name) == name.lower())
    if exclude_id is not None:
        stmt = stmt.where(JobType.id != exclude_id)
    return (await db.execute(stmt)).first() is not None


@router.get("/", response_model=list[JobTypeRef])
async def list_job_types_endpoint(
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> list[JobTypeRef]:
    """Every job type (active + retired), in display order — for management."""
    stmt = select(JobType).order_by(JobType.position.asc(), JobType.name.asc())
    rows = (await db.execute(stmt)).scalars().all()
    return [JobTypeRef.model_validate(r) for r in rows]


@router.post("/", response_model=JobTypeRef, status_code=http_status.HTTP_201_CREATED)
async def create_job_type(
    payload: JobTypeCreate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> JobTypeRef:
    """Create a new job type. 409 on a duplicate name (case-insensitive)."""
    name = payload.name.strip()
    if await _name_conflict(db, name):
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"job type '{name}' already exists",
        )
    # Append after the last type but keep the catch-all ("Other") last.
    max_non_catchall = (
        await db.execute(select(func.max(JobType.position)).where(JobType.is_catchall.is_(False)))
    ).scalar()
    position = (max_non_catchall or 0) + 1
    jt = JobType(
        name=name,
        description=(payload.description or "").strip() or None,
        position=position,
        is_active=True,
        is_catchall=False,
    )
    db.add(jt)
    await db.commit()
    await db.refresh(jt)
    return JobTypeRef.model_validate(jt)


@router.patch("/{job_type_id}", response_model=JobTypeRef)
async def update_job_type(
    job_type_id: int,
    payload: JobTypeUpdate,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> JobTypeRef:
    """Rename / re-describe / activate-deactivate a job type.

    A rename cascades to `work_orders.brenk_category` (a name string), so
    existing categorizations and profit history follow the new name. The
    catch-all can't be deactivated.
    """
    update_data = payload.model_dump(exclude_unset=True)
    jt = await _fetch(db, job_type_id)

    if "name" in update_data and update_data["name"] is not None:
        new_name = update_data["name"].strip()
        if await _name_conflict(db, new_name, exclude_id=jt.id):
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail=f"job type '{new_name}' already exists",
            )
        if new_name != jt.name:
            # Cascade the rename onto existing work orders' category strings.
            await db.execute(
                update(WorkOrder)
                .where(WorkOrder.brenk_category == jt.name)
                .values(brenk_category=new_name)
            )
            jt.name = new_name

    if "description" in update_data:
        desc = update_data["description"]
        jt.description = (desc or "").strip() or None if desc is not None else None

    if "is_active" in update_data and update_data["is_active"] is not None:
        if jt.is_catchall and not update_data["is_active"]:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="the catch-all job type can't be deactivated",
            )
        jt.is_active = update_data["is_active"]

    await db.commit()
    await db.refresh(jt)
    return JobTypeRef.model_validate(jt)


@router.delete("/{job_type_id}", response_model=JobTypeRef)
async def deactivate_job_type(
    job_type_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> JobTypeRef:
    """Soft-retire a job type (hidden from pickers + the categorizer; history
    kept). Hard delete is intentionally unsupported so categorized WOs and
    vendor skills never dangle."""
    jt = await _fetch(db, job_type_id)
    if jt.is_catchall:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="the catch-all job type can't be retired",
        )
    jt.is_active = False
    await db.commit()
    await db.refresh(jt)
    return JobTypeRef.model_validate(jt)
