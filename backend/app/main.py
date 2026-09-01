import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.middleware import EnterpriseMiddleware
from app.core.ws_manager import ws_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Safely start Redis Pub/Sub background reader
    try:
        await ws_manager.start_redis_listener()
    except Exception as e:
        print(f"Warning: Redis Pub/Sub listener failed to initialize: {e}")
    
    yield
    
    # Graceful shutdown
    if ws_manager.listener_task and not ws_manager.listener_task.done():
        ws_manager.listener_task.cancel()
        try:
            await ws_manager.listener_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# 1. CORS Middleware (Must be added FIRST so preflight checks pass)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# 2. Custom Enterprise Middleware
app.add_middleware(EnterpriseMiddleware)

# 3. API Router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "Validation Error", "details": exc.errors()},
    )


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Database Error", "message": "Database operation failed."},
    )


@app.get("/health", tags=["System Health"])
async def health_check():
    return {"status": "healthy", "service": "nexus-backend", "version": "1.0.0"}