"""Booking schemas."""

from datetime import date, datetime, time
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, computed_field

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

    @computed_field
    @property
    def nights(self) -> Optional[int]:
        """Calculate number of nights for hotel/apartment bookings."""
        if self.check_in_date and self.check_out_date:
            return (self.check_out_date - self.check_in_date).days
        return None


class BookingStatsResponse(BaseModel):
    """Booking statistics."""

    total_bookings: int
    confirmed_bookings: int
    cancelled_bookings: int
    pending_bookings: int
    total_revenue: float
    bookings_by_type: dict[str, int]
    bookings_by_status: dict[str, int]

