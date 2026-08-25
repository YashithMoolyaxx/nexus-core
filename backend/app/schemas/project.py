from datetime import datetime
from typing import Generic, TypeVar
import uuid
from pydantic import BaseModel, ConfigDict, Field
from app.models.project import ProjectStatus

T = TypeVar("T")


class ProjectBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=100)
    description: str | None = Field(None, max_length=1000)
    status: ProjectStatus = ProjectStatus.ACTIVE


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=100)
    description: str | None = Field(None, max_length=1000)
    status: ProjectStatus | None = None


class ProjectResponse(ProjectBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Generic Paginated Response Envelope
class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int