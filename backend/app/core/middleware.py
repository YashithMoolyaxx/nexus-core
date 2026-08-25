import time
import uuid
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.redis import redis_client


class EnterpriseMiddleware(BaseHTTPMiddleware):
    """
    Middleware providing:
    1. Unique X-Request-ID distributed tracing injection.
    2. Distributed Redis-backed Rate Limiting (60 requests per minute per client IP).
    """

    async def dispatch(self, request: Request, call_next):
    
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))


        if "/health" not in request.url.path:
            client_ip = request.client.host if request.client else "unknown"
            rate_limit_key = f"ratelimit:{client_ip}"

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

        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response