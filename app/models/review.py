"""Review & Rating model.

A single polymorphic table covers all reviewable entities:
  doctor, hospital, hotel, apartment, restaurant

Business rules enforced at DB level:
  - UNIQUE (patient_id, entity_type, entity_id)  → one review per patient per entity
  - CHECK (rating BETWEEN 1 AND 5)

After a review is saved, the service recalculates `rating` and
`total_reviews` on the target entity row.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Review(BaseModel):
    """Patient review / star rating for a reviewed entity."""

    __tablename__ = "reviews"

    __table_args__ = (
        # One review per patient per entity
        UniqueConstraint("patient_id", "entity_type", "entity_id", name="uq_review_patient_entity"),
        # Rating must be 1–5
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_rating_range"),
        # Fast lookups by entity
        Index("ix_reviews_entity", "entity_type", "entity_id"),
        # Fast lookups by patient
        Index("ix_reviews_patient_id", "patient_id"),
        # Admin moderation queue
        Index("ix_reviews_is_approved", "is_approved"),
    )

    # ----- What is being reviewed -----
    entity_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="doctor | hospital | hotel | apartment | restaurant",
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="PK of the reviewed entity (no cross-table FK — polymorphic)",
    )

    # ----- Who is reviewing -----
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ----- Review content -----
    rating: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Star rating 1–5",
    )
    title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Short headline, e.g. 'Excellent care'",
    )
    body: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Full review text",
    )

    # ----- Verification & moderation -----
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Patient has a confirmed booking/consultation for this entity",
    )
    is_approved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Admin has approved for public display",
    )
    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Pinned / highlighted review",
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Admin rejection note (not shown publicly)",
    )

    # ----- Social -----
    helpful_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of users who marked this helpful",
    )

    # ----- Entity owner response -----
    response_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Official response from the reviewed entity",
    )
    response_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    response_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User ID of whoever wrote the response",
    )

    # ----- Verification links -----
    booking_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="SET NULL"),
        nullable=True,
        comment="Booking that verifies hotel/apartment/restaurant usage",
    )
    consultation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consultations.id", ondelete="SET NULL"),
        nullable=True,
        comment="Consultation that verifies doctor usage",
    )

    def __repr__(self) -> str:
        return f"Review(id={self.id}, entity_type={self.entity_type}, entity_id={self.entity_id}, rating={self.rating})"
