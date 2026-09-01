import time
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
    2. Distributed Redis-backed Rate Limiting (60 requests per minute per client IP).
    """

    async def dispatch(self, request: Request, call_next):
        # 1. Skip preflight CORS requests and API documentation / health endpoints
        if request.method == "OPTIONS" or request.url.path in ["/health", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)

        # 2. Request ID Distributed Tracing
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # 3. Distributed Redis Rate Limiting (60 req / 60s)
        client_ip = request.client.host if request.client else "unknown"
        rate_limit_key = f"ratelimit:{client_ip}"

        try:
            current_count = await redis_client.get(rate_limit_key)

            if current_count is not None and int(current_count) >= 60:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Rate limit exceeded. Maximum 60 requests per minute permitted.",
                        "request_id": request_id,
                    },
                )

            pipe = redis_client.pipeline()
            pipe.incr(rate_limit_key)
            if current_count is None:
                pipe.expire(rate_limit_key, 60)
            await pipe.execute()
        except Exception:
            # Fallback gracefully if Redis connection drops or during isolated unit test runs
            pass

        # 4. Process request & attach distributed tracing header
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response