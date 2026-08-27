import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from jose import JWTError, jwt
from sqlalchemy import select
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.ws_manager import ws_manager
from app.models.user import User

router = APIRouter()


async def get_ws_user(token: str) -> User | None:
    """Authenticates WebSocket connections using the JWT token passed in query parameters."""
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
    Real-time collaboration WebSocket channel.
    Synchronizes document mutations and live states across all users in the tenant.
    """
    user = await get_ws_user(token)
    if not user or not user.tenant_id or not user.is_active:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    tenant_id_str = str(user.tenant_id)
    await ws_manager.connect(tenant_id_str, websocket)

    # Broadcast user join notification
    await ws_manager.publish_event(
        tenant_id=tenant_id_str,
        event_type="USER_JOINED",
        data={"username": user.username, "user_id": str(user.id)},
    )

    try:
        while True:
            # Keep socket alive and receive client messages (e.g. typing ping or presence)
            client_msg = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(tenant_id_str, websocket)
        await ws_manager.publish_event(
            tenant_id=tenant_id_str,
            event_type="USER_LEFT",
            data={"username": user.username, "user_id": str(user.id)},
        )