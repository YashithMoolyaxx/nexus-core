from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from celery.result import AsyncResult
from app.api.deps import get_current_user, require_admin
from app.core.celery_app import celery_app
from app.models.user import User
from app.tasks.analytics import process_dataset_analytics

router = APIRouter()


class TaskTriggerRequest(BaseModel):
    record_count: int = Field(15000, ge=1000, le=100000, description="Volume of records to process")


class TaskTriggerResponse(BaseModel):
    task_id: str
    status: str
    message: str


@router.post(
    "/run-analytics",
    response_model=TaskTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue Heavy Statistical Analytics Task (Requires Admin role)",
)
async def run_analytics(
    payload: TaskTriggerRequest,
    current_user: User = Depends(require_admin),
):
    task = process_dataset_analytics.delay(record_count=payload.record_count)
    return {
        "task_id": task.id,
        "status": "QUEUED",
        "message": f"Dispatched async batch analytics for {payload.record_count:,} records.",
    }


@router.get(
    "/status/{task_id}",
    summary="Poll Background Task Execution State",
)
async def get_task_status(task_id: str):
    task_result = AsyncResult(task_id, app=celery_app)
    response = {
        "task_id": task_id,
        "status": task_result.status,
    }
    if task_result.status == "SUCCESS":
        response["result"] = task_result.result
    elif task_result.status == "FAILURE":
        response["error"] = str(task_result.result)
    return response