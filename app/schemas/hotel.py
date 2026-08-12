"""Hotel schemas."""

from datetime import date as _date
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
from app.schemas.common import BaseSchema

class HotelResponse(BaseSchema):
    """Hotel response schema."""
    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    star_rating: Optional[int] = None

    # Contact
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None

    # Location
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: str
    state: Optional[str] = None
    country: str
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_to_hospital_km: Optional[float] = None
    nearest_hospital: Optional[str] = None

    # Media
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    gallery: Optional[List[str]] = None

    # Amenities
    amenities: Optional[List[str]] = None
    medical_amenities: Optional[List[str]] = None

    # Pricing
    base_price_per_night: Optional[float] = None
    currency: str = "USD"

    # Ratings
    rating: Optional[float] = None
    total_reviews: int = 0

    # Policies
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    cancellation_policy: Optional[str] = None
    facilities: Optional[dict] = None
    policies: Optional[dict] = None

    # Status
    is_featured: bool = False

class RoomResponse(BaseSchema):
    """Room response schema."""
    id: UUID
    hotel_id: UUID
    name: Optional[str] = None
    room_number: Optional[str] = None
    room_type: str
    description: Optional[str] = None
    max_occupancy: int
    bed_type: Optional[str] = None
    bed_count: int = 1
    size_sqm: Optional[float] = None
    amenities: Optional[List[str]] = None
    highlights: Optional[List[str]] = None
    view: Optional[dict] = None
    price_per_night: float
    total_rooms: int = 1
    is_available: bool = True
    wheelchair_accessible: bool = False
    medical_equipment_available: bool = False
    images: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Rate & availability calendar
# ---------------------------------------------------------------------------

class RoomCalendarDay(BaseModel):
    """One night of a room type's calendar."""

    date: _date
    price: float
    available_rooms: int = Field(..., description="Units on sale that night")
    booked_rooms: int = Field(..., description="Units already taken")
    remaining_rooms: int = Field(..., description="available_rooms minus booked_rooms")
    is_blocked: bool
    notes: Optional[str] = None
    has_override: bool = Field(
        ..., description="False means this night falls back to the room's defaults"
    )


class RoomCalendarUpdate(BaseModel):
    """Set price, inventory, or a block across a date range.

    Only the fields you send are changed. `end_date` is exclusive, matching how nights
    work: 1–3 June is two nights, the 1st and the 2nd.
    """

    start_date: _date
    end_date: _date = Field(..., description="Exclusive — the first night NOT included")
    price: Optional[float] = Field(None, ge=0)
    available_rooms: Optional[int] = Field(None, ge=0)
    is_blocked: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=500)
    weekdays: Optional[List[int]] = Field(
        None,
        description="Restrict to these weekdays (0=Monday .. 6=Sunday), e.g. [4,5] for Fri+Sat",
    )

    @field_validator("weekdays")
    @classmethod
    def _valid_weekdays(cls, value):
        if value is not None and (not value or any(d < 0 or d > 6 for d in value)):
            raise ValueError("weekdays must be a non-empty list of 0-6 (0=Monday)")
        return value


class RoomCalendarUpdateResponse(BaseModel):
    """Result of a calendar write."""

    room_id: UUID
    days_updated: int
    start_date: _date
    end_date: _date
