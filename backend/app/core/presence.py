import redis.asyncio as aioredis
from app.core.config import settings

redis_presence = aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def register_presence(tenant_id: str, user_id: str, username: str):
    """Registers ephemeral user presence with a 30-second sliding TTL."""
    key = f"presence:{tenant_id}:{user_id}"
    await redis_presence.setex(key, 30, username)


async def refresh_presence(tenant_id: str, user_id: str, username: str):
    """Refreshes presence key TTL on WebSocket heartbeat."""
    key = f"presence:{tenant_id}:{user_id}"
    await redis_presence.setex(key, 30, username)


async def unregister_presence(tenant_id: str, user_id: str):
    """Purges ephemeral presence key upon socket disconnection."""
    key = f"presence:{tenant_id}:{user_id}"
    await redis_presence.delete(key)


async def get_active_tenant_operators(tenant_id: str):
    """Retrieves all active ephemeral operators currently online in this tenant."""
    pattern = f"presence:{tenant_id}:*"
    keys = await redis_presence.keys(pattern)
    operators = []
    for k in keys:
        user_id = k.split(":")[-1]
        username = await redis_presence.get(k)
        if username:
            operators.append({"user_id": user_id, "username": username})
    return operators