from datetime import timedelta
from typing import Annotated
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserLogin, UserResponse

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register account with assigned RBAC role and bind to default tenant",
)
async def register(
    user_in: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Verify unique username and email
    query = select(User).where(
        or_(
            User.email == user_in.email.strip().lower(),
            User.username == user_in.username.strip(),
        )
    )
    result = await db.execute(query)
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this username or email already exists.",
        )

    # Ensure default workspace tenant exists
    tenant_res = await db.execute(
        select(Tenant).where(Tenant.slug == "core-engineering")
    )
    tenant = tenant_res.scalars().first()
    if not tenant:
        tenant = Tenant(name="Core Engineering", slug="core-engineering")
        db.add(tenant)
        await db.flush()

    # Create user with strictly bound RBAC role
    db_user = User(
        email=user_in.email.strip().lower(),
        username=user_in.username.strip(),
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role,
        tenant_id=tenant.id,
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


@router.post(
    "/login",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="User login with JWT generation containing signed RBAC role claim",
)
async def login(
    login_data: UserLogin,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    identifier = login_data.username_or_email.strip()
    query = select(User).where(
        or_(
            User.username == identifier,
            User.email == identifier.lower(),
        )
    )
    result = await db.execute(query)
    user = result.scalars().first()

    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account has been deactivated.",
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id,
        role=user.role.value,
        expires_delta=access_token_expires,
    )
    refresh_token = create_refresh_token(subject=user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.get("/tenants", summary="List available workspace organizations")
async def list_tenants(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(Tenant).order_by(Tenant.name.asc()))
    return result.scalars().all()


@router.post("/switch-tenant/{tenant_id}", summary="Switch user tenant scope (Demonstrates RLS)")
async def switch_tenant(
    tenant_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    tenant_uuid = uuid.UUID(tenant_id)
    tenant_check = await db.execute(select(Tenant).where(Tenant.id == tenant_uuid))
    tenant = tenant_check.scalars().first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant organization not found.")

    current_user.tenant_id = tenant_uuid
    await db.commit()
    await db.refresh(current_user)
    return {"message": f"Switched context to {tenant.name}", "tenant_id": str(tenant.id)}