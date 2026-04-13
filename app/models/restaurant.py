"""Restaurant and menu models for dining management."""

import uuid
from datetime import date, datetime, time
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, Time
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, SimpleBaseModel
from app.utils.enums import MealType


class Restaurant(BaseModel):
    """Restaurant model for dining partners."""

    __tablename__ = "restaurants"

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
    cuisine_types: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
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

    # Operating hours
    opening_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )
    closing_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )
    operating_hours: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )  # Day-wise hours

    # Features
    features: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )  # Outdoor seating, WiFi, etc.
    dietary_options: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )  # Vegetarian, Vegan, Halal, Kosher, etc.
    accepts_medical_diets: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Pricing
    price_range: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
    )  # $, $$, $$$, $$$$
    average_cost_per_person: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        nullable=False,
    )

    # Distance from hospital
    distance_to_hospital_km: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    nearest_hospital: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Capacity
    seating_capacity: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    accepts_reservations: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
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

    # Relationships
    menu_items: Mapped[List["MenuItem"]] = relationship(
        "MenuItem",
        back_populates="restaurant",
        lazy="dynamic",
    )
    meal_bookings: Mapped[List["MealBooking"]] = relationship(
        "MealBooking",
        back_populates="restaurant",
        lazy="dynamic",
    )
    menu_categories: Mapped[List["MenuCategory"]] = relationship(
        "MenuCategory",
        back_populates="restaurant",
        lazy="dynamic",
    )
    thalis: Mapped[List["Thali"]] = relationship(
        "Thali",
        back_populates="restaurant",
        lazy="dynamic",
    )
    dining_passes: Mapped[List["DiningPass"]] = relationship(
        "DiningPass",
        back_populates="restaurant",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"Restaurant(id={self.id}, name={self.name})"


class MenuItem(BaseModel):
    """Menu item model."""

    __tablename__ = "menu_items"

    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("restaurants.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Category FK (optional – links to MenuCategory)
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("menu_categories.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Basic info
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )  # Appetizer, Main, Dessert, etc.

    # Pricing
    price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # Media
    image_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Dietary info
    calories: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    is_vegetarian: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_vegan: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_gluten_free: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    allergens: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    nutritional_info: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Medical diet compatibility
    suitable_for_diabetics: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    low_sodium: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    medical_diet_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Availability
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    available_for: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )  # breakfast, lunch, dinner
    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    badge: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )  # Legendary, Popular, Chef's Pick, Must Try, Spicy, Premium
    tags: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )  # Additional tags for filtering
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        nullable=False,
    )

    # Relationships
    restaurant: Mapped["Restaurant"] = relationship(
        "Restaurant",
        back_populates="menu_items",
    )
    category_obj: Mapped[Optional["MenuCategory"]] = relationship(
        "MenuCategory",
        back_populates="menu_items",
        foreign_keys=[category_id],
    )

    def __repr__(self) -> str:
        return f"MenuItem(id={self.id}, name={self.name})"


class MealBooking(BaseModel):
    """Meal booking for restaurant reservations."""

    __tablename__ = "meal_bookings"

    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("restaurants.id", ondelete="CASCADE"),
        nullable=False,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
    )
    booking_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Booking details
    meal_type: Mapped[str] = mapped_column(
        String(20),
        default=MealType.LUNCH.value,
        nullable=False,
    )
    booking_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    booking_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )
    guest_count: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    # Menu items
    selected_items: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    special_requests: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    dietary_requirements: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Pricing
    estimated_cost: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
    )
    confirmation_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    # Contact
    contact_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    contact_phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # Relationships
    restaurant: Mapped["Restaurant"] = relationship(
        "Restaurant",
        back_populates="meal_bookings",
    )


class MenuCategory(BaseModel):
    """Menu category for grouping menu items within a restaurant."""

    __tablename__ = "menu_categories"

    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("restaurants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    meal_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    restaurant: Mapped["Restaurant"] = relationship(
        "Restaurant",
        back_populates="menu_categories",
    )
    menu_items: Mapped[List["MenuItem"]] = relationship(
        "MenuItem",
        back_populates="category_obj",
        foreign_keys="MenuItem.category_id",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"MenuCategory(id={self.id}, name={self.name})"


class Thali(BaseModel):
    """Thali – a fixed meal set containing multiple menu items."""

    __tablename__ = "thalis"

    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("restaurants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    image_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    # List of menu item UUIDs included in this thali
    menu_item_ids: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
    )
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Relationships
    restaurant: Mapped["Restaurant"] = relationship(
        "Restaurant",
        back_populates="thalis",
    )

    def __repr__(self) -> str:
        return f"Thali(id={self.id}, name={self.name})"


class DiningPass(BaseModel):
    """Dining pass for restaurant meal packages."""

    __tablename__ = "dining_passes"

    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("restaurants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    duration_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    available_from: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    available_until: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    meals_per_day: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Relationships
    restaurant: Mapped["Restaurant"] = relationship(
        "Restaurant",
        back_populates="dining_passes",
    )
    purchases: Mapped[List["DiningPassPurchase"]] = relationship(
        "DiningPassPurchase",
        back_populates="dining_pass",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"DiningPass(id={self.id}, name={self.name})"


class DiningPassPurchase(BaseModel):
    """Record of a purchased dining pass."""

    __tablename__ = "dining_pass_purchases"

    dining_pass_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dining_passes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("restaurants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Pass details (snapshot at purchase time)
    pass_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    reference_code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    # Token tracking
    tokens_total: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    tokens_used: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Validity
    purchased_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Pricing
    amount_paid: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        nullable=False,
    )

    # Status: pending, active, expired, fully_used, cancelled
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
    )

    # Linked booking for payment tracking
    booking_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    dining_pass: Mapped["DiningPass"] = relationship(
        "DiningPass",
        back_populates="purchases",
    )
    restaurant: Mapped["Restaurant"] = relationship(
        "Restaurant",
        foreign_keys=[restaurant_id],
    )

    def __repr__(self) -> str:
        return f"DiningPassPurchase(id={self.id}, ref={self.reference_code})"
