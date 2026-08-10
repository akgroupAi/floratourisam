"""Admin chat oversight schemas."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ChatRoomParticipant(BaseModel):
    """Someone in a chat room."""

    user_id: UUID
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None


class AdminChatRoomResponse(BaseModel):
    """Chat room row for admin."""

    id: UUID
    name: Optional[str] = None
    room_type: Optional[str] = None
    consultation_id: Optional[UUID] = None
    is_active: bool
    message_count: int
    last_message_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    participants: List[ChatRoomParticipant] = []
    created_at: datetime


class AdminChatMessageResponse(BaseModel):
    """One message in a transcript."""

    id: UUID
    room_id: UUID
    sender_id: Optional[UUID] = None
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    sender_role: Optional[str] = None
    message_type: Optional[str] = None
    content: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    is_edited: bool = False
    is_deleted: bool = False
    created_at: datetime


class AdminChatStatsResponse(BaseModel):
    """Chat volume across the platform."""

    total_rooms: int
    active_rooms: int
    rooms_active_last_24h: int
    rooms_by_type: dict[str, int]
    total_messages: int
    messages_last_24h: int
    messages_last_7d: int
    average_messages_per_room: float


class ChatMessageDeleteRequest(BaseModel):
    """Reason for moderating a message away — required, and kept on the record."""

    reason: str = Field(..., min_length=3, max_length=500)
