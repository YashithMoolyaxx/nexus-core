from typing import Annotated, List
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_db, require_developer, require_viewer
from app.core.ws_manager import ws_manager
from app.models.document import WorkspaceDocument
from app.models.user import User
from app.schemas.document import (
    DocumentCreate,
    DocumentResponse,
    DocumentUpdate,
)

router = APIRouter()


@router.get(
    "/",
    response_model=List[DocumentResponse],
    summary="List tenant documents (Enforced by PostgreSQL RLS)",
)
async def list_documents(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_viewer)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    query = (
        select(WorkspaceDocument)
        .where(WorkspaceDocument.tenant_id == current_user.tenant_id)
        .offset(skip)
        .limit(limit)
        .order_by(WorkspaceDocument.updated_at.desc())
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.post(
    "/",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create document (Requires Developer or Admin role)",
)
async def create_document(
    doc_in: DocumentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_developer)],
):
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not belong to any tenant workspace.",
        )

    document = WorkspaceDocument(
        title=doc_in.title,
        content=doc_in.content,
        tenant_id=current_user.tenant_id,
        created_by=current_user.id,
        version=1,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    await ws_manager.publish_event(
        tenant_id=str(current_user.tenant_id),
        event_type="DOCUMENT_CREATED",
        data={
            "id": str(document.id),
            "title": document.title,
            "content": document.content,
            "version": document.version,
            "tenant_id": str(document.tenant_id),
            "created_by": str(document.created_by) if document.created_by else None,
        },
    )

    return document


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Fetch single document",
)
async def get_document(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_viewer)],
):
    query = select(WorkspaceDocument).where(
        WorkspaceDocument.id == document_id,
        WorkspaceDocument.tenant_id == current_user.tenant_id,
    )
    result = await db.execute(query)
    doc = result.scalars().first()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found within active tenant workspace.",
        )
    return doc


@router.put(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Atomic OCC Update (Requires Developer or Admin role)",
)
async def update_document(
    document_id: uuid.UUID,
    doc_in: DocumentUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_developer)],
):
    query = select(WorkspaceDocument).where(
        WorkspaceDocument.id == document_id,
        WorkspaceDocument.tenant_id == current_user.tenant_id,
    )
    result = await db.execute(query)
    doc = result.scalars().first()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found within active tenant workspace.",
        )

    if doc.version != doc_in.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Optimistic Concurrency Conflict: Document was modified by another operator.",
                "current_version": doc.version,
                "submitted_version": doc_in.version,
            },
        )

    doc.title = doc_in.title
    doc.content = doc_in.content
    doc.version += 1

    await db.commit()
    await db.refresh(doc)

    await ws_manager.publish_event(
        tenant_id=str(current_user.tenant_id),
        event_type="DOCUMENT_UPDATED",
        data={
            "id": str(doc.id),
            "title": doc.title,
            "content": doc.content,
            "version": doc.version,
            "tenant_id": str(doc.tenant_id),
            "created_by": str(doc.created_by) if doc.created_by else None,
        },
    )

    return doc