"""Doctor model for medical professionals."""

import uuid
from datetime import date, datetime, time
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.hospital import Hospital
    from app.models.consultation import Consultation


class Doctor(BaseModel):
    """Doctor profile with qualifications and availability."""

    __tablename__ = "doctors"

    # Link to user
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # Link to hospital
    hospital_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Professional information
    title: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )  # Dr., Prof., etc.
    license_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        unique=True,
        nullable=True,
    )
    license_expiry: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    years_of_experience: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Qualifications
    qualifications: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    education: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    certifications: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Bio and description
    bio: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    languages_spoken: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Consultation settings
    consultation_fee: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    consultation_duration_minutes: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
    )
    video_consultation_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    chat_consultation_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    in_person_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Ratings
    rating: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    total_reviews: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    total_consultations: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Verification
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    verification_date: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="doctor_profile",
        foreign_keys=[user_id],
    )
    hospital: Mapped[Optional["Hospital"]] = relationship(
        "Hospital",
        back_populates="doctors",
    )
    specializations: Mapped[List["DoctorSpecialization"]] = relationship(
        "DoctorSpecialization",
        back_populates="doctor",
        lazy="selectin",
    )
    availability: Mapped[List["DoctorAvailability"]] = relationship(
        "DoctorAvailability",
        back_populates="doctor",
        lazy="selectin",
    )
    consultations: Mapped[List["Consultation"]] = relationship(
        "Consultation",
        back_populates="doctor",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"Doctor(id={self.id}, license={self.license_number})"


class DoctorSpecialization(BaseModel):
    """Doctor specialization mapping."""

    __tablename__ = "doctor_specializations"

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
    )
    specialization: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    certification: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Relationships
    doctor: Mapped["Doctor"] = relationship(
        "Doctor",
        back_populates="specializations",
    )


class DoctorAvailability(BaseModel):
    """Doctor availability schedule."""

    __tablename__ = "doctor_availability"

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
    )
    day_of_week: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )  # 0=Monday, 6=Sunday
    start_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )
    end_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    slot_duration_minutes: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
    )
    max_appointments: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    break_start_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )
    break_end_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )

    # Relationships
    doctor: Mapped["Doctor"] = relationship(
        "Doctor",
        back_populates="availability",
    )
