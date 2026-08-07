"""Notification service for WebSocket and push notifications."""

import asyncio
from typing import Dict, List, Set, Union
from uuid import UUID

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.core.logging import get_logger

logger = get_logger(__name__)

RoomId = Union[str, UUID]


def room_key(room_id: RoomId) -> str:
    """Normalise a room identifier into a single canonical dictionary key.

    WebSocket clients arrive with the id as a raw path string while REST callers
    pass a parsed UUID. Both are funnelled through here so a room registered by
    one path is always found by the other, regardless of casing or formatting.
    """
    if isinstance(room_id, UUID):
        return str(room_id)
    try:
        return str(UUID(str(room_id)))
    except (ValueError, AttributeError, TypeError):
        # Not a UUID — fall back to the raw value so non-UUID keys still work.
        return str(room_id)


class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: RoomId):
        await websocket.accept()
        self.register(websocket, room_id)

    def register(self, websocket: WebSocket, room_id: RoomId):
        """Track an already-accepted socket against a room."""
        key = room_key(room_id)
        self.active_connections.setdefault(key, set()).add(websocket)

    def disconnect(self, websocket: WebSocket, room_id: RoomId):
        key = room_key(room_id)
        connections = self.active_connections.get(key)
        if connections is None:
            return
        connections.discard(websocket)
        # Drop empty rooms so the registry does not grow without bound.
        if not connections:
            self.active_connections.pop(key, None)

    def connection_count(self, room_id: RoomId) -> int:
        return len(self.active_connections.get(room_key(room_id), ()))

    async def broadcast(self, room_id: RoomId, message: dict):
        """Fan a message out to every live socket in the room.

        Each send is isolated: a socket that has already gone away is dropped
        from the registry instead of aborting delivery for everyone behind it.
        """
        key = room_key(room_id)
        connections = self.active_connections.get(key)
        if not connections:
            return

        # Iterate a snapshot — pruning below mutates the underlying set, and a
        # concurrent disconnect can land mid-broadcast.
        targets: List[WebSocket] = list(connections)
        results = await asyncio.gather(
            *(self._send(websocket, message) for websocket in targets),
            return_exceptions=True,
        )

        for websocket, delivered in zip(targets, results):
            if delivered is not True:
                self.disconnect(websocket, key)

    async def _send(self, websocket: WebSocket, message: dict) -> bool:
        """Send to one socket, reporting failure instead of raising."""
        if websocket.client_state != WebSocketState.CONNECTED:
            return False
        try:
            await websocket.send_json(message)
            return True
        except Exception as exc:
            logger.warning("websocket_send_failed", error=str(exc), error_type=type(exc).__name__)
            return False


class NotificationService:
    def __init__(self):
        self.manager = ConnectionManager()

    async def send_notification(self, user_id: UUID, notification: dict):
        """Push a notification to any socket registered under this user id.

        No endpoint currently opens a per-user socket, so this is a no-op until
        one exists. It stays safe to call from anywhere in the meantime.
        """
        await self.manager.broadcast(str(user_id), notification)

    async def send_chat_message(self, room_id: RoomId, message: dict):
        await self.manager.broadcast(room_id, message)


notification_service = NotificationService()
