"""Notification service for WebSocket and push notifications.

Socket registries live in process memory, so with more than one worker a
broadcast raised in worker A cannot reach a socket held by worker B. The
Redis backplane below republishes every broadcast to all workers, which is
what makes chat work under ``--workers N``. Without Redis the service still
runs, but live delivery only spans a single worker.
"""

import asyncio
import json
from typing import Awaitable, Callable, Dict, List, Optional, Set, Union
from uuid import UUID

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.core.config import settings
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
        # Set by ChatBackplane once Redis is live. While it is None every
        # broadcast is delivered straight to this worker's own sockets.
        self.publisher: Optional[Callable[[RoomId, dict], Awaitable[bool]]] = None

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
        """Deliver a message to the room across every worker.

        With the backplane up the message is only published — this worker
        receives its own publication back through the subscription and delivers
        locally from there, so each socket is written to exactly once. If Redis
        is disabled or unreachable we fall back to local-only delivery, which is
        correct for a single worker and degraded (but not broken) for several.
        """
        if self.publisher is not None and await self.publisher(room_id, message):
            return
        await self.deliver_local(room_id, message)

    async def deliver_local(self, room_id: RoomId, message: dict):
        """Fan a message out to every live socket held by *this* worker.

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


class ChatBackplane:
    """Redis pub/sub fan-out so every uvicorn worker sees every broadcast.

    One channel carries all rooms. Each worker receives every published
    message and drops the ones for rooms it holds no sockets for — cheaper
    than subscribing and unsubscribing as rooms come and go, and chat volume
    is far below the point where that filtering costs anything.
    """

    CHANNEL = "chat:broadcast"

    # An idle pub/sub socket reports a read timeout; that is routine, not a
    # failure. Poll on this interval so a quiet channel never looks like a
    # dead one.
    POLL_TIMEOUT = 1.0
    RECONNECT_DELAY_MIN = 1.0
    RECONNECT_DELAY_MAX = 30.0
    # How long startup waits for the first subscription before moving on.
    READY_TIMEOUT = 10.0

    def __init__(self, manager: ConnectionManager):
        self._manager = manager
        self._redis = None
        self._pubsub = None
        self._task: Optional[asyncio.Task] = None
        self._subscribed = False
        self._stopping = False
        self._ready = asyncio.Event()

    @property
    def active(self) -> bool:
        """True only while a live subscription is in place."""
        return self._subscribed and self._redis is not None

    async def start(self) -> None:
        """Begin the supervised subscribe/listen loop. Never raises."""
        if not settings.REDIS_ENABLED:
            logger.warning(
                "chat_backplane_disabled",
                reason="REDIS_ENABLED is false — live chat will not cross workers",
            )
            return

        try:
            import redis.asyncio as redis_asyncio

            self._redis = redis_asyncio.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                # Keep the pub/sub connection healthy through idle periods and
                # any proxy or firewall that reaps quiet sockets.
                health_check_interval=30,
                socket_keepalive=True,
            )
            await self._redis.ping()
        except Exception as exc:
            logger.error(
                "chat_backplane_start_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            await self.stop()
            return

        self._stopping = False
        self._ready.clear()
        self._task = asyncio.create_task(self._run())

        # Don't report success until the subscription is actually up, otherwise
        # the startup log claims a backplane that may never have attached.
        try:
            await asyncio.wait_for(self._ready.wait(), timeout=self.READY_TIMEOUT)
            logger.info("chat_backplane_started", channel=self.CHANNEL)
        except asyncio.TimeoutError:
            logger.error(
                "chat_backplane_not_ready",
                channel=self.CHANNEL,
                timeout_seconds=self.READY_TIMEOUT,
                detail="still retrying in the background; chat stays worker-local until it attaches",
            )

    async def _run(self) -> None:
        """Stay subscribed for the life of the process, reconnecting as needed.

        A dropped subscription used to end the listener for good, which left the
        worker publishing into a channel nobody read and delivering only to its
        own sockets — chat looked broken but logged nothing after the first
        error. The loop below always comes back.
        """
        delay = self.RECONNECT_DELAY_MIN

        while not self._stopping:
            try:
                self._pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
                await self._pubsub.subscribe(self.CHANNEL)
                self._subscribed = True
                self._manager.publisher = self.publish
                self._ready.set()
                delay = self.RECONNECT_DELAY_MIN
                logger.info("chat_backplane_subscribed", channel=self.CHANNEL)

                await self._consume()

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "chat_backplane_reconnecting",
                    error=str(exc),
                    error_type=type(exc).__name__,
                    retry_in_seconds=delay,
                )
            finally:
                self._subscribed = False
                self._ready.clear()
                self._manager.publisher = None
                await self._close_pubsub()

            if self._stopping:
                break

            await asyncio.sleep(delay)
            delay = min(delay * 2, self.RECONNECT_DELAY_MAX)

    async def _consume(self) -> None:
        """Read the channel until the subscription breaks or we shut down."""
        while not self._stopping:
            raw = await self._pubsub.get_message(
                ignore_subscribe_messages=True, timeout=self.POLL_TIMEOUT
            )
            # No traffic in this window — the connection is fine, keep waiting.
            if raw is None:
                continue
            if raw.get("type") != "message":
                continue

            try:
                envelope = json.loads(raw["data"])
                room = envelope["room"]
                message = envelope["message"]
            except (ValueError, KeyError, TypeError) as exc:
                logger.warning("chat_backplane_bad_envelope", error=str(exc))
                continue

            await self._manager.deliver_local(room, message)

    async def _close_pubsub(self) -> None:
        if self._pubsub is None:
            return
        try:
            await self._pubsub.close()
        except Exception:
            pass
        self._pubsub = None

    async def publish(self, room_id: RoomId, message: dict) -> bool:
        """Publish to all workers. Returns False so the caller can fall back."""
        if not self.active:
            return False
        try:
            await self._redis.publish(
                self.CHANNEL,
                json.dumps(
                    {"room": room_key(room_id), "message": message}, default=str
                ),
            )
            return True
        except Exception as exc:
            logger.warning(
                "chat_backplane_publish_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return False

    async def stop(self) -> None:
        """Tear down on shutdown. Never raises."""
        self._stopping = True
        self._subscribed = False
        self._manager.publisher = None

        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.warning("chat_backplane_stop_failed", error=str(exc))
            self._task = None

        await self._close_pubsub()

        if self._redis is not None:
            try:
                await self._redis.close()
            except Exception as exc:
                logger.warning("chat_backplane_close_failed", error=str(exc))
            self._redis = None


class NotificationService:
    def __init__(self):
        self.manager = ConnectionManager()
        self.backplane = ChatBackplane(self.manager)

    async def start(self) -> None:
        await self.backplane.start()

    async def stop(self) -> None:
        await self.backplane.stop()

    async def send_notification(self, user_id: UUID, notification: dict):
        """Push a notification to any socket registered under this user id.

        No endpoint currently opens a per-user socket, so this is a no-op until
        one exists. It stays safe to call from anywhere in the meantime.
        """
        await self.manager.broadcast(str(user_id), notification)

    async def send_chat_message(self, room_id: RoomId, message: dict):
        await self.manager.broadcast(room_id, message)


notification_service = NotificationService()
