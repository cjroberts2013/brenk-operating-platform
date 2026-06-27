"""Job-category taxonomy endpoint.

Serves the active job-type names (the shared taxonomy in the `job_types`
table) so the frontend category dropdown stays in sync with what the
categorizer and vendor skills use.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.services.job_types import list_job_type_names

router = APIRouter()


class CategoryListResponse(BaseModel):
    categories: list[str]


@router.get("/", response_model=CategoryListResponse)
async def list_categories(
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> CategoryListResponse:
    """The active Brenk job types, in display order."""
    return CategoryListResponse(categories=await list_job_type_names(db))
