import json
from typing import Any
import redis.asyncio as aioredis
from app.core.config import settings

# Initialize asynchronous Redis connection pool
redis_client = aioredis.from_url(
    settings.REDIS_URL,
    decode_responses=True,  # Automatically decode byte responses to UTF-8 strings
)


class CacheService:
    """Helper service implementing Redis get, set, and invalidation."""

    @staticmethod
    async def get(key: str) -> Any | None:
        """Retrieves and deserializes JSON from Redis."""
        data = await redis_client.get(key)
        if data:
            return json.loads(data)
        return None

    @staticmethod
    async def set(key: str, value: Any, expire_seconds: int = 300) -> None:
        """Serializes and caches data in Redis with a TTL (default 5 minutes)."""
        serialized_data = json.dumps(value, default=str)
        await redis_client.set(key, serialized_data, ex=expire_seconds)

    @staticmethod
    async def delete(key: str) -> None:
        """Deletes a key from Redis (Cache Invalidation)."""
        await redis_client.delete(key)