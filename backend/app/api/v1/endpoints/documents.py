from datetime import datetime, timezone
from typing import Annotated
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_tenant_session
from app.models.document import WorkspaceDocument
from app.models.user import User
from app.schemas.document import DocumentCreate, DocumentResponse, DocumentUpdate

router = APIRouter()


@router.post(
    "/",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create document under active tenant (RLS Protected)",
)
async def create_document(
    doc_in: DocumentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_tenant_session)],
):
    doc = WorkspaceDocument(
        title=doc_in.title,
        content=doc_in.content,
        tenant_id=current_user.tenant_id,
        created_by=current_user.id,
        version=1,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


@router.get(
    "/",
    response_model=list[DocumentResponse],
    summary="List all documents in tenant (PostgreSQL RLS Filtered)",
)
async def list_documents(
    db: Annotated[AsyncSession, Depends(get_tenant_session)],
):
    query = select(WorkspaceDocument).order_by(WorkspaceDocument.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Fetch single document",
)
async def get_document(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_tenant_session)],
):
    query = select(WorkspaceDocument).where(WorkspaceDocument.id == document_id)
    result = await db.execute(query)
    doc = result.scalars().first()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found within your tenant workspace.",
        )
    return doc


@router.put(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Update document with Optimistic Concurrency Control (OCC)",
)
async def update_document_occ(
    document_id: uuid.UUID,
    doc_in: DocumentUpdate,
    db: Annotated[AsyncSession, Depends(get_tenant_session)],
):
    """
    Atomic OCC Mutation:
    Increments version counter ONLY if current version matches expected version.
    Returns 409 Conflict if a concurrent write modified the state first.
    """
    values_to_update = {
        "version": WorkspaceDocument.version + 1,
        "updated_at": datetime.now(timezone.utc),
    }
    if doc_in.title is not None:
        values_to_update["title"] = doc_in.title
    if doc_in.content is not None:
        values_to_update["content"] = doc_in.content

    # Atomic conditional update
    stmt = (
        update(WorkspaceDocument)
        .where(
            WorkspaceDocument.id == document_id,
            WorkspaceDocument.version == doc_in.version,  # OCC guard
        )
        .values(**values_to_update)
        .returning(WorkspaceDocument)
    )

    result = await db.execute(stmt)
    updated_doc = result.scalars().first()

    if not updated_doc:
        # Fetch current record to verify whether it was deleted or had a version conflict
        check_query = select(WorkspaceDocument).where(WorkspaceDocument.id == document_id)
        check_res = await db.execute(check_query)
        existing_doc = check_res.scalars().first()

        if not existing_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document does not exist or has been deleted.",
            )
        
        # Concurrency race collision detected!
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "State Conflict: Document was modified by another operator.",
                "current_version": existing_doc.version,
                "attempted_version": doc_in.version,
            },
        )

    await db.commit()
    return updated_doc