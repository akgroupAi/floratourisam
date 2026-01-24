"""Notification service for WebSocket and push notifications."""

from typing import Dict, Set
from uuid import UUID

from fastapi import WebSocket

from app.core.logging import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = set()
        self.active_connections[room_id].add(websocket)

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_connections:
            self.active_connections[room_id].discard(websocket)

    async def broadcast(self, room_id: str, message: dict):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                await connection.send_json(message)


class NotificationService:
    def __init__(self):
        self.manager = ConnectionManager()

    async def send_notification(self, user_id: UUID, notification: dict):
        await self.manager.broadcast(str(user_id), notification)

    async def send_chat_message(self, room_id: UUID, message: dict):
        await self.manager.broadcast(str(room_id), message)


notification_service = NotificationService()
