"""Pydantic schemas for the job-types taxonomy API."""

from pydantic import BaseModel, ConfigDict, Field


class JobTypeRef(BaseModel):
    """Read shape for a job type."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    position: int
    is_active: bool
    is_catchall: bool


class JobTypeCreate(BaseModel):
    """POST body — name required, description optional."""

    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class JobTypeUpdate(BaseModel):
    """PATCH body — only fields present are touched."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
