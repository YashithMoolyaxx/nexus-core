import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import get_db, Base
from app.core.security import get_password_hash, create_access_token
from app.core.ws_manager import ws_manager
from app.main import app
from app.models.tenant import Tenant
from app.models.user import User, UserRole

TEST_DATABASE_URL = settings.DATABASE_URL

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    future=True,
    poolclass=NullPool,
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture(autouse=True)
def isolate_async_redis():
    mock_pipe = AsyncMock()
    mock_pipe.incr.return_value = mock_pipe
    mock_pipe.expire.return_value = mock_pipe
    mock_pipe.execute = AsyncMock(return_value=[1, True])

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.incr = AsyncMock(return_value=1)
    mock_redis.expire = AsyncMock(return_value=True)
    mock_redis.pipeline = MagicMock(return_value=mock_pipe)
    mock_redis.publish = AsyncMock(return_value=1)

    with patch("app.core.middleware.redis_client", mock_redis), \
         patch("app.core.presence.redis_presence", mock_redis), \
         patch.object(ws_manager, "publish_event", new_callable=AsyncMock), \
         patch.object(ws_manager, "broadcast_to_tenant", new_callable=AsyncMock):
        yield


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncClient:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_tenants(db_session: AsyncSession):
    suffix = uuid.uuid4().hex[:8]
    tenant_a = Tenant(
        id=uuid.uuid4(),
        name=f"Alpha Dynamics {suffix}",
        slug=f"alpha-dynamics-{suffix}",
    )
    tenant_b = Tenant(
        id=uuid.uuid4(),
        name=f"Beta Robotics {suffix}",
        slug=f"beta-robotics-{suffix}",
    )
    db_session.add_all([tenant_a, tenant_b])
    await db_session.commit()
    await db_session.refresh(tenant_a)
    await db_session.refresh(tenant_b)
    return {"tenant_a": tenant_a, "tenant_b": tenant_b}


@pytest_asyncio.fixture
async def test_users(db_session: AsyncSession, test_tenants):
    tenant_a = test_tenants["tenant_a"]
    tenant_b = test_tenants["tenant_b"]
    suffix = uuid.uuid4().hex[:8]

    admin_user = User(
        id=uuid.uuid4(),
        email=f"admin_{suffix}@alpha.io",
        username=f"admin_{suffix}",
        hashed_password=get_password_hash("Password123!"),
        role=UserRole.ADMIN,
        tenant_id=tenant_a.id,
        is_active=True,
    )

    dev_user = User(
        id=uuid.uuid4(),
        email=f"dev_{suffix}@alpha.io",
        username=f"dev_{suffix}",
        hashed_password=get_password_hash("Password123!"),
        role=UserRole.DEVELOPER,
        tenant_id=tenant_a.id,
        is_active=True,
    )

    viewer_user = User(
        id=uuid.uuid4(),
        email=f"viewer_{suffix}@alpha.io",
        username=f"viewer_{suffix}",
        hashed_password=get_password_hash("Password123!"),
        role=UserRole.VIEWER,
        tenant_id=tenant_a.id,
        is_active=True,
    )

    tenant_b_user = User(
        id=uuid.uuid4(),
        email=f"dev_{suffix}@beta.io",
        username=f"beta_dev_{suffix}",
        hashed_password=get_password_hash("Password123!"),
        role=UserRole.DEVELOPER,
        tenant_id=tenant_b.id,
        is_active=True,
    )

    db_session.add_all([admin_user, dev_user, viewer_user, tenant_b_user])
    await db_session.commit()
    await db_session.refresh(admin_user)
    await db_session.refresh(dev_user)
    await db_session.refresh(viewer_user)
    await db_session.refresh(tenant_b_user)

    return {
        "admin": admin_user,
        "developer": dev_user,
        "viewer": viewer_user,
        "beta_developer": tenant_b_user,
    }


@pytest.fixture
def auth_headers(test_users):
    tokens = {}
    for role_name, user_obj in test_users.items():
        token = create_access_token(
            subject=user_obj.id,
            role=user_obj.role.value,
        )
        tokens[role_name] = {"Authorization": f"Bearer {token}"}
    return tokens