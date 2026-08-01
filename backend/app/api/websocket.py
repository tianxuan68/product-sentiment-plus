"""JeecgBoot 系统消息 WebSocket（精简版：维持连接 + 心跳）。"""
from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


@router.websocket("/websocket/{user_id}")
async def system_websocket(websocket: WebSocket, user_id: str):
    subprotocols = websocket.scope.get("subprotocols") or []
    subprotocol = subprotocols[0] if subprotocols else None
    await websocket.accept(subprotocol=subprotocol)
    logger.debug("WebSocket connected: %s", user_id)
    try:
        while True:
            data = await websocket.receive_text()
            # 前端 @vueuse/core heartbeat 发送 "ping"
            if data == "ping":
                await websocket.send_text("ping")
    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected: %s", user_id)
    except Exception as exc:
        logger.debug("WebSocket closed (%s): %s", user_id, exc)
