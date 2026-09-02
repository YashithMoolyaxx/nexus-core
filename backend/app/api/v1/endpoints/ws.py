import json
import uuid
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from sqlalchemy import select
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.presence import (
    get_active_tenant_operators,
    refresh_presence,
    register_presence,
    unregister_presence,
)
from app.core.ws_manager import ws_manager
from app.models.tenant import Tenant
from app.models.user import User

router = APIRouter()


@router.websocket("/workspace")
async def workspace_websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
):
    # 1. Validate JWT Auth Token
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id_str: str = payload.get("sub")
        if not user_id_str:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        user_uuid = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 2. Retrieve User & Tenant Scope with an ephemeral DB session
    async with AsyncSessionLocal() as session:
        user_res = await session.execute(select(User).where(User.id == user_uuid))
        user = user_res.scalars().first()

        if not user or not user.is_active:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Fallback to default tenant if not assigned
        if not user.tenant_id:
            tenant_res = await session.execute(select(Tenant).where(Tenant.slug == "core-engineering"))
            default_tenant = tenant_res.scalars().first()
            user_tenant_id = str(default_tenant.id) if default_tenant else str(uuid.uuid4())
        else:
            user_tenant_id = str(user.tenant_id)

        user_name = user.username
        user_id = str(user.id)

    # 3. Accept WebSocket Connection
    await ws_manager.connect(websocket, user_tenant_id)

    # 4. Register Ephemeral Presence & Broadcast Sync Event
    await register_presence(user_tenant_id, user_id, user_name)
    active_operators = await get_active_tenant_operators(user_tenant_id)
    await ws_manager.publish_event(
        tenant_id=user_tenant_id,
        event_type="PRESENCE_SYNC",
        data={"active_users": active_operators},
    )

    # 5. Persistent Event Stream Loop
    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                msg_data = json.loads(raw_text)
                if msg_data.get("type") == "HEARTBEAT":
                    await refresh_presence(user_tenant_id, user_id, user_name)
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_tenant_id)
        await unregister_presence(user_tenant_id, user_id)
        updated_operators = await get_active_tenant_operators(user_tenant_id)
        await ws_manager.publish_event(
            tenant_id=user_tenant_id,
            event_type="PRESENCE_SYNC",
            data={"active_users": updated_operators},
        )