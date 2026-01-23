"""Booking endpoints."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from app.api.deps import CurrentUser, DatabaseSession
from app.schemas.booking import BookingListResponse, BookingResponse, HotelBookingCreate, RestaurantBookingCreate, BookingCancelRequest
from app.schemas.common import PaginatedResponse, PaginationParams
from app.services.booking_service import BookingService
from app.services.patient_service import PatientService

router = APIRouter()


@router.get("", response_model=PaginatedResponse[BookingListResponse])
async def list_bookings(current_user: CurrentUser, db: DatabaseSession, page: int = Query(1), page_size: int = Query(20)):
    """List user's bookings."""
    patient_service = PatientService(db)
    patient = await patient_service.get_by_user_id(current_user.id)
    service = BookingService(db)
    bookings, total = await service.get_list(PaginationParams(page=page, page_size=page_size), patient.id if patient else None)
    return PaginatedResponse.create(bookings, total, page, page_size)


@router.post("/hotel", response_model=BookingResponse)
async def create_hotel_booking(data: HotelBookingCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create hotel booking."""
    patient_service = PatientService(db)
    patient = await patient_service.get_or_create(current_user.id)
    service = BookingService(db)
    return await service.create_hotel_booking(patient.id, data, current_user.id)


@router.post("/restaurant", response_model=BookingResponse)
async def create_restaurant_booking(data: RestaurantBookingCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create restaurant booking."""
    patient_service = PatientService(db)
    patient = await patient_service.get_or_create(current_user.id)
    service = BookingService(db)
    return await service.create_restaurant_booking(patient.id, data, current_user.id)


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(booking_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Get booking by ID."""
    service = BookingService(db)
    booking = await service.get_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.post("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(booking_id: UUID, data: BookingCancelRequest, current_user: CurrentUser, db: DatabaseSession):
    """Cancel a booking."""
    service = BookingService(db)
    booking = await service.get_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return await service.cancel(booking, data, current_user.id)
