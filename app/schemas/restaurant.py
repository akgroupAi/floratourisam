"""Restaurant schemas."""

from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from app.schemas.common import BaseSchema

class RestaurantResponse(BaseSchema):
    """Restaurant response schema."""
    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    city: str
    country: str
    cuisine_types: Optional[List[str]] = None
    cover_image_url: Optional[str] = None
    rating: Optional[float] = None
    price_range: Optional[str] = None

class MenuItemResponse(BaseSchema):
    """Menu item response schema."""
    id: UUID
    restaurant_id: UUID
    name: str
    description: Optional[str] = None
    category: str
    price: float
    image_url: Optional[str] = None
    is_vegetarian: bool = False
    is_vegan: bool = False
    is_gluten_free: bool = False
    calories: Optional[int] = None
