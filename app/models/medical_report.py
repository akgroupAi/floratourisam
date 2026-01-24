"""Medical report model for patient records."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.doctor import Doctor
    from app.models.consultation import Consultation


class MedicalReport(BaseModel):
    """Medical report/document model."""

    __tablename__ = "medical_reports"

    # Ownership
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doctor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="SET NULL"),
        nullable=True,
    )
    consultation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consultations.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Report information
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    report_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )  # lab_result, imaging, prescription, etc.
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # File information
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
        nullable=True,
    )

    # Report content
    content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    structured_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Report date
    report_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Lab/facility information
    facility_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    facility_address: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    performing_doctor: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Interpretation
    interpretation: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    is_abnormal: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    requires_followup: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )

    # Access control
    is_private: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    shared_with: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Reference
    reference_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Relationships
    consultation: Mapped[Optional["Consultation"]] = relationship(
        "Consultation",
        back_populates="medical_reports",
    )

    def __repr__(self) -> str:
        return f"MedicalReport(id={self.id}, title={self.title})"
