"""Apartment schemas."""

from datetime import date as _date
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import BaseSchema


class ApartmentResponse(BaseSchema):
    """Apartment response schema."""

    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    short_description: Optional[str] = None

    # Type & Capacity
    bedroom_type: str
    property_type: Optional[str] = None
    capacity: int
    bedrooms: int = 1
    beds: int = 1
    bathrooms: int = 1

    # Pricing
    price_per_night: Optional[float] = None
    price_per_week: Optional[float] = None
    price_per_month: Optional[float] = None
    currency: str = "USD"

    # Location
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: Optional[str] = None
    country: str
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Contact
    phone: Optional[str] = None
    email: Optional[str] = None

    # Hospital proximity
    distance_to_hospital_km: Optional[float] = None
    nearest_hospital: Optional[str] = None

    # Amenities
    amenities: Optional[List[str]] = None
    medical_amenities: Optional[List[str]] = None

    # Highlights / USPs [{icon, title, description}]
    highlights: Optional[List[Any]] = None

    # Media
    cover_image_url: Optional[str] = None
    logo_url: Optional[str] = None
    gallery: Optional[List[str]] = None

    # Nearby
    nearby_places: Optional[Any] = None

    # Ratings
    rating: Optional[float] = None
    total_reviews: int = 0

    # Policies
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    house_rules: Optional[List[Any]] = None
    safety_features: Optional[List[Any]] = None
    cancellation_policy: Optional[str] = None

    # Status
    is_available: bool = True
    is_featured: bool = False

    # SEO
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None


# ---------------------------------------------------------------------------
# Rate & availability calendar
# ---------------------------------------------------------------------------

class ApartmentCalendarDay(BaseModel):
    """One night of an apartment's calendar."""

    date: _date
    price: Optional[float] = None
    minimum_nights: int
    is_blocked: bool
    is_booked: bool = Field(..., description="Taken by a confirmed booking")
    notes: Optional[str] = None
    has_override: bool = Field(
        ..., description="False means this night falls back to the apartment's defaults"
    )


class ApartmentCalendarUpdate(BaseModel):
    """Set price, minimum stay, or a block across a date range.

    Only the fields you send are changed. `end_date` is exclusive.
    """

    start_date: _date
    end_date: _date = Field(..., description="Exclusive — the first night NOT included")
    price: Optional[float] = Field(None, ge=0)
    is_blocked: Optional[bool] = None
    minimum_nights: Optional[int] = Field(None, ge=1)
    notes: Optional[str] = Field(None, max_length=500)
    weekdays: Optional[List[int]] = Field(
        None, description="Restrict to these weekdays (0=Monday .. 6=Sunday)"
    )

    @field_validator("weekdays")
    @classmethod
    def _valid_weekdays(cls, value):
        if value is not None and (not value or any(d < 0 or d > 6 for d in value)):
            raise ValueError("weekdays must be a non-empty list of 0-6 (0=Monday)")
        return value


class ApartmentCalendarUpdateResponse(BaseModel):
    """Result of a calendar write."""

    apartment_id: UUID
    days_updated: int
    start_date: _date
    end_date: _date
