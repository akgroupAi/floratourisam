"""Booking schemas."""

from datetime import date, datetime, time
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import BaseSchema
from app.utils.enums import BookingStatus, BookingType, MealType


class BookingBase(BaseModel):
    """Base booking schema."""

    booking_type: BookingType
    special_requests: Optional[str] = Field(default=None, max_length=2000)
    notes: Optional[str] = Field(default=None, max_length=1000)


class HotelBookingCreate(BookingBase):
    """Hotel room booking."""

    room_id: UUID
    check_in_date: date
    check_out_date: date
    guest_count: int = Field(default=1, ge=1, le=10)
    guest_details: Optional[dict] = None

    def __init__(self, **data):
        data["booking_type"] = BookingType.HOTEL
        super().__init__(**data)


class ApartmentBookingCreate(BookingBase):
    """Apartment booking."""

    apartment_id: UUID
    check_in_date: date
    check_out_date: date
    guest_count: int = Field(default=1, ge=1, le=10)
    guest_details: Optional[dict] = None

    def __init__(self, **data):
        data["booking_type"] = BookingType.APARTMENT
        super().__init__(**data)


class OrderedItem(BaseModel):
    """A single menu item included in a restaurant booking."""

    item_id: UUID
    quantity: int = Field(default=1, ge=1)
    notes: Optional[str] = Field(default=None, max_length=200)


class RestaurantBookingCreate(BookingBase):
    """Restaurant table reservation with optional food pre-order."""

    restaurant_id: UUID
    booking_date: date
    booking_time: time
    meal_type: MealType = MealType.LUNCH
    guest_count: int = Field(default=1, ge=1, le=20)
    dietary_requirements: Optional[str] = Field(default=None, max_length=500)
    # Optional pre-ordered items; if provided, creates a MealBooking record
    ordered_items: Optional[List[OrderedItem]] = None
    contact_name: Optional[str] = Field(default=None, max_length=255)
    contact_phone: Optional[str] = Field(default=None, max_length=20)

    def __init__(self, **data):
        data["booking_type"] = BookingType.RESTAURANT
        super().__init__(**data)


class BookingUpdate(BaseModel):
    """Booking update schema."""

    special_requests: Optional[str] = Field(default=None, max_length=2000)
    guest_count: Optional[int] = Field(default=None, ge=1, le=20)
    notes: Optional[str] = Field(default=None, max_length=1000)


class BookingStatusUpdate(BaseModel):
    """Booking status update."""

    status: BookingStatus
    internal_notes: Optional[str] = None


class BookingCancelRequest(BaseModel):
    """Booking cancellation request."""

    cancellation_reason: str = Field(..., max_length=500)


class BookingListResponse(BaseSchema):
    """Booking list response."""

    id: UUID
    reference_number: str
    booking_type: str
    status: str
    status_label: Optional[str] = None
    booking_date: datetime
    check_in_date: Optional[date] = None
    check_out_date: Optional[date] = None
    scheduled_time: Optional[datetime] = None
    guest_count: int
    total_price: float
    currency: str
    is_paid: bool
    created_at: datetime

    entity_name: Optional[str] = None  # Hotel / Apartment / Restaurant name


class BookingResponse(BaseSchema):
    """Booking detail response."""

    id: UUID
    patient_id: UUID
    reference_number: str
    booking_type: str
    status: str

    # Related entities
    consultation_id: Optional[UUID] = None
    hotel_room_id: Optional[UUID] = None
    apartment_id: Optional[UUID] = None
    restaurant_id: Optional[UUID] = None

    # Dates
    booking_date: datetime
    check_in_date: Optional[date] = None
    check_out_date: Optional[date] = None
    scheduled_time: Optional[datetime] = None

    # Guest info
    guest_count: int
    guest_details: Optional[dict] = None

    # Pricing
    base_price: float
    taxes: float
    discount: float
    total_price: float
    currency: str
    discount_code: Optional[str] = None
    price_per_night: Optional[float] = None
    nights: Optional[int] = None

    # Payment
    payment_id: Optional[UUID] = None
    is_paid: bool
    paid_at: Optional[datetime] = None

    # Requests
    special_requests: Optional[str] = None
    notes: Optional[str] = None

    # Confirmation
    confirmed_at: Optional[datetime] = None

    # Cancellation
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    refund_amount: Optional[float] = None

    # Check-in/out
    actual_check_in: Optional[datetime] = None
    actual_check_out: Optional[datetime] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # Related entity info
    entity_name: Optional[str] = None
    entity_address: Optional[str] = None

    booking_metadata: Optional[dict] = None

    @model_validator(mode="before")
    @classmethod
    def extract_pricing_from_metadata(cls, data):
        """Pull price_per_night and nights from booking_metadata if present."""
        metadata = None
        if hasattr(data, "booking_metadata"):
            metadata = data.booking_metadata
        elif isinstance(data, dict):
            metadata = data.get("booking_metadata")
        if metadata and isinstance(metadata, dict):
            if isinstance(data, dict):
                data.setdefault("price_per_night", metadata.get("price_per_night"))
                data.setdefault("nights", metadata.get("nights"))
            else:
                if not getattr(data, "price_per_night", None):
                    try:
                        data.price_per_night = metadata.get("price_per_night")
                    except Exception:
                        pass
                if not getattr(data, "nights", None):
                    try:
                        data.nights = metadata.get("nights")
                    except Exception:
                        pass
        return data


class PriceCalculationRequest(BaseModel):
    """Request body for price calculation preview."""

    booking_type: BookingType = Field(..., description="hotel or apartment")
    room_id: Optional[UUID] = Field(default=None, description="Required for hotel bookings")
    apartment_id: Optional[UUID] = Field(default=None, description="Required for apartment bookings")
    check_in_date: date
    check_out_date: date
    guest_count: int = Field(default=1, ge=1, le=10)


class PriceCalculationResponse(BaseModel):
    """Price breakdown returned by the calculator."""

    booking_type: str
    nights: int
    pricing_tier: Optional[str] = Field(default=None, description="monthly, weekly, or nightly (apartments only)")
    rate_used: float = Field(..., description="Per-unit rate applied")
    base_price: float
    taxes: float
    total_price: float
    currency: str
    entity_name: Optional[str] = None
    guest_count: int


class BookingStatsResponse(BaseModel):
    """Booking statistics."""

    total_bookings: int
    confirmed_bookings: int
    cancelled_bookings: int
    pending_bookings: int
    total_revenue: float
    bookings_by_type: dict[str, int]
    bookings_by_status: dict[str, int]


# Admin Booking Management Schemas

class AdminBookingKPIs(BaseModel):
    total_bookings: int
    active_confirmed: int
    pending_approval: int
    collected_revenue: float


class AdminBookingListItem(BookingListResponse):
    patient_name: str
    patient_email: Optional[str]
    property_name: Optional[str]
    room_name: Optional[str]


class AdminBookingDashboardResponse(BaseModel):
    kpis: AdminBookingKPIs
    bookings: List[AdminBookingListItem]
    total_count: int
    page: int
    page_size: int


class BookingTimelineItem(BaseModel):
    status: str
    description: str
    timestamp: datetime
    actor_name: Optional[str] = None


class AdminBookingDetailResponse(BookingResponse):
    patient_name: str
    patient_email: Optional[str]
    patient_phone: Optional[str]
    property_name: Optional[str]
    room_name: Optional[str]
    room_no: Optional[str] = None
    timeline: List[BookingTimelineItem] = []
    payment_progress: float = 0.0
    paid_amount: float = 0.0
    balance_amount: float = 0.0


class AdminBookingUpdate(BaseModel):
    check_in_date: Optional[date] = None
    check_out_date: Optional[date] = None
    guest_count: Optional[int] = Field(default=None, ge=1, le=20)
    status: Optional[BookingStatus] = None
    special_requests: Optional[str] = None
    notes: Optional[str] = None
    internal_notes: Optional[str] = None
    reference_number: Optional[str] = None


class KPITrend(BaseModel):
    date: date
    value: float


class PropertyBooking(BaseModel):
    name: str
    count: int
    percentage: float


class BookingReportSummary(BaseModel):
    total_bookings: int
    total_revenue: float
    occupancy_rate: float
    cancellation_rate: float
    bookings_trend: List[KPITrend]
    revenue_trend: List[KPITrend]
    bookings_by_property: List[PropertyBooking]

