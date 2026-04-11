"""Apartment schemas."""

from typing import Any, List, Optional
from uuid import UUID

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
