"""Hospital model for medical facilities."""

import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.doctor import Doctor


class Hospital(BaseModel):
    """Hospital/Medical facility model."""

    __tablename__ = "hospitals"

    # Basic information
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    short_description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Contact information
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    website: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Location
    address_line1: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    address_line2: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    state: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    country: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    postal_code: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    latitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    longitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    # Media
    logo_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    cover_image_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    gallery: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Accreditation and ratings
    accreditations: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    rating: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    total_reviews: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Facilities
    facilities: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    specialties: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    languages_supported: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Operational
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Statistics
    total_doctors: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    total_patients_served: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # SEO
    meta_title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    meta_description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Relationships
    doctors: Mapped[List["Doctor"]] = relationship(
        "Doctor",
        back_populates="hospital",
        lazy="dynamic",
    )
    departments: Mapped[List["Department"]] = relationship(
        "Department",
        back_populates="hospital",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"Hospital(id={self.id}, name={self.name})"


class Department(BaseModel):
    """Hospital department model."""

    __tablename__ = "departments"

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    head_doctor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    icon: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Relationships
    hospital: Mapped["Hospital"] = relationship(
        "Hospital",
        back_populates="departments",
    )
