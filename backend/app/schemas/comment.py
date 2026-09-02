import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class CommentCreate(BaseModel):
    content: str


class CommentAuthor(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class CommentResponse(BaseModel):
    id: uuid.UUID
    content: str
    document_id: uuid.UUID
    tenant_id: uuid.UUID
    author_id: uuid.UUID
    created_at: datetime
    author: CommentAuthor

    model_config = ConfigDict(from_attributes=True)