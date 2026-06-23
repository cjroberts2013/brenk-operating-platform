"""Job-category taxonomy endpoint.

Serves the curated category list (app/services/categories.py) so the
frontend category dropdown stays in sync without duplicating it.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.categories import JOB_CATEGORIES

router = APIRouter()


class CategoryListResponse(BaseModel):
    categories: list[str]


@router.get("/", response_model=CategoryListResponse)
async def list_categories() -> CategoryListResponse:
    """The curated Brenk job categories, in display order."""
    return CategoryListResponse(categories=JOB_CATEGORIES)
