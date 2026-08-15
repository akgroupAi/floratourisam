"""Booking model for unified booking management."""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
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
    apartment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("apartments.id", ondelete="SET NULL"),
        nullable=True,
    )
    restaurant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("restaurants.id", ondelete="SET NULL"),
        nullable=True,
    )
    package_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("medical_packages.id", ondelete="SET NULL"),
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
    # Charged to the customer on top of the subtotal; included in total_price.
    platform_fee: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        server_default="0",
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
    # What the customer forfeits under the cancellation policy.
    cancellation_charge: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    # Refund workflow. A cancellation computes the amount and queues it; an admin
    # releases it. none | pending | processed | rejected | failed
    refund_status: Mapped[str] = mapped_column(
        String(20),
        default="none",
        nullable=False,
        server_default="none",
        index=True,
    )
    refund_requested_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    refund_processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    refund_processed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    refund_reference: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )  # Razorpay refund id
    refund_note: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )  # Rejection reason, or the gateway failure

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

    guests: Mapped[list["BookingGuest"]] = relationship(
        "BookingGuest",
        back_populates="booking",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list["BookingDocument"]] = relationship(
        "BookingDocument",
        back_populates="booking",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"Booking(id={self.id}, ref={self.reference_number}, type={self.booking_type})"

    @property
    def nights(self) -> Optional[int]:
        """Calculate number of nights for hotel bookings."""
        if self.check_in_date and self.check_out_date:
            return (self.check_out_date - self.check_in_date).days
        return None


class BookingGuest(BaseModel):
    """A traveller on a booking — the patient, or someone accompanying them.

    Bookings previously carried only a `guest_count` and a free-form `guest_details`
    blob. Medical travel needs the real thing: who is coming, their passport, and who to
    call. One row per person so a document can be attached to the right individual.
    """

    __tablename__ = "booking_guests"

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # "patient" — the person being treated. "companion" — anyone travelling with them.
    guest_type: Mapped[str] = mapped_column(
        String(20),
        default="companion",
        nullable=False,
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Identity
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    nationality: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Travel documents. Numbers only — the scanned copies live in BookingDocument.
    passport_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    passport_expiry: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Contact
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Companions only: how they relate to the patient (spouse, parent, attendant...)
    relationship_to_patient: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Anything the property needs to know — wheelchair, dietary, interpreter.
    special_needs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    booking: Mapped["Booking"] = relationship("Booking", back_populates="guests")
    documents: Mapped[list["BookingDocument"]] = relationship(
        "BookingDocument",
        back_populates="guest",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"BookingGuest(id={self.id}, name={self.full_name}, type={self.guest_type})"


class BookingDocument(BaseModel):
    """A file uploaded against a booking — passport, flight ticket, visa, insurance.

    `guest_id` is optional: a passport belongs to a person, a hotel voucher or a shared
    flight booking belongs to the booking as a whole.

    `file_path` is a server-side location and is never browser-reachable. Files are
    served through an authenticated download endpoint — these are passports.
    """

    __tablename__ = "booking_documents"

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    guest_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("booking_guests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # passport, flight_ticket, visa, insurance, medical_report, id_proof, other

    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    booking: Mapped["Booking"] = relationship("Booking", back_populates="documents")
    guest: Mapped[Optional["BookingGuest"]] = relationship(
        "BookingGuest", back_populates="documents"
    )

    def __repr__(self) -> str:
        return f"BookingDocument(id={self.id}, type={self.document_type})"
