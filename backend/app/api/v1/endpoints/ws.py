import asyncio
import json
import uuid
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from sqlalchemy import select
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.presence import PresenceService
from app.core.ws_manager import ws_manager
from app.models.user import User

router = APIRouter()


async def get_ws_user(token: str) -> User | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return None
    except JWTError:
        return None

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
        return result.scalars().first()


@router.websocket("/workspace")
async def workspace_ws_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT Bearer token"),
):
    """
    Real-time collaboration & Ephemeral Presence WebSocket endpoint.
    Processes live document synchronizations and periodic Redis TTL heartbeats.
    """
    user = await get_ws_user(token)
    if not user or not user.tenant_id or not user.is_active:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    tenant_id_str = str(user.tenant_id)
    user_id_str = str(user.id)

    await ws_manager.connect(tenant_id_str, websocket)

    # 1. Register presence in Redis with 15s TTL
    await PresenceService.heartbeat(tenant_id_str, user_id_str, user.username)

    # 2. Broadcast active presence state to all tenant nodes
    active_operators = await PresenceService.get_active_users(tenant_id_str)
    await ws_manager.publish_event(
        tenant_id=tenant_id_str,
        event_type="PRESENCE_SYNC",
        data={"active_users": active_operators},
    )

    try:
        while True:
            # Receive heartbeat or edit events from client
            raw_data = await websocket.receive_text()
            try:
                message = json.loads(raw_data)
                if message.get("type") == "HEARTBEAT":
                    await PresenceService.heartbeat(tenant_id_str, user_id_str, user.username)
                    # Broadcast refreshed presence list
                    active_ops = await PresenceService.get_active_users(tenant_id_str)
                    await ws_manager.publish_event(
                        tenant_id=tenant_id_str,
                        event_type="PRESENCE_SYNC",
                        data={"active_users": active_ops},
                    )
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        # On disconnect: Remove presence key and notify workspace
        ws_manager.disconnect(tenant_id_str, websocket)
        await PresenceService.remove(tenant_id_str, user_id_str)
        active_ops = await PresenceService.get_active_users(tenant_id_str)
        await ws_manager.publish_event(
            tenant_id=tenant_id_str,
            event_type="PRESENCE_SYNC",
            data={"active_users": active_ops},
        )