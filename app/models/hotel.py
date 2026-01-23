"""Hotel and room models for accommodation management."""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.utils.enums import RoomType


class Hotel(BaseModel):
    """Hotel model for accommodation partners."""

    __tablename__ = "hotels"

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

    # Star rating
    star_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Contact
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

    # Distance from hospitals
    distance_to_hospital_km: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    nearest_hospital: Mapped[Optional[str]] = mapped_column(
        String(255),
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

    # Amenities
    amenities: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    medical_amenities: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )  # Wheelchair access, medical staff on call, etc.

    # Pricing
    base_price_per_night: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
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

    # Status
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

    # Manager
    manager_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
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
    cancellation_policy: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    policies: Mapped[Optional[dict]] = mapped_column(
        JSONB,
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

    # Relationships
    rooms: Mapped[List["Room"]] = relationship(
        "Room",
        back_populates="hotel",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"Hotel(id={self.id}, name={self.name})"


class Room(BaseModel):
    """Room model for hotel rooms."""

    __tablename__ = "rooms"

    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hotels.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Basic info
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    room_type: Mapped[str] = mapped_column(
        String(50),
        default=RoomType.DOUBLE.value,
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Capacity
    max_occupancy: Mapped[int] = mapped_column(
        Integer,
        default=2,
        nullable=False,
    )
    bed_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    bed_count: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    # Dimensions
    size_sqm: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    # Amenities
    amenities: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    view: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Pricing
    price_per_night: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # Availability
    total_rooms: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Medical features
    wheelchair_accessible: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    medical_equipment_available: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Media
    images: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )

    # Relationships
    hotel: Mapped["Hotel"] = relationship(
        "Hotel",
        back_populates="rooms",
    )
    availability: Mapped[List["RoomAvailability"]] = relationship(
        "RoomAvailability",
        back_populates="room",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"Room(id={self.id}, name={self.name})"


class RoomAvailability(BaseModel):
    """Room availability for specific dates."""

    __tablename__ = "room_availability"

    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    available_rooms: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    is_blocked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Relationships
    room: Mapped["Room"] = relationship(
        "Room",
        back_populates="availability",
    )
