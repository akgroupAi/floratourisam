"""Booking endpoints.

Patient-facing booking flows:
  Hotel      → POST /bookings/hotel       (book room)
  Apartment  → POST /bookings/apartment   (book apartment)
  Restaurant → POST /bookings/restaurant  (reserve table + optional food pre-order)
  My list    → GET  /bookings/me
  Detail     → GET  /bookings/{id}
  Cancel     → POST /bookings/{id}/cancel
  Availability check → GET /bookings/rooms/{room_id}/availability
"""

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DatabaseSession
from app.core.logging import get_logger
from app.models.hotel import Hotel, Room
from app.models.apartment import Apartment
from app.schemas.booking import (
    ApartmentBookingCreate,
    BookingCancelRequest,
    BookingListResponse,
    BookingResponse,
    HotelBookingCreate,
    PriceCalculationRequest,
    PriceCalculationResponse,
    RestaurantBookingCreate,
)
from app.schemas.common import PaginatedResponse, PaginationParams
from app.services.booking_service import BookingService
from app.services.patient_service import PatientService

logger = get_logger(__name__)
from app.utils.enums import BookingType

router = APIRouter()


@router.get(
    "/rooms/{room_id}/availability",
    summary="Check hotel room availability",
    description="Returns whether a room is available for the given date range.",
)
async def check_room_availability(
    room_id: UUID,
    db: DatabaseSession,
    check_in: date = Query(..., description="Check-in date (YYYY-MM-DD)"),
    check_out: date = Query(..., description="Check-out date (YYYY-MM-DD)"),
):
    if check_out <= check_in:
        raise HTTPException(status_code=400, detail="check_out must be after check_in")
    service = BookingService(db)
    available = await service.check_room_availability(room_id, check_in, check_out)
    nights = (check_out - check_in).days
    return {"room_id": room_id, "check_in": check_in, "check_out": check_out, "nights": nights, "available": available}


@router.get(
    "/apartments/{apartment_id}/availability",
    summary="Check apartment availability",
    description="Returns whether an apartment is available for the given date range.",
)
async def check_apartment_availability(
    apartment_id: UUID,
    db: DatabaseSession,
    check_in: date = Query(..., description="Check-in date (YYYY-MM-DD)"),
    check_out: date = Query(..., description="Check-out date (YYYY-MM-DD)"),
):
    if check_out <= check_in:
        raise HTTPException(status_code=400, detail="check_out must be after check_in")
    service = BookingService(db)
    available = await service.check_apartment_availability(apartment_id, check_in, check_out)
    nights = (check_out - check_in).days
    return {"apartment_id": apartment_id, "check_in": check_in, "check_out": check_out, "nights": nights, "available": available}


@router.post(
    "/hotel",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Book a hotel room",
    description=(
        "Books a hotel room for the patient. Validates date-range availability against "
        "RoomAvailability and existing confirmed bookings. "
        "Creates a pending booking; inventory is reserved and confirmation is sent only after payment verification."
    ),
)
async def create_hotel_booking(
    data: HotelBookingCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    if data.check_out_date <= data.check_in_date:
        raise HTTPException(status_code=400, detail="check_out_date must be after check_in_date")

    patient_service = PatientService(db)
    patient = await patient_service.get_or_create(current_user.id)

    service = BookingService(db)
    try:
        return await service.create_hotel_booking(
            patient_id=patient.id,
            data=data,
            created_by=current_user.id,
            user=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/apartment",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Book an apartment",
    description=(
        "Books an apartment for the patient. "
        "Price uses monthly rate (≥28 nights), weekly rate (≥7 nights), or nightly rate. "
        "Creates a pending booking; confirmation is sent only after payment verification."
    ),
)
async def create_apartment_booking(
    data: ApartmentBookingCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    if data.check_out_date <= data.check_in_date:
        raise HTTPException(status_code=400, detail="check_out_date must be after check_in_date")

    patient_service = PatientService(db)
    patient = await patient_service.get_or_create(current_user.id)

    service = BookingService(db)
    try:
        booking = await service.create_apartment_booking(
            patient_id=patient.id,
            data=data,
            created_by=current_user.id,
            user=current_user,
        )
        return booking
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error("apartment_booking_error", error=str(exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create apartment booking. Please try again.",
        )



@router.post(
    "/restaurant",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reserve a restaurant table",
    description=(
        "Reserves a table and optionally pre-orders food items. "
        "If `ordered_items` is provided, a MealBooking record is created with per-item pricing "
        "and the booking total is calculated (5% service charge). "
        "Confirmation email sent immediately."
    ),
)
async def create_restaurant_booking(
    data: RestaurantBookingCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    patient_service = PatientService(db)
    patient = await patient_service.get_or_create(current_user.id)

    service = BookingService(db)
    try:
        return await service.create_restaurant_booking(
            patient_id=patient.id,
            data=data,
            created_by=current_user.id,
            user=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/calculate-price",
    response_model=PriceCalculationResponse,
    summary="Calculate booking price",
    description=(
        "Returns a price breakdown for a hotel room or apartment based on "
        "dates and guest count. No booking is created."
    ),
)
async def calculate_price(
    data: PriceCalculationRequest,
    db: DatabaseSession,
):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    if data.check_out_date <= data.check_in_date:
        raise HTTPException(status_code=400, detail="check_out_date must be after check_in_date")

    nights = max((data.check_out_date - data.check_in_date).days, 1)

    if data.booking_type == BookingType.HOTEL:
        if not data.room_id:
            raise HTTPException(status_code=400, detail="room_id is required for hotel bookings")
        result = await db.execute(
            select(Room).options(selectinload(Room.hotel)).where(Room.id == data.room_id, Room.is_deleted == False)
        )
        room = result.scalar_one_or_none()
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")

        base_price = round(room.price_per_night * nights, 2)
        taxes = round(base_price * 0.10, 2)
        total_price = base_price + taxes
        currency = room.hotel.currency if room.hotel else "USD"
        entity_name = room.hotel.name if room.hotel else None

        return PriceCalculationResponse(
            booking_type="hotel",
            nights=nights,
            pricing_tier=None,
            rate_used=room.price_per_night,
            base_price=base_price,
            taxes=taxes,
            total_price=total_price,
            currency=currency,
            entity_name=entity_name,
            guest_count=data.guest_count,
        )

    elif data.booking_type == BookingType.APARTMENT:
        if not data.apartment_id:
            raise HTTPException(status_code=400, detail="apartment_id is required for apartment bookings")
        result = await db.execute(
            select(Apartment).where(Apartment.id == data.apartment_id, Apartment.is_deleted == False)
        )
        apartment = result.scalar_one_or_none()
        if not apartment:
            raise HTTPException(status_code=404, detail="Apartment not found")

        if nights >= 28 and apartment.price_per_month:
            months = nights / 30
            base_price = round(apartment.price_per_month * months, 2)
            tier = "monthly"
            rate_used = apartment.price_per_month
        elif nights >= 7 and apartment.price_per_week:
            weeks = nights / 7
            base_price = round(apartment.price_per_week * weeks, 2)
            tier = "weekly"
            rate_used = apartment.price_per_week
        elif apartment.price_per_night:
            base_price = round(apartment.price_per_night * nights, 2)
            tier = "nightly"
            rate_used = apartment.price_per_night
        else:
            raise HTTPException(status_code=400, detail="Apartment has no pricing configured")

        total_price = base_price

        return PriceCalculationResponse(
            booking_type="apartment",
            nights=nights,
            pricing_tier=tier,
            rate_used=rate_used,
            base_price=base_price,
            taxes=0,
            total_price=total_price,
            currency=apartment.currency,
            entity_name=apartment.name,
            guest_count=data.guest_count,
        )

    else:
        raise HTTPException(status_code=400, detail="Price calculation is only supported for hotel and apartment bookings")


@router.get(
    "/me",
    response_model=PaginatedResponse[BookingListResponse],
    summary="List my bookings",
    description="Returns the authenticated patient's bookings, newest first.",
)
async def list_my_bookings(
    current_user: CurrentUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    booking_type: Optional[BookingType] = Query(default=None, description="Filter: hotel | apartment | restaurant | consultation"),
    booking_status: Optional[str] = Query(default=None, alias="status"),
):
    patient_service = PatientService(db)
    patient = await patient_service.get_by_user_id(current_user.id)
    if not patient:
        return PaginatedResponse.create([], 0, page, page_size)

    from app.utils.enums import BookingStatus as BS
    status_enum = None
    if booking_status:
        try:
            status_enum = BS(booking_status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {booking_status}")

    service = BookingService(db)
    bookings, total = await service.get_list(
        PaginationParams(page=page, page_size=page_size),
        patient_id=patient.id,
        booking_type=booking_type,
        status=status_enum,
    )
    return PaginatedResponse.create(bookings, total, page, page_size)


@router.get(
    "/{booking_id}",
    response_model=BookingResponse,
    summary="Get booking details",
)
async def get_booking(
    booking_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = BookingService(db)
    booking = await service.get_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return booking


@router.post(
    "/{booking_id}/cancel",
    response_model=BookingResponse,
    summary="Cancel a booking",
    description="Cancels the booking. If already paid, 80% refund is calculated.",
)
async def cancel_booking(
    booking_id: UUID,
    data: BookingCancelRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = BookingService(db)
    booking = await service.get_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    try:
        return await service.cancel(booking, data, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

