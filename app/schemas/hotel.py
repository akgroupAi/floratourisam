    """Hotel schemas."""

from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field
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
