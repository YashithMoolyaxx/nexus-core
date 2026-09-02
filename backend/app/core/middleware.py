import uuid
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as aioredis
from app.core.config import settings

redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)


class EnterpriseMiddleware(BaseHTTPMiddleware):
    """
    Enterprise Middleware providing:
    1. Unique X-Request-ID distributed tracing injection.
    2. Distributed Redis-backed Rate Limiting.
    3. Complete bypass for WebSocket ASGI upgrades and public probes.
    """

    async def dispatch(self, request: Request, call_next):
        # 1. Immediately bypass WebSockets, CORS preflights, health probes, and auth routes
        if request.scope.get("type") == "websocket" or "/ws" in request.url.path:
            return await call_next(request)

        exempt_paths = [
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
        ]
        if request.method == "OPTIONS" or any(request.url.path.startswith(p) for p in exempt_paths):
            return await call_next(request)

        # 2. Request ID Distributed Tracing
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # 3. Distributed Redis Rate Limiting (300 req / 60s ceiling)
        client_ip = request.client.host if request.client else "127.0.0.1"
        rate_limit_key = f"ratelimit:{client_ip}"

        try:
            pipe = redis_client.pipeline()
            pipe.incr(rate_limit_key)
            pipe.expire(rate_limit_key, 60)
            results = await pipe.execute()
            current_count = results[0] if results else 1

            if current_count > 300:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Rate limit exceeded. Maximum 300 requests per minute permitted.",
                        "request_id": request_id,
                    },
                )
        except Exception:
            pass

        # 4. Attach tracing headers to HTTP responses
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response