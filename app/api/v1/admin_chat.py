"""Admin oversight of doctor/patient chat.

Chat rooms are otherwise visible only to their participants. These endpoints exist for
dispute resolution, compliance, and moderation — not for routine browsing. Transcript
access is logged with the acting admin.
"""

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.schemas.admin_chat import (
    AdminChatMessageResponse,
    AdminChatRoomResponse,
    AdminChatStatsResponse,
    ChatMessageDeleteRequest,
)
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.services.admin_chat_service import AdminChatService

router = APIRouter()


@router.get(
    "/stats",
    response_model=AdminChatStatsResponse,
    dependencies=[RequireAdmin],
    summary="Chat volume statistics",
)
async def get_chat_stats(db: DatabaseSession):
    """Room and message counts, including how much traffic is from the last 24 hours."""
    return await AdminChatService(db).get_stats()


@router.get(
    "/rooms",
    response_model=PaginatedResponse[AdminChatRoomResponse],
    dependencies=[RequireAdmin],
    summary="List chat rooms",
)
async def list_rooms(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    room_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    participant_id: Optional[UUID] = Query(None, description="Rooms one user is in"),
    consultation_id: Optional[UUID] = Query(None, description="Room for one consultation"),
    search: Optional[str] = Query(None, description="Room name"),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
):
    """Chat rooms with their participants, most recently active first."""
    items, total = await AdminChatService(db).list_rooms(
        PaginationParams(page=page, page_size=page_size),
        room_type=room_type,
        is_active=is_active,
        participant_id=participant_id,
        consultation_id=consultation_id,
        search=search,
        from_date=from_date,
        to_date=to_date,
    )
    return PaginatedResponse.create(items, total, page, page_size)


@router.get(
    "/rooms/{room_id}/messages",
    response_model=PaginatedResponse[AdminChatMessageResponse],
    dependencies=[RequireAdmin],
    summary="Read a room transcript",
)
async def get_room_messages(
    room_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search message text"),
    include_deleted: bool = Query(False, description="Include moderated/deleted messages"),
):
    """
    Full transcript for one room, oldest first.

    Read-only — admins cannot post into a room. **Each call is written to the
    application log** with the room and the acting admin, because reading a
    doctor/patient conversation is itself a sensitive action.
    """
    service = AdminChatService(db)
    room = await service.get_room(room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat room not found")

    items, total = await service.get_messages(
        room_id,
        PaginationParams(page=page, page_size=page_size),
        accessed_by=current_user.id,
        search=search,
        include_deleted=include_deleted,
    )
    return PaginatedResponse.create(items, total, page, page_size)


@router.delete(
    "/messages/{message_id}",
    response_model=MessageResponse,
    dependencies=[RequireAdmin],
    summary="Moderate a message",
)
async def delete_message(
    message_id: UUID,
    data: ChatMessageDeleteRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """
    Soft-delete an abusive or mistaken message.

    The row is kept with the reason, the acting admin, and a timestamp recorded on it,
    so the moderation itself stays auditable. Pass `include_deleted=true` on the
    transcript endpoint to see moderated messages.
    """
    if not await AdminChatService(db).delete_message(
        message_id, deleted_by=current_user.id, reason=data.reason
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return MessageResponse(message="Message deleted")
