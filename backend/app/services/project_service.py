import math
import uuid
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.project import Project, ProjectStatus
from app.models.user import User, UserRole
from app.schemas.project import (
    PaginatedResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)


class ProjectService:

    @staticmethod
    async def create_project(
        db: AsyncSession, project_in: ProjectCreate, current_user: User
    ) -> Project:
        """Creates a new project owned by the current authenticated user."""
        project = Project(
            title=project_in.title,
            description=project_in.description,
            status=project_in.status,
            owner_id=current_user.id,
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)
        return project

    @staticmethod
    async def get_paginated_projects(
        db: AsyncSession,
        current_user: User,
        page: int = 1,
        size: int = 10,
        status_filter: ProjectStatus | None = None,
    ) -> PaginatedResponse[ProjectResponse]:
        """Fetches projects with pagination and role-based filtering."""
        offset = (page - 1) * size

        # Base query: Admins see all, developers see only their own projects
        query = select(Project)
        count_query = select(func.count(Project.id))

        if current_user.role != UserRole.ADMIN:
            query = query.where(Project.owner_id == current_user.id)
            count_query = count_query.where(Project.owner_id == current_user.id)

        if status_filter:
            query = query.where(Project.status == status_filter)
            count_query = count_query.where(Project.status == status_filter)

        total_count = (await db.execute(count_query)).scalar_one()

        query = query.order_by(Project.created_at.desc()).offset(offset).limit(size)
        result = await db.execute(query)
        projects = result.scalars().all()

        total_pages = math.ceil(total_count / size) if total_count > 0 else 1

        return PaginatedResponse(
            items=[ProjectResponse.model_validate(p) for p in projects],
            total=total_count,
            page=page,
            size=size,
            pages=total_pages,
        )

    @staticmethod
    async def get_project_by_id(
        db: AsyncSession, project_id: uuid.UUID, current_user: User
    ) -> Project:
        """Fetches a single project verifying ownership or admin privileges."""
        query = select(Project).where(Project.id == project_id)
        result = await db.execute(query)
        project = result.scalars().first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found.",
            )

        if current_user.role != UserRole.ADMIN and project.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this project.",
            )

        return project

    @staticmethod
    async def update_project(
        db: AsyncSession,
        project_id: uuid.UUID,
        project_in: ProjectUpdate,
        current_user: User,
    ) -> Project:
        """Updates a project resource."""
        project = await ProjectService.get_project_by_id(db, project_id, current_user)

        update_data = project_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(project, field, value)

        await db.commit()
        await db.refresh(project)
        return project

    @staticmethod
    async def delete_project(
        db: AsyncSession, project_id: uuid.UUID, current_user: User
    ) -> None:
        """Deletes a project."""
        project = await ProjectService.get_project_by_id(db, project_id, current_user)
        await db.delete(project)
        await db.commit()