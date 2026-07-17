from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

from app.core.redis_client import get_redis
from app.core.security import InvalidTokenError, TokenType, decode_token

router = APIRouter()


def _canal_tenant(tenant_id: str) -> str:
    return f"tenant.{tenant_id}.notificacoes"


@router.websocket("/ws/notificacoes")
async def notificacoes_ws(websocket: WebSocket, token: str = Query(...), redis: Redis = Depends(get_redis)):
    try:
        payload = decode_token(token, expected_type=TokenType.ACCESS)
    except InvalidTokenError:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    tenant_id = payload["tenant_id"]
    pubsub = redis.pubsub()
    await pubsub.subscribe(_canal_tenant(tenant_id))
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is not None:
                await websocket.send_text(message["data"])
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        await pubsub.unsubscribe(_canal_tenant(tenant_id))
        await pubsub.aclose()
