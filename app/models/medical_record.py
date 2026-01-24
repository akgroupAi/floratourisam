"""Medical record models for patient health information."""

import uuid
from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, ForeignKey, String, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.patient import Patient


class MedicalCondition(BaseModel):
    """Patient medical condition model."""

    __tablename__ = "medical_conditions"

    # Foreign key
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Condition details
    condition_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    diagnosed_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Active",
    )  # Active, Managed, Controlled, Resolved
    severity: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )  # Mild, Moderate, Severe
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"MedicalCondition(id={self.id}, condition={self.condition_name})"


class Allergy(BaseModel):
    """Patient allergy model."""

    __tablename__ = "allergies"

    # Foreign key
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Allergy details
    allergen: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    reaction: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )  # Rash, Anaphylaxis, etc.
    severity: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Moderate",
    )  # Mild, Moderate, Severe
    diagnosed_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"Allergy(id={self.id}, allergen={self.allergen})"


class Medication(BaseModel):
    """Patient medication model."""

    __tablename__ = "medications"

    # Foreign key
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Medication details
    medication_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    dosage: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    frequency: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )  # Once daily, Twice daily, etc.
    duration: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )  # Ongoing, 2 weeks, etc.
    start_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    end_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    prescribing_doctor: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    def __repr__(self) -> str:
        return f"Medication(id={self.id}, name={self.medication_name})"
