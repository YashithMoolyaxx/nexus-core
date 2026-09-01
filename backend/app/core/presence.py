import json
import redis.asyncio as aioredis
from app.core.config import settings

redis_presence = aioredis.from_url(settings.REDIS_URL, decode_responses=True)


class PresenceService:
    """Manages active user heartbeats with zero database load using Redis TTLs."""

    @staticmethod
    async def heartbeat(tenant_id: str, user_id: str, username: str) -> None:
        """Sets an ephemeral heartbeat key that expires automatically in 15 seconds."""
        key = f"presence:{tenant_id}:{user_id}"
        payload = json.dumps({"user_id": user_id, "username": username})
        await redis_presence.set(key, payload, ex=15)

    @staticmethod
    async def remove(tenant_id: str, user_id: str) -> None:
        """Explicitly purges user presence on clean disconnect."""
        key = f"presence:{tenant_id}:{user_id}"
        await redis_presence.delete(key)

    @staticmethod
    async def get_active_users(tenant_id: str) -> list[dict]:
        """Scans and retrieves all active operators within the given tenant workspace."""
        pattern = f"presence:{tenant_id}:*"
        keys = []
        async for k in redis_presence.scan_iter(match=pattern):
            keys.append(k)

        if not keys:
            return []

        values = await redis_presence.mget(keys)
        active_users = [json.loads(v) for v in values if v is not None]
        return active_users