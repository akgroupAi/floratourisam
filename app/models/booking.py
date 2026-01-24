"""Booking model for unified booking management."""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.utils.enums import BookingStatus, BookingType

if TYPE_CHECKING:
    from app.models.patient import Patient


class Booking(BaseModel):
    """Unified booking model for all booking types."""

    __tablename__ = "bookings"

    # Patient
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Booking type and reference
    booking_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    reference_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    # Related entity (polymorphic reference)
    consultation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consultations.id", ondelete="SET NULL"),
        nullable=True,
    )
    hotel_room_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rooms.id", ondelete="SET NULL"),
        nullable=True,
    )
    restaurant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("restaurants.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default=BookingStatus.PENDING.value,
        nullable=False,
        index=True,
    )

    # Dates
    booking_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    check_in_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    check_out_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    scheduled_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Guest information
    guest_count: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    guest_details: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Pricing
    base_price: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    taxes: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    discount: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    total_price: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        nullable=False,
    )
    discount_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    # Payment
    payment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_paid: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Special requests
    special_requests: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    internal_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Confirmation
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    confirmed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    # Cancellation
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancellation_reason: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    cancelled_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    refund_amount: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    # Check-in/out tracking
    actual_check_in: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    actual_check_out: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Source tracking
    source: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )  # website, app, phone, partner
    source_reference: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Metadata
    booking_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    patient: Mapped["Patient"] = relationship(
        "Patient",
        back_populates="bookings",
    )

    def __repr__(self) -> str:
        return f"Booking(id={self.id}, ref={self.reference_number}, type={self.booking_type})"

    @property
    def nights(self) -> Optional[int]:
        """Calculate number of nights for hotel bookings."""
        if self.check_in_date and self.check_out_date:
            return (self.check_out_date - self.check_in_date).days
        return None
