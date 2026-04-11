"""Apartment model for short-term accommodation management."""

import uuid
from typing import List, Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Apartment(BaseModel):
    """Apartment model for short-term rental listings."""

    __tablename__ = "apartments"

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

    # Type & Capacity
    bedroom_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="studio",
    )  # studio, 1BR, 2BR, 3BR, 4BR+
    property_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )  # Entire home, Private room, Shared room
    capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2,
    )
    bedrooms: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    beds: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    bathrooms: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    # Pricing
    price_per_night: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    price_per_week: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    price_per_month: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        nullable=False,
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
        index=True,
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

    # Contact
    phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Hospital proximity
    distance_to_hospital_km: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    nearest_hospital: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Amenities
    amenities: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )  # WiFi, AC, Kitchen, Washer, Dryer, Parking, Pool, Gym, TV, Workspace, Balcony, Elevator
    medical_amenities: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )  # Nurse on call, Physiotherapy, Medical equipment, Wheelchair access

    # Highlights / USPs (JSONB: [{icon, title, description}])
    highlights: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Policies
    check_in_time: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
    )
    check_out_time: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
    )
    house_rules: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
    )  # ["Children of all ages are welcome", "Pets are not allowed"]
    safety_features: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
    )  # ["Carbon monoxide alarm", "Smoke alarm", "Security cameras"]
    cancellation_policy: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Media
    cover_image_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    logo_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    gallery: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Nearby places (JSONB: [{name, distance_km, type}])
    nearby_places: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
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

    # Priority / display order
    priority: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Manager
    manager_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
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

    def __repr__(self) -> str:
        return f"Apartment(id={self.id}, name={self.name})"
