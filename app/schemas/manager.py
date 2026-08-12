"""Manager portal schemas."""

from datetime import date as _date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BaseSchema


class ManagerPropertySummary(BaseModel):
    """One property a manager is responsible for."""

    id: UUID
    name: str
    city: Optional[str] = None
    country: Optional[str] = None
    is_active: bool = True
    rating: Optional[float] = None
    image_url: Optional[str] = None


class ManagerPropertiesResponse(BaseModel):
    """Everything the caller manages, grouped by type."""

    role: str
    hotels: List[ManagerPropertySummary] = []
    apartments: List[ManagerPropertySummary] = []
    restaurants: List[ManagerPropertySummary] = []
    total: int = 0


class ManagerDashboardResponse(BaseModel):
    """Today at the manager's properties."""

    date: _date
    arrivals_today: int
    departures_today: int
    in_house: int = Field(..., description="Guests currently staying")
    pending_bookings: int
    unpaid_bookings: int
    cancellations_last_7d: int
    revenue_today: float
    revenue_this_month: float
    property_count: int


class ManagerBookingItem(BaseSchema):
    """A booking at one of the manager's properties."""

    id: UUID
    reference_number: str
    booking_type: str
    status: str
    booking_date: Optional[datetime] = None
    check_in_date: Optional[_date] = None
    check_out_date: Optional[_date] = None
    scheduled_time: Optional[datetime] = None
    guest_count: Optional[int] = None
    guest_details: Optional[dict] = None
    base_price: float = 0.0
    platform_fee: float = 0.0
    total_price: float = 0.0
    currency: Optional[str] = None
    is_paid: bool = False
    special_requests: Optional[str] = None
    cancellation_reason: Optional[str] = None
    created_at: datetime


class ManagerReviewItem(BaseSchema):
    """A review of one of the manager's properties."""

    id: UUID
    entity_type: str
    entity_id: UUID
    rating: int
    title: Optional[str] = None
    body: Optional[str] = None
    is_approved: bool = False
    response_text: Optional[str] = None
    response_date: Optional[datetime] = None
    created_at: datetime


class ReviewResponseRequest(BaseModel):
    """A manager's public reply to a review."""

    response_text: str = Field(..., min_length=1, max_length=2000)


class ManagerMenuItem(BaseModel):
    """A menu item with today's stock resolved."""

    id: UUID
    restaurant_id: UUID
    name: str
    category: Optional[str] = None
    price: float
    currency: Optional[str] = None
    is_available: bool = Field(..., description="Permanent on/off switch")
    available_for: List[str] = []
    daily_quantity: Optional[int] = Field(None, description="null = unlimited")
    sold_today: int = 0
    remaining_today: Optional[int] = Field(None, description="null = unlimited")
    is_sold_out: bool = False
    image_url: Optional[str] = None


class MenuStockUpdate(BaseModel):
    """Set today's stock for a menu item.

    `unlimited` clears the quantity; `reset` puts the sold counter back to zero.
    """

    daily_quantity: Optional[int] = Field(None, ge=0)
    unlimited: bool = Field(False, description="Clear daily_quantity — no limit")
    sold_today: Optional[int] = Field(None, ge=0)
    is_available: Optional[bool] = None
    reset: bool = Field(False, description="Restocked — set sold_today back to 0")
