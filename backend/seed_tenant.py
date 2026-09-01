import asyncio
import uuid
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.tenant import Tenant
from app.models.document import WorkspaceDocument
from app.models.user import User, UserRole


async def seed():
    async with AsyncSessionLocal() as session:
        # 1. Seed Enterprise Tenants
        tenants_data = [
            {"name": "Core Engineering", "slug": "core-engineering"},
            {"name": "FinTech Labs", "slug": "fintech-labs"},
            {"name": "Cyberdyne Systems", "slug": "cyberdyne-systems"},
        ]

        created_tenants = {}
        for t_data in tenants_data:
            query = select(Tenant).where(Tenant.slug == t_data["slug"])
            res = await session.execute(query)
            tenant = res.scalars().first()
            if not tenant:
                tenant = Tenant(name=t_data["name"], slug=t_data["slug"])
                session.add(tenant)
                await session.flush()
                print(f"Created Tenant: {tenant.name} ({tenant.id})")
            created_tenants[tenant.slug] = tenant

        # 2. Seed Pre-configured RBAC Test Users
        demo_users = [
            {
                "email": "admin@nexuscore.io",
                "username": "admin_user",
                "full_name": "System Administrator",
                "password": "AdminPass123!",
                "role": UserRole.ADMIN,
                "tenant_slug": "core-engineering",
            },
            {
                "email": "dev@nexuscore.io",
                "username": "dev_user",
                "full_name": "Senior Software Engineer",
                "password": "DevPass123!",
                "role": UserRole.DEVELOPER,
                "tenant_slug": "core-engineering",
            },
            {
                "email": "viewer@nexuscore.io",
                "username": "viewer_user",
                "full_name": "Audit Observer",
                "password": "ViewerPass123!",
                "role": UserRole.VIEWER,
                "tenant_slug": "core-engineering",
            },
        ]

        for u_data in demo_users:
            user_query = select(User).where(User.email == u_data["email"])
            existing_user = (await session.execute(user_query)).scalars().first()
            if not existing_user:
                t = created_tenants[u_data["tenant_slug"]]
                new_user = User(
                    email=u_data["email"],
                    username=u_data["username"],
                    full_name=u_data["full_name"],
                    hashed_password=get_password_hash(u_data["password"]),
                    role=u_data["role"],
                    tenant_id=t.id,
                )
                session.add(new_user)
                print(f"Created Demo User: {u_data['username']} with Role: {u_data['role'].value.upper()}")

        # 3. Seed Sample Documents
        sample_docs = [
            {
                "title": "Kernel Memory Management Architecture",
                "content": "# Core Engineering Spec\n\nAll threads execute under strict memory bounds.",
                "tenant_slug": "core-engineering",
            },
            {
                "title": "PCI-DSS Payment Ledger Ingestion",
                "content": "# FinTech Compliance\n\nTokenized transaction stream protocols.",
                "tenant_slug": "fintech-labs",
            },
            {
                "title": "Autonomous Neural Network Orchestrator",
                "content": "# Cyberdyne Robotics\n\nDistributed drone telemetry cluster.",
                "tenant_slug": "cyberdyne-systems",
            },
        ]

        for doc_item in sample_docs:
            t = created_tenants[doc_item["tenant_slug"]]
            doc_query = select(WorkspaceDocument).where(
                WorkspaceDocument.title == doc_item["title"],
                WorkspaceDocument.tenant_id == t.id,
            )
            existing = (await session.execute(doc_query)).scalars().first()
            if not existing:
                doc = WorkspaceDocument(
                    title=doc_item["title"],
                    content=doc_item["content"],
                    tenant_id=t.id,
                    version=1,
                )
                session.add(doc)

        await session.commit()
        print("Database seeding completed successfully.")


if __name__ == "__main__":
    asyncio.run(seed())