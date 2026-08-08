"""Chat endpoints with WebSocket support."""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from starlette.websockets import WebSocketState

from app.api.deps import CurrentUser, DatabaseSession
from app.core.security import verify_token
from app.core.logging import get_logger
from app.db.session import async_session_factory
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatRoomCreate,
    ChatRoomListResponse,
    ChatRoomResponse,
)
from app.services.chat_service import ChatService
from app.services.notification_service import notification_service

logger = get_logger(__name__)

router = APIRouter()


@router.get("/rooms", response_model=ChatRoomListResponse)
async def list_chat_rooms(current_user: CurrentUser, db: DatabaseSession):
    """List user's chat rooms with unread counts."""
    service = ChatService(db)
    rooms, total_unread = await service.list_rooms_for_user(current_user.id)
    return {"rooms": rooms, "total_unread": total_unread}


@router.post("/rooms", response_model=ChatRoomResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_room(data: ChatRoomCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create a chat room with participants."""
    service = ChatService(db)
    
    # DEBUG: Log what's being sent
    logger.info(
        "create_room_request",
        current_user_id=str(current_user.id),
        participant_ids=[str(pid) for pid in data.participant_ids]
    )
    
    try:
        room = await service.create_room(data, created_by=current_user.id)
    except ValueError as exc:
        logger.error("create_room_validation_failed", error=str(exc), current_user=str(current_user.id))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Build response
    participant_count = len(data.participant_ids) + (1 if current_user.id not in data.participant_ids else 0)
    return {
        "id": room.id,
        "name": room.name,
        "room_type": room.room_type,
        "consultation_id": room.consultation_id,
        "is_active": room.is_active,
        "last_message_at": room.last_message_at,
        "message_count": room.message_count,
        "created_at": room.created_at,
        "participant_count": participant_count,
        "unread_count": 0,
    }


@router.get("/rooms/{room_id}/messages", response_model=list[ChatMessageResponse])
async def get_room_messages(
    room_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Get all messages in a chat room."""
    service = ChatService(db)

    # Verify room exists and user is a participant
    room = await service.get_room_by_id(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Chat room not found")
    if not await service.is_participant(room_id, current_user.id):
        raise HTTPException(status_code=403, detail="Not a participant of this room")

    messages = await service.get_messages(room_id)
    return messages


@router.get("/rooms/{room_id}/participants", response_model=list)
async def get_room_participants(
    room_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Debug endpoint: Get all participants in a room with their IDs."""
    service = ChatService(db)
    
    # Verify room exists
    room = await service.get_room_by_id(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Verify user is participant
    if not await service.is_participant(room_id, current_user.id):
        raise HTTPException(status_code=403, detail="Not a participant")
    
    # Get all participants
    from sqlalchemy import select
    from app.models.chat import ChatParticipant
    from app.models.user import User
    
    result = await db.execute(
        select(ChatParticipant, User)
        .join(User, ChatParticipant.user_id == User.id)
        .where(
            ChatParticipant.room_id == room_id,
            ChatParticipant.is_deleted == False,
        )
    )
    
    participants = []
    for participant, user in result.all():
        participants.append({
            "participant_id": str(participant.id),
            "user_id": str(participant.user_id),  # ← This should match sender_id in messages
            "user_name": user.full_name,
            "user_role": user.role,
            "joined_at": participant.joined_at.isoformat(),
            "is_active": participant.is_active,
        })
    
    return participants


@router.post("/rooms/{room_id}/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    room_id: UUID,
    data: ChatMessageCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Send a message to a chat room (REST). Also broadcasts via WebSocket."""
    service = ChatService(db)

    room = await service.get_room_by_id(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Chat room not found")
    if not room.is_active:
        raise HTTPException(status_code=400, detail="Chat room is closed")
    if not await service.is_participant(room_id, current_user.id):
        raise HTTPException(status_code=403, detail="Not a participant of this room")

    msg_dict = await service.send_message(room_id, current_user.id, data)

    # Broadcast to connected WebSocket clients
    await notification_service.send_chat_message(
        room_id,
        {"type": "message", "data": msg_dict},
    )
    return msg_dict


@router.post("/rooms/{room_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_messages_read(
    room_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Mark all messages in the room as read for the current user."""
    service = ChatService(db)
    if not await service.is_participant(room_id, current_user.id):
        raise HTTPException(status_code=403, detail="Not a participant of this room")
    await service.mark_read(room_id, current_user.id)


async def _safe_send(websocket: WebSocket, message: dict) -> None:
    """Send to a single socket without letting a dead peer raise."""
    if websocket.client_state != WebSocketState.CONNECTED:
        return
    try:
        await websocket.send_json(message)
    except Exception as exc:
        logger.warning("websocket_direct_send_failed", error=str(exc))


async def _reject(websocket: WebSocket, code: int, reason: str) -> None:
    """Accept the handshake, report the reason, then close.

    Closing before accept() makes the server answer the upgrade with a bare
    HTTP 403 — the close code and reason never reach the browser, so the client
    only ever sees an opaque connection failure. Accepting first means the
    frontend receives both an 'error' frame and a real close code.
    """
    try:
        await websocket.accept()
        await _safe_send(websocket, {"type": "error", "data": {"message": reason}})
        await websocket.close(code=code, reason=reason)
    except Exception as exc:
        logger.warning("websocket_reject_failed", reason=reason, error=str(exc))


async def _persist_and_broadcast(
    websocket: WebSocket,
    room_id: str,
    room_uuid: UUID,
    sender_uuid: UUID,
    data: dict,
) -> None:
    """Store an incoming chat message, then fan the stored row out to the room."""
    payload = data.get("data")
    if not isinstance(payload, dict):
        payload = {}

    content = (payload.get("content") or "").strip()
    if not content and not payload.get("file_url"):
        await _safe_send(
            websocket,
            {"type": "error", "data": {"message": "Message content is required"}},
        )
        return

    try:
        async with async_session_factory() as session:
            try:
                service = ChatService(session)
                msg_create = ChatMessageCreate(
                    room_id=room_uuid,
                    content=content,
                    message_type=payload.get("message_type") or "text",
                    reply_to_id=payload.get("reply_to_id"),
                    file_url=payload.get("file_url"),
                    file_name=payload.get("file_name"),
                    file_type=payload.get("file_type"),
                    file_size_bytes=payload.get("file_size_bytes"),
                )
                # Use the authenticated sender from the token, never the payload
                msg_dict = await service.send_message(room_uuid, sender_uuid, msg_create)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    except ValueError as val_err:
        # Covers pydantic validation and the service's participant guard
        logger.error(
            "websocket_message_validation_failed",
            error=str(val_err),
            sender=str(sender_uuid),
            room=room_id,
        )
        await _safe_send(
            websocket,
            {
                "type": "error",
                "data": {"message": "Failed to send message", "detail": str(val_err)},
            },
        )
        return
    except Exception as exc:
        logger.error(
            "chat_message_persist_failed",
            room_id=room_id,
            sender=str(sender_uuid),
            error=str(exc),
        )
        # Never broadcast an unsaved message — it would show up live for everyone
        # and then vanish on the next reload.
        await _safe_send(
            websocket,
            {"type": "error", "data": {"message": "Failed to send message"}},
        )
        return

    # Broadcast the persisted row (carries the real DB id and created_at)
    await notification_service.manager.broadcast(
        room_id, {"type": "message", "data": msg_dict}
    )


@router.websocket("/ws/{room_id}")
async def websocket_chat(websocket: WebSocket, room_id: str):
    """WebSocket endpoint for real-time chat.

    Requires 'token' query parameter with valid JWT.
    User ID is extracted from token (not client-provided).
    Messages with type 'message' are persisted to the database.
    Typing indicators and read events are broadcast only (not persisted).
    """
    # Validate the room id shape before spending a database round trip on it
    try:
        room_uuid = UUID(room_id)
    except (ValueError, AttributeError, TypeError):
        logger.warning("websocket_rejected", room_id=room_id, reason="invalid_room_id")
        await _reject(websocket, status.WS_1008_POLICY_VIOLATION, "Invalid room id")
        return

    # Extract and verify JWT token from query params
    token = websocket.query_params.get("token")
    if not token:
        logger.warning("websocket_rejected", room_id=room_id, reason="missing_token")
        await _reject(websocket, status.WS_1008_POLICY_VIOLATION, "Missing token")
        return

    sender_id = verify_token(token, token_type="access")
    if not sender_id:
        logger.warning("websocket_rejected", room_id=room_id, reason="invalid_token")
        await _reject(websocket, status.WS_1008_POLICY_VIOLATION, "Invalid token")
        return

    try:
        sender_uuid = UUID(sender_id)
    except (ValueError, AttributeError, TypeError):
        logger.warning(
            "websocket_rejected",
            room_id=room_id,
            reason="token_subject_not_a_uuid",
            jwt_sender_id=sender_id,
        )
        await _reject(websocket, status.WS_1008_POLICY_VIOLATION, "Invalid token")
        return

    # Verify user is a participant in the room
    try:
        async with async_session_factory() as session:
            service = ChatService(session)

            if not await service.is_participant(room_uuid, sender_uuid):
                # Report the room's roster so the mismatch is visible in the logs.
                # is_active matters here — is_participant requires it, so a member
                # who left still appears on the roster but is correctly refused.
                from sqlalchemy import select

                from app.models.chat import ChatParticipant

                participants_result = await session.execute(
                    select(ChatParticipant.user_id, ChatParticipant.is_active).where(
                        ChatParticipant.room_id == room_uuid,
                        ChatParticipant.is_deleted == False,
                    )
                )
                room_participants = [
                    {"user_id": str(row.user_id), "is_active": row.is_active}
                    for row in participants_result.all()
                ]

                logger.error(
                    "websocket_sender_not_in_room",
                    room_id=room_id,
                    jwt_sender_id=sender_id,
                    room_participants=room_participants,
                )
                await _reject(
                    websocket, status.WS_1008_POLICY_VIOLATION, "Not a participant"
                )
                return
    except Exception as exc:
        logger.error(
            "websocket_participant_check_failed",
            room_id=room_id,
            jwt_sender_id=sender_id,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        await _reject(websocket, status.WS_1011_SERVER_ERROR, "Internal error")
        return

    await notification_service.manager.connect(websocket, room_id)
    logger.info("websocket_connected", room_id=room_id, sender_id=sender_id)

    try:
        while True:
            try:
                data = await websocket.receive_json()
            except (ValueError, TypeError):
                # Malformed frame — tell the sender but keep the socket open,
                # otherwise one bad payload ends the session.
                await _safe_send(
                    websocket,
                    {"type": "error", "data": {"message": "Invalid JSON payload"}},
                )
                continue

            if not isinstance(data, dict):
                await _safe_send(
                    websocket,
                    {"type": "error", "data": {"message": "Expected a JSON object"}},
                )
                continue

            msg_type = data.get("type", "")

            # Keepalive — answer the sender only, never fan out to the room
            if msg_type == "ping":
                await _safe_send(websocket, {"type": "pong"})
                continue
            if msg_type == "pong":
                continue

            if msg_type == "message":
                await _persist_and_broadcast(
                    websocket, room_id, room_uuid, sender_uuid, data
                )
                continue

            # Non-message events (typing, read) — broadcast without persisting.
            # Stamp the authenticated sender so peers cannot be impersonated.
            event = dict(data)
            event_data = event.get("data")
            if isinstance(event_data, dict):
                stamped = dict(event_data)
                stamped["sender_id"] = sender_id
                stamped.setdefault("user_id", sender_id)
                event["data"] = stamped
            await notification_service.manager.broadcast(room_id, event)

    except WebSocketDisconnect:
        logger.info("websocket_disconnected", room_id=room_id, sender_id=sender_id)
    except Exception as exc:
        logger.error(
            "websocket_loop_failed",
            room_id=room_id,
            sender_id=sender_id,
            error=str(exc),
            error_type=type(exc).__name__,
        )
    finally:
        # Always deregister. A socket left behind here would break delivery for
        # every other member of the room on the next broadcast.
        notification_service.manager.disconnect(websocket, room_id)

