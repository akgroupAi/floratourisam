"""Chat schemas."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BaseSchema
from app.utils.enums import ChatRoomType, MessageType


class ChatRoomCreate(BaseModel):
    """Chat room creation schema."""

    name: Optional[str] = Field(default=None, max_length=255)
    room_type: ChatRoomType = ChatRoomType.CONSULTATION
    consultation_id: Optional[UUID] = None
    participant_ids: List[UUID] = Field(..., min_length=1)


class ChatRoomResponse(BaseSchema):
    """Chat room response."""

    id: UUID
    name: Optional[str] = None
    room_type: str
    consultation_id: Optional[UUID] = None
    is_active: bool
    last_message_at: Optional[datetime] = None
    message_count: int
    created_at: datetime

    # Participants summary
    participant_count: int = 0
    unread_count: int = 0


class ChatRoomDetailResponse(ChatRoomResponse):
    """Chat room detail response."""

    participants: List["ChatParticipantResponse"] = []
    last_messages: List["ChatMessageResponse"] = []


class ChatParticipantResponse(BaseSchema):
    """Chat participant response."""

    id: UUID
    room_id: UUID
    user_id: UUID
    is_active: bool
    joined_at: datetime
    left_at: Optional[datetime] = None
    is_muted: bool
    last_read_at: Optional[datetime] = None
    unread_count: int
    role: str

    # User info
    user_name: Optional[str] = None
    user_avatar: Optional[str] = None


class ChatMessageCreate(BaseModel):
    """Chat message creation."""

    room_id: UUID
    message_type: MessageType = MessageType.TEXT
    content: str = Field(..., max_length=10000)
    reply_to_id: Optional[UUID] = None
    file_url: Optional[str] = Field(default=None, max_length=500)
    file_name: Optional[str] = Field(default=None, max_length=255)
    file_type: Optional[str] = Field(default=None, max_length=50)
    file_size_bytes: Optional[int] = None


class ChatMessageResponse(BaseSchema):
    """Chat message response."""

    id: UUID
    room_id: UUID
    sender_id: UUID
    message_type: str
    content: str
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    reply_to_id: Optional[UUID] = None
    is_edited: bool
    edited_at: Optional[datetime] = None
    created_at: datetime

    # Sender info
    sender_name: Optional[str] = None
    sender_avatar: Optional[str] = None

    # Reply info
    reply_to_content: Optional[str] = None


class ChatMessageUpdate(BaseModel):
    """Chat message update."""

    content: str = Field(..., max_length=10000)


class ChatWebSocketMessage(BaseModel):
    """WebSocket message format."""

    type: str  # message, typing, read, join, leave
    data: dict


class ChatTypingEvent(BaseModel):
    """Typing indicator event."""

    room_id: UUID
    user_id: UUID
    is_typing: bool


class ChatReadEvent(BaseModel):
    """Message read event."""

    room_id: UUID
    user_id: UUID
    last_read_message_id: UUID


class ChatRoomListResponse(BaseModel):
    """Chat room list for user."""

    rooms: List[ChatRoomResponse]
    total_unread: int
