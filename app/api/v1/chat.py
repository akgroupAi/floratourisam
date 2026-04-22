"""Chat endpoints with WebSocket support."""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status

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
    try:
        room = await service.create_room(data, created_by=current_user.id)
    except ValueError as exc:
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


@router.websocket("/ws/{room_id}")
async def websocket_chat(websocket: WebSocket, room_id: str):
    """WebSocket endpoint for real-time chat.

    Requires 'token' query parameter with valid JWT.
    User ID is extracted from token (not client-provided).
    Messages with type 'message' are persisted to the database.
    Typing indicators and read events are broadcast only (not persisted).
    """
    # Extract and verify JWT token from query params
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token")
        return

    sender_id = verify_token(token, token_type="access")
    if not sender_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return

    # Verify user is a participant in the room
    try:
        async with async_session_factory() as session:
            service = ChatService(session)
            if not await service.is_participant(UUID(room_id), UUID(sender_id)):
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Not a participant")
                return
    except Exception as exc:
        logger.error("websocket_participant_check_failed", room_id=room_id, error=str(exc))
        await websocket.close(code=status.WS_1011_SERVER_ERROR, reason="Internal error")
        return

    await notification_service.manager.connect(websocket, room_id)
    logger.info("websocket_connected", room_id=room_id, sender_id=sender_id)
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "message":
                # Persist the message to the database
                payload = data.get("data", {})
                content = payload.get("content", "")

                if content:
                    try:
                        async with async_session_factory() as session:
                            try:
                                service = ChatService(session)
                                msg_create = ChatMessageCreate(
                                    room_id=room_id,
                                    content=content,
                                    message_type=payload.get("message_type", "text"),
                                    reply_to_id=payload.get("reply_to_id"),
                                    file_url=payload.get("file_url"),
                                    file_name=payload.get("file_name"),
                                    file_type=payload.get("file_type"),
                                    file_size_bytes=payload.get("file_size_bytes"),
                                )
                                # Use authenticated sender_id from token, not from payload
                                msg_dict = await service.send_message(
                                    UUID(room_id), UUID(sender_id), msg_create
                                )
                                await session.commit()
                                # Broadcast the persisted message (with DB id)
                                await notification_service.manager.broadcast(
                                    room_id, {"type": "message", "data": msg_dict}
                                )
                                continue
                            except ValueError as val_err:
                                logger.error("websocket_message_validation_failed", error=str(val_err), sender=sender_id, room=room_id)
                                await websocket.send_json({
                                    "type": "error",
                                    "data": {
                                        "message": "Failed to send message",
                                        "detail": str(val_err)
                                    }
                                })
                                await session.rollback()
                                continue
                            except Exception:
                                await session.rollback()
                                raise
                    except Exception as exc:
                        logger.error("chat_message_persist_failed", room_id=room_id, sender=sender_id, error=str(exc))
                        # If DB save fails, still broadcast the raw message
                        await notification_service.manager.broadcast(room_id, data)
                        continue

            # Non-message events (typing, read) — broadcast without persisting
            await notification_service.manager.broadcast(room_id, data)

    except WebSocketDisconnect:
        logger.info("websocket_disconnected", room_id=room_id, sender_id=sender_id)
        notification_service.manager.disconnect(websocket, room_id)

