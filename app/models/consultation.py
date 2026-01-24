"""Consultation model for patient-doctor interactions."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.utils.enums import ConsultationStatus, ConsultationType

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.doctor import Doctor
    from app.models.medical_report import MedicalReport


class Consultation(BaseModel):
    """Consultation between patient and doctor."""

    __tablename__ = "consultations"

    # Participants
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Type and status
    consultation_type: Mapped[str] = mapped_column(
        String(20),
        default=ConsultationType.VIDEO.value,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=ConsultationStatus.SCHEDULED.value,
        nullable=False,
        index=True,
    )

    # Scheduling
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    duration_minutes: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Symptoms and reason
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    symptoms: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    symptom_duration: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Doctor notes
    diagnosis: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    prescription: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    recommendations: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    follow_up_required: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    follow_up_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Video/chat session
    session_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    session_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    recording_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Payment
    fee: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    is_paid: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    payment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    # Rating
    rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    review: Mapped[Optional[str]] = mapped_column(
        Text,
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

    # Reference
    reference_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )

    # Relationships
    patient: Mapped["Patient"] = relationship(
        "Patient",
        back_populates="consultations",
    )
    doctor: Mapped["Doctor"] = relationship(
        "Doctor",
        back_populates="consultations",
    )
    medical_reports: Mapped[List["MedicalReport"]] = relationship(
        "MedicalReport",
        back_populates="consultation",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"Consultation(id={self.id}, ref={self.reference_number})"

    @property
    def actual_duration_minutes(self) -> Optional[int]:
        """Calculate actual duration if consultation is completed."""
        if self.started_at and self.ended_at:
            delta = self.ended_at - self.started_at
            return int(delta.total_seconds() / 60)
        return None
