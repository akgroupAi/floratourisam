"""Patient model for medical tourism patients."""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.utils.enums import BloodGroup, Gender

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.consultation import Consultation
    from app.models.booking import Booking


class Patient(BaseModel):
    """Patient profile with medical information."""

    __tablename__ = "patients"

    # Link to user
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # Personal information
    date_of_birth: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    gender: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    nationality: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    passport_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    passport_expiry: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )

    # Address
    address_line1: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    address_line2: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    city: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    state: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    country: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    postal_code: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    # Medical information
    blood_group: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
    )
    height_cm: Mapped[Optional[float]] = mapped_column(
        nullable=True,
    )
    weight_kg: Mapped[Optional[float]] = mapped_column(
        nullable=True,
    )
    allergies: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    chronic_conditions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    current_medications: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    medical_history: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )

    # Emergency contact
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    emergency_contact_relation: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Insurance
    insurance_provider: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    insurance_policy_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    insurance_details: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Preferences
    preferred_language: Mapped[Optional[str]] = mapped_column(
        String(10),
        default="en",
        nullable=True,
    )
    preferences: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="patient_profile",
        foreign_keys=[user_id],
    )
    consultations: Mapped[List["Consultation"]] = relationship(
        "Consultation",
        back_populates="patient",
        lazy="dynamic",
    )
    bookings: Mapped[List["Booking"]] = relationship(
        "Booking",
        back_populates="patient",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"Patient(id={self.id}, user_id={self.user_id})"

    @property
    def age(self) -> Optional[int]:
        """Calculate patient's age from date of birth."""
        if self.date_of_birth:
            today = date.today()
            age = today.year - self.date_of_birth.year
            if (today.month, today.day) < (
                self.date_of_birth.month,
                self.date_of_birth.day,
            ):
                age -= 1
            return age
        return None

    @property
    def bmi(self) -> Optional[float]:
        """Calculate BMI from height and weight."""
        if self.height_cm and self.weight_kg and self.height_cm > 0:
            height_m = self.height_cm / 100
            return round(self.weight_kg / (height_m * height_m), 2)
        return None
