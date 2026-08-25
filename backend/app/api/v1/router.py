from fastapi import APIRouter
from app.api.v1.endpoints import auth, projects, tasks, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(projects.router, prefix="/projects", tags=["Projects Domain"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Background Tasks"])