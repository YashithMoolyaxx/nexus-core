from typing import Annotated, Any
from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.api.deps import get_current_user
from app.models.user import User
from app.workers.celery_app import celery_app
from app.workers.tasks import process_data_analytics, send_welcome_notification

router = APIRouter()


class AnalyticsTaskRequest(BaseModel):
    record_count: int = Field(..., ge=1, le=100000)


class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


@router.post(
    "/send-welcome",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue async welcome notification",
)
async def trigger_welcome_email(
    current_user: Annotated[User, Depends(get_current_user)],
) -> Any:
    """
    Enqueues an asynchronous welcome notification to the Celery queue.
    Returns HTTP 202 Accepted immediately.
    """
 
    task = send_welcome_notification.delay(
        email=current_user.email,
        username=current_user.username,
    )
    return {
        "task_id": task.id,
        "status": "ENQUEUED",
        "message": "Welcome notification dispatched to background queue.",
    }


@router.post(
    "/run-analytics",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue heavy analytics calculation",
)
async def trigger_analytics_job(
    payload: AnalyticsTaskRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> Any:
    """
    Offloads data aggregation processing to a Celery worker.
    """
    task = process_data_analytics.delay(record_count=payload.record_count)
    return {
        "task_id": task.id,
        "status": "ENQUEUED",
        "message": "Analytics job enqueued for asynchronous processing.",
    }


@router.get(
    "/status/{task_id}",
    summary="Query background task execution status",
)
async def get_task_status(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """
    Fetches real-time task status and computed results from Celery Result Backend.
    """
    task_result = AsyncResult(task_id, app=celery_app)
    
    response = {
        "task_id": task_id,
        "status": task_result.status,
    }

    if task_result.successful():
        response["result"] = task_result.result
    elif task_result.failed():
        response["error"] = str(task_result.result)

    return response