from typing import Annotated, List
import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User, UserRole
from app.schemas.token import TokenPayload

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        token_data = TokenPayload(sub=user_id_str)
    except JWTError:
        raise credentials_exception

    try:
        user_uuid = uuid.UUID(token_data.sub)
    except ValueError:
        raise credentials_exception

    query = select(User).where(User.id == user_uuid)
    result = await db.execute(query)
    user = result.scalars().first()

    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    return user


class RoleChecker:
    """
    Enforces Role-Based Access Control (RBAC) at the route level.
    """
    def __init__(self, allowed_roles: List[UserRole]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"RBAC Permission Denied: Operation requires one of {[r.value for r in self.allowed_roles]} roles. Your current role is '{current_user.role.value}'.",
            )
        return current_user


# Predefined RBAC role dependencies
require_admin = RoleChecker([UserRole.ADMIN])
require_developer = RoleChecker([UserRole.ADMIN, UserRole.DEVELOPER])
require_viewer = RoleChecker([UserRole.ADMIN, UserRole.DEVELOPER, UserRole.VIEWER])