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
    min_price: Optional[float] = None  # Computed field

class RoomResponse(BaseSchema):
    """Room response schema."""
    id: UUID
    hotel_id: UUID
    name: str
    room_type: str
    description: Optional[str] = None
    max_occupancy: int
    price_per_night: float
    is_available: bool = True
    images: Optional[List[str]] = None
