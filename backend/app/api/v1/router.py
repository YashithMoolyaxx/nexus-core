from fastapi import APIRouter
from app.api.v1.endpoints import auth, documents, projects, tasks, users, ws

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(documents.router, prefix="/documents", tags=["Workspace Documents (RLS + OCC)"])
api_router.include_router(ws.router, prefix="/ws", tags=["Real-Time WebSockets"])
api_router.include_router(projects.router, prefix="/projects", tags=["Projects Domain"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Background Tasks"])