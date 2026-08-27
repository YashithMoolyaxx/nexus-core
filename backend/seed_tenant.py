import asyncio
import uuid
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.tenant import Tenant
from app.models.user import User


async def seed():
    async with AsyncSessionLocal() as session:
        # 1. Create or get default tenant
        query = select(Tenant).where(Tenant.slug == "core-engineering")
        result = await session.execute(query)
        tenant = result.scalars().first()

        if not tenant:
            tenant = Tenant(
                name="Core Engineering",
                slug="core-engineering",
            )
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)
            print(f"Created Tenant: {tenant.name} (ID: {tenant.id})")
        else:
            print(f"Tenant already exists: {tenant.name} (ID: {tenant.id})")

        # 2. Attach all existing users to this tenant
        user_query = select(User)
        user_res = await session.execute(user_query)
        users = user_res.scalars().all()

        for user in users:
            if not user.tenant_id:
                user.tenant_id = tenant.id
                print(f"Assigned User '{user.username}' to Tenant '{tenant.name}'")

        await session.commit()
        print("Tenant seeding complete.")


if __name__ == "__main__":
    asyncio.run(seed())