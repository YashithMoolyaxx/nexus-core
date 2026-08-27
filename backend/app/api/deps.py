from typing import Annotated, AsyncGenerator
import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db
from app.models.user import User, UserRole
from app.schemas.token import TokenPayload

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or token expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
        if token_data.type != "access" or token_data.sub is None:
            raise credentials_exception
    except (JWTError, Exception):
        raise credentials_exception

    query = select(User).where(User.id == uuid.UUID(token_data.sub))
    result = await db.execute(query)
    user = result.scalars().first()

    if user is None or not user.is_active:
        raise credentials_exception
    return user


class RoleChecker:
    def __init__(self, allowed_roles: list[UserRole]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have required permissions to perform this action.",
            )
        return user


async def get_tenant_session(
    current_user: Annotated[User, Depends(get_current_user)],
) -> AsyncGenerator[AsyncSession, None]:
    """
    Yields an AsyncSession with PostgreSQL RLS tenant context pre-configured.
    Guarantees kernel-level data isolation.
    """
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not assigned to a tenant organization.",
        )

    session = AsyncSessionLocal()
    try:
        # Inject tenant_id into the PostgreSQL transaction state for RLS
        await session.execute(
            text(f"SET LOCAL app.current_tenant_id = '{str(current_user.tenant_id)}';")
        )
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()