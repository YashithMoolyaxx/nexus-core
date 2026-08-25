from datetime import datetime
import uuid
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models.user import UserRole


# Shared properties across schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str | None = None
    role: UserRole = UserRole.DEVELOPER


# Request schema when creating a new user
class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)


# Request schema for user login
class UserLogin(BaseModel):
    username_or_email: str
    password: str


# Response schema (Never include hashed_password here!)
class UserResponse(UserBase):
    id: uuid.UUID
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    # ConfigDict enables reading attributes directly from SQLAlchemy ORM models
    model_config = ConfigDict(from_attributes=True)