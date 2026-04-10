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
    cuisine_types: Optional[List[str]] = None

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

    # Hours
    opening_time: Optional[str] = None
    closing_time: Optional[str] = None
    operating_hours: Optional[dict] = None

    # Features & dietary
    features: Optional[List[str]] = None
    dietary_options: Optional[List[str]] = None
    accepts_medical_diets: bool = False

    # Pricing
    price_range: Optional[str] = None
    average_cost_per_person: Optional[float] = None
    currency: str = "USD"

    # Capacity
    seating_capacity: Optional[int] = None
    accepts_reservations: bool = True

    # Ratings
    rating: Optional[float] = None
    total_reviews: int = 0


class RestaurantMinimalResponse(BaseSchema):
    """Minimal restaurant response schema."""
    id: UUID
    name: str


class MenuItemResponse(BaseSchema):
    """Menu item response schema."""
    id: UUID
    restaurant_id: UUID
    category_id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    category: str
    price: float
    currency: str = "USD"
    image_url: Optional[str] = None
    is_vegetarian: bool = False
    is_vegan: bool = False
    is_gluten_free: bool = False
    allergens: Optional[List[str]] = None
    calories: Optional[int] = None
    suitable_for_diabetics: bool = False
    low_sodium: bool = False
    medical_diet_notes: Optional[str] = None
    is_available: bool = True
    is_featured: bool = False
    badge: Optional[str] = None
    tags: Optional[List[str]] = None
    available_for: Optional[List[str]] = None
    display_order: int = 0


class MenuCategoryWithItems(BaseSchema):
    """Menu category with its items."""
    id: UUID
    name: str
    description: Optional[str] = None
    display_order: int = 0
    items: List[MenuItemResponse] = []


class MenuCategoryResponse(BaseSchema):
    """Menu category response schema."""
    id: UUID
    restaurant_id: UUID
    name: str
    meal_type: Optional[str] = None
    description: Optional[str] = None
    display_order: int = 0


class DiningPassResponse(BaseSchema):
    """Dining pass response schema."""
    id: UUID
    restaurant_id: UUID
    name: str
    description: Optional[str] = None
    tokens: int
    duration_days: int
    price: float
    currency: str = "USD"
    is_active: bool = True
