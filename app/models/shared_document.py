"""Models for doctor-patient document sharing."""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class SharedDocument(BaseModel):
    """A document sent between a patient and a doctor."""

    __tablename__ = "shared_documents"

    # Who sent / who receives
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    receiver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Optional link to existing document record
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Optional link to consultation
    consultation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consultations.id", ondelete="SET NULL"),
        nullable=True,
    )

    # File info
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Document classification
    document_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # lab_report, prescription, xray, mri_scan, etc.
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status tracking
    is_viewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    viewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    comments: Mapped[List["DocumentComment"]] = relationship(
        "DocumentComment",
        back_populates="shared_document",
        lazy="selectin",
        order_by="DocumentComment.created_at",
    )

    def __repr__(self) -> str:
        return f"SharedDocument(id={self.id}, sender={self.sender_id}, receiver={self.receiver_id})"


class DocumentComment(BaseModel):
    """Comment on a shared document."""

    __tablename__ = "document_comments"

    shared_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shared_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    shared_document: Mapped["SharedDocument"] = relationship(
        "SharedDocument",
        back_populates="comments",
    )

    def __repr__(self) -> str:
        return f"DocumentComment(id={self.id}, doc={self.shared_document_id})"
