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
    city: str
    country: str
    star_rating: Optional[int] = None
    cover_image_url: Optional[str] = None
    rating: Optional[float] = None
    facilities: Optional[dict] = None
    policies: Optional[dict] = None
    min_price: Optional[float] = None  # Computed field

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
