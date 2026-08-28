import asyncio
import json
import uuid
from typing import Dict, Set
from fastapi import WebSocket
import redis.asyncio as aioredis
from app.core.config import settings


class ConnectionManager:
    """
    Distributed WebSocket connection manager.
    Coordinates local WebSocket client pools with a Redis Pub/Sub broadcast mesh.
    """

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        self.pubsub = self.redis_client.pubsub()
        self.listener_task: asyncio.Task | None = None

    async def start_redis_listener(self):
        """Spawns an async loop listening for distributed Redis broadcast events."""
        await self.pubsub.psubscribe("workspace:*")
        self.listener_task = asyncio.create_task(self._redis_event_reader())

    async def _redis_event_reader(self):
        """Reads incoming Pub/Sub messages from Redis and fans out to local WebSockets."""
        try:
            async for message in self.pubsub.listen():
                if message and message["type"] == "pmessage":
                    channel = message["channel"]  # Format: workspace:doc:<tenant_id>
                    tenant_id = channel.split(":")[-1]
                    payload = json.loads(message["data"])
                    await self._broadcast_to_local_sockets(tenant_id, payload)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Redis Pub/Sub Reader Error: {e}")

    async def connect(self, tenant_id: str, websocket: WebSocket):
        """Registers a newly authenticated WebSocket connection."""
        await websocket.accept()
        if tenant_id not in self.active_connections:
            self.active_connections[tenant_id] = set()
        self.active_connections[tenant_id].add(websocket)

    def disconnect(self, tenant_id: str, websocket: WebSocket):
        """Purges a disconnected WebSocket connection from memory."""
        if tenant_id in self.active_connections:
            self.active_connections[tenant_id].discard(websocket)
            if not self.active_connections[tenant_id]:
                del self.active_connections[tenant_id]

    async def publish_event(self, tenant_id: str, event_type: str, data: dict):
        """
        Publishes an event to the distributed Redis channel.
        Reaches all FastAPI replicas.
        """
        channel = f"workspace:doc:{tenant_id}"
        message = {
            "event": event_type,
            "tenant_id": tenant_id,
            "data": data,
        }
        await self.redis_client.publish(channel, json.dumps(message, default=str))

    async def _broadcast_to_local_sockets(self, tenant_id: str, payload: dict):
        """Broadcasts payload to WebSockets connected to THIS server instance."""
        if tenant_id in self.active_connections:
            dead_sockets = set()
            for ws in self.active_connections[tenant_id]:
                try:
                    await ws.send_json(payload)
                except Exception:
                    dead_sockets.add(ws)
            for dead_ws in dead_sockets:
                self.disconnect(tenant_id, dead_ws)


ws_manager = ConnectionManager()