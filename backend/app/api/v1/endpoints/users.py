from typing import Annotated, Any, Sequence
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import RoleChecker, get_current_user
from app.core.database import get_db
from app.core.redis import CacheService
from app.models.user import User, UserRole
from app.schemas.user import UserResponse

router = APIRouter()


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile (Cached)",
)
async def read_current_user_profile(
    current_user: Annotated[User, Depends(get_current_user)],
) -> Any:
    """
    Returns user profile with Cache-Aside pattern applied.
    Subsequent requests hit in-memory Redis instead of the DB.
    """
    cache_key = f"user:profile:{current_user.id}"

    # 1. Check Redis Cache
    cached_profile = await CacheService.get(cache_key)
    if cached_profile:
        return cached_profile

    # 2. Cache Miss: Serialize user data and store in Redis for 5 minutes (300s)
    user_data = UserResponse.model_validate(current_user).model_dump(mode="json")
    await CacheService.set(cache_key, user_data, expire_seconds=300)

    return user_data


@router.get(
    "/",
    response_model=list[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="List all users (Admin only)",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def list_all_users(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Sequence[User]:
    """
    Fetches all registered users.
    Restricted strictly to users with the 'admin' role.
    """
    query = select(User).order_by(User.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()