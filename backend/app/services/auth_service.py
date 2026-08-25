from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserLogin


class AuthService:

    @staticmethod
    async def register_user(db: AsyncSession, user_in: UserCreate) -> User:
        """Validates duplicate users and persists a new user to the database."""
        # 1. Check if user with same email or username already exists
        query = select(User).where(
            or_(User.email == user_in.email, User.username == user_in.username)
        )
        result = await db.execute(query)
        existing_user = result.scalars().first()

        if existing_user:
            if existing_user.email == user_in.email:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A user with this email address already exists.",
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This username is already taken.",
            )

        # 2. Hash the raw password and create user instance
        new_user = User(
            email=user_in.email,
            username=user_in.username,
            full_name=user_in.full_name,
            role=user_in.role,
            hashed_password=hash_password(user_in.password),
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user

    @staticmethod
    async def authenticate_user(db: AsyncSession, credentials: UserLogin) -> Token:
        """Verifies credentials and returns access & refresh tokens."""
        # Query by email or username
        query = select(User).where(
            or_(
                User.email == credentials.username_or_email,
                User.username == credentials.username_or_email,
            )
        )
        result = await db.execute(query)
        user = result.scalars().first()

        if not user or not verify_password(
            credentials.password, user.hashed_password
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive or disabled.",
            )

        # Generate tokens
        access_token = create_access_token(
            subject=user.id, role=user.role.value
        )
        refresh_token = create_refresh_token(subject=user.id)

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )