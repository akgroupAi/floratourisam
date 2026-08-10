"""Treatment Proposal model.

A doctor sends a treatment proposal (with cost breakdown) to a patient.
The patient can approve, reject, or request changes.
Linked to a consultation so both parties can reference the context.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, Time
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class TreatmentProposal(BaseModel):
    """Treatment proposal sent by a doctor to a patient."""

    __tablename__ = "treatment_proposals"

    # Participants
    consultation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consultations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hospital_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Treatment details
    treatment_name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estimated_duration: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Proposed visit schedule
    proposed_visit_date: Mapped[Optional[datetime]] = mapped_column(
        Date, nullable=True
    )
    proposed_visit_time: Mapped[Optional[datetime]] = mapped_column(
        Time, nullable=True
    )

    # Cost breakdown (JSONB for flexibility)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    consultation_fee: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    surgery_fee: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    hospital_stay_fee: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    medications_fee: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    other_fees: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    other_fees_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Additional cost items (array of {label, amount})
    additional_costs: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Doctor's notes for patient
    doctor_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status: pending → approved / rejected / revision_requested
    status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False, index=True
    )

    # Patient response
    patient_response_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    responded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # DEPRECATED — proposals no longer require admin approval. Nothing reads or writes
    # these; they are kept only so existing rows are not lost. Drop in a migration once
    # any historical values have been exported or confirmed unneeded.
    admin_approved: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    admin_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    admin_reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    admin_reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Reference number
    reference_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Relationships
    consultation = relationship("Consultation", foreign_keys=[consultation_id], lazy="selectin")
    doctor = relationship("Doctor", foreign_keys=[doctor_id], lazy="selectin")
    patient = relationship("Patient", foreign_keys=[patient_id], lazy="selectin")
    hospital = relationship("Hospital", foreign_keys=[hospital_id], lazy="selectin")
