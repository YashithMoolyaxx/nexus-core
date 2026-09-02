from typing import Annotated, List
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.api.deps import get_current_user, get_db, require_viewer
from app.core.ws_manager import ws_manager
from app.models.comment import DocumentComment
from app.models.document import WorkspaceDocument
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentResponse

router = APIRouter()


@router.get(
    "/{document_id}/comments",
    response_model=List[CommentResponse],
    summary="List document comments (Enforced by PostgreSQL RLS)",
)
async def list_document_comments(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_viewer)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    # 1. Verify target document belongs to the active tenant
    doc_query = select(WorkspaceDocument).where(
        WorkspaceDocument.id == document_id,
        WorkspaceDocument.tenant_id == current_user.tenant_id,
    )
    doc_result = await db.execute(doc_query)
    document = doc_result.scalars().first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found within active workspace.",
        )

    # 2. Query comments with author details preloaded
    comments_query = (
        select(DocumentComment)
        .options(selectinload(DocumentComment.author))
        .where(
            DocumentComment.document_id == document_id,
            DocumentComment.tenant_id == current_user.tenant_id,
        )
        .order_by(DocumentComment.created_at.asc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(comments_query)
    return result.scalars().all()


@router.post(
    "/{document_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Post comment on a document and broadcast in real-time",
)
async def create_document_comment(
    document_id: uuid.UUID,
    comment_in: CommentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_viewer)],
):
    # 1. Verify target document belongs to the active tenant
    doc_query = select(WorkspaceDocument).where(
        WorkspaceDocument.id == document_id,
        WorkspaceDocument.tenant_id == current_user.tenant_id,
    )
    doc_result = await db.execute(doc_query)
    document = doc_result.scalars().first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found within active workspace.",
        )

    # 2. Persist new comment bound to current tenant and author
    comment = DocumentComment(
        content=comment_in.content,
        document_id=document_id,
        tenant_id=current_user.tenant_id,
        author_id=current_user.id,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment, attribute_names=["author"])

    # 3. Broadcast real-time event through Redis Pub/Sub mesh
    await ws_manager.publish_event(
        tenant_id=str(current_user.tenant_id),
        event_type="NEW_COMMENT",
        data={
            "comment_id": str(comment.id),
            "document_id": str(document_id),
            "content": comment.content,
            "created_at": comment.created_at.isoformat(),
            "author": {
                "id": str(current_user.id),
                "username": current_user.username,
                "role": current_user.role.value,
            },
        },
    )

    return comment