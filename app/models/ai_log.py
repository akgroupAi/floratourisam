"""AI interaction logging models."""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class AIConversation(BaseModel):
    """AI conversation session."""

    __tablename__ = "ai_conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Session info
    session_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )
    title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Context
    context_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )  # general, booking, medical, support
    context_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Statistics
    message_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    total_tokens_used: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    estimated_cost: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    # Feedback
    rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    feedback: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Metadata
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    logs: Mapped[List["AILog"]] = relationship(
        "AILog",
        back_populates="conversation",
        lazy="dynamic",
        order_by="AILog.created_at",
    )

    def __repr__(self) -> str:
        return f"AIConversation(id={self.id}, session={self.session_id})"


class AILog(BaseModel):
    """Individual AI interaction log."""

    __tablename__ = "ai_logs"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Request
    user_message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    system_prompt: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Response
    ai_response: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Model info
    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    model_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    # Token usage
    prompt_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Performance
    response_time_ms: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Cost
    cost: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    # Intent and entities (for NLU)
    detected_intent: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    detected_entities: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    # Actions taken
    actions_triggered: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Error handling
    is_error: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Feedback
    is_helpful: Mapped[Optional[bool]] = mapped_column(
        nullable=True,
    )
    feedback: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Request context
    request_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    conversation: Mapped["AIConversation"] = relationship(
        "AIConversation",
        back_populates="logs",
    )

    def __repr__(self) -> str:
        return f"AILog(id={self.id}, model={self.model_name})"
