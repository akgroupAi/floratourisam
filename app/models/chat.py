"""Chat models for real-time messaging."""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.utils.enums import ChatRoomType, MessageType


class ChatRoom(BaseModel):
    """Chat room for conversations."""

    __tablename__ = "chat_rooms"

    # Room info
    name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    room_type: Mapped[str] = mapped_column(
        String(20),
        default=ChatRoomType.CONSULTATION.value,
        nullable=False,
    )

    # Related entity
    consultation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consultations.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    closed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    # Metadata
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    message_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    participants: Mapped[List["ChatParticipant"]] = relationship(
        "ChatParticipant",
        back_populates="room",
        lazy="selectin",
    )
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="room",
        lazy="dynamic",
        order_by="ChatMessage.created_at",
    )

    def __repr__(self) -> str:
        return f"ChatRoom(id={self.id}, type={self.room_type})"


class ChatParticipant(BaseModel):
    """Participant in a chat room."""

    __tablename__ = "chat_participants"

    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_rooms.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    left_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Notification settings
    is_muted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    muted_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Read tracking
    last_read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    unread_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Role in room
    role: Mapped[str] = mapped_column(
        String(20),
        default="member",
        nullable=False,
    )  # admin, member

    # Relationships
    room: Mapped["ChatRoom"] = relationship(
        "ChatRoom",
        back_populates="participants",
    )

    def __repr__(self) -> str:
        return f"ChatParticipant(room_id={self.room_id}, user_id={self.user_id})"


class ChatMessage(BaseModel):
    """Message in a chat room."""

    __tablename__ = "chat_messages"

    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Message content
    message_type: Mapped[str] = mapped_column(
        String(20),
        default=MessageType.TEXT.value,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # File attachment
    file_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    file_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    file_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    file_size_bytes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Reply to
    reply_to_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Status
    is_edited: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    edited_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Read receipts
    read_by: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )  # {user_id: timestamp}

    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    room: Mapped["ChatRoom"] = relationship(
        "ChatRoom",
        back_populates="messages",
    )
    reply_to: Mapped[Optional["ChatMessage"]] = relationship(
        "ChatMessage",
        remote_side="ChatMessage.id",
    )

    def __repr__(self) -> str:
        return f"ChatMessage(id={self.id}, type={self.message_type})"
