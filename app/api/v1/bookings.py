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

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DatabaseSession
from app.core.logging import get_logger
from app.models.booking import Booking
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
    BookingDocumentResponse,
    BookingGuestCreate,
    BookingGuestResponse,
    BookingGuestUpdate,
)
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.refund import PatientRefundStatus, RefundPreviewResponse
from app.services.booking_guest_service import BookingGuestService, document_download_url
from app.services.booking_service import BookingService
from app.services.patient_service import PatientService

logger = get_logger(__name__)
from app.utils.enums import BookingType
from app.utils.pricing import price_with_platform_fee

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
        _, platform_fee, total_price = price_with_platform_fee(base_price, taxes)
        currency = room.hotel.currency if room.hotel else "USD"
        entity_name = room.hotel.name if room.hotel else None

        return PriceCalculationResponse(
            booking_type="hotel",
            nights=nights,
            pricing_tier=None,
            rate_used=room.price_per_night,
            base_price=base_price,
            taxes=taxes,
            platform_fee=platform_fee,
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

        _, platform_fee, total_price = price_with_platform_fee(base_price)

        return PriceCalculationResponse(
            booking_type="apartment",
            nights=nights,
            pricing_tier=tier,
            rate_used=rate_used,
            base_price=base_price,
            taxes=0,
            platform_fee=platform_fee,
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
    """Get a booking.

    Restricted to the patient who owns it, an admin, or the property's manager.
    """
    return await _booking_for_caller(db, booking_id, current_user)


@router.post(
    "/{booking_id}/cancel",
    response_model=BookingResponse,
    summary="Cancel a booking",
    description=(
        "Cancels the booking and works out the refund under the cancellation policy. "
        "Any refund due is queued for admin approval — no money moves here. "
        "Call GET /bookings/{id}/refund-preview first to show the customer what they "
        "will get back before they confirm."
    ),
)
async def cancel_booking(
    booking_id: UUID,
    data: BookingCancelRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Cancel a booking, giving a reason.

    Restricted to the patient who owns it, an admin, or the property's manager —
    cancelling is destructive and triggers a refund, so it must never be reachable by
    booking id alone.
    """
    booking = await _booking_for_caller(db, booking_id, current_user)
    try:
        return await BookingService(db).cancel(booking, data, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))



# ============== TRAVELLERS & DOCUMENTS ==============
#
# Who is travelling (patient plus companions) and the files they upload — passports,
# flight tickets, visas. These are sensitive, so every route resolves the caller first.


async def _booking_for_caller(db, booking_id: UUID, user) -> Booking:
    """Fetch a booking the caller is entitled to see.

    Permitted: the patient who owns it, an admin, or the manager of the property it is
    for. Anything else gets 404 rather than 403 — identical to a booking that does not
    exist, so the endpoint cannot be used to probe for references.
    """
    from app.core.manager_scope import ADMIN_ROLES, MANAGER_ROLES
    from app.models.apartment import Apartment as _Apartment
    from app.models.hotel import Hotel as _Hotel, Room as _Room
    from app.models.restaurant import Restaurant as _Restaurant

    booking = (
        await db.execute(
            select(Booking).where(Booking.id == booking_id, Booking.is_deleted == False)
        )
    ).scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if user.role in ADMIN_ROLES:
        return booking

    if user.role in MANAGER_ROLES:
        managed = False
        if booking.hotel_room_id:
            managed = bool(
                (
                    await db.execute(
                        select(_Hotel.id)
                        .join(_Room, _Room.hotel_id == _Hotel.id)
                        .where(_Room.id == booking.hotel_room_id, _Hotel.manager_id == user.id)
                    )
                ).scalar_one_or_none()
            )
        elif booking.apartment_id:
            managed = bool(
                (
                    await db.execute(
                        select(_Apartment.id).where(
                            _Apartment.id == booking.apartment_id,
                            _Apartment.manager_id == user.id,
                        )
                    )
                ).scalar_one_or_none()
            )
        elif booking.restaurant_id:
            managed = bool(
                (
                    await db.execute(
                        select(_Restaurant.id).where(
                            _Restaurant.id == booking.restaurant_id,
                            _Restaurant.manager_id == user.id,
                        )
                    )
                ).scalar_one_or_none()
            )
        if managed:
            return booking
        raise HTTPException(status_code=404, detail="Booking not found")

    # Patients see only their own.
    patient = await PatientService(db).get_by_user_id(user.id)
    if not patient or booking.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.get(
    "/{booking_id}/guests",
    response_model=list[BookingGuestResponse],
    summary="Travellers on a booking",
)
async def list_booking_guests(
    booking_id: UUID, current_user: CurrentUser, db: DatabaseSession
):
    """The patient and any companions, patient first."""
    await _booking_for_caller(db, booking_id, current_user)
    return await BookingGuestService(db).list_guests(booking_id)


@router.post(
    "/{booking_id}/guests",
    response_model=list[BookingGuestResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add travellers to a booking",
)
async def add_booking_guests(
    booking_id: UUID,
    guests: list[BookingGuestCreate],
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """
    Add the patient and any companions after the booking exists.

    Travellers can also be supplied inline when creating a hotel or apartment booking,
    via the `guests` field — this endpoint is for adding them later or correcting them.
    """
    booking = await _booking_for_caller(db, booking_id, current_user)
    service = BookingGuestService(db)
    try:
        await service.add_guests(booking.id, guests, created_by=current_user.id)
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return await service.list_guests(booking_id)


@router.put(
    "/{booking_id}/guests/{guest_id}",
    response_model=BookingGuestResponse,
    summary="Edit a traveller",
)
async def update_booking_guest(
    booking_id: UUID,
    guest_id: UUID,
    data: BookingGuestUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    await _booking_for_caller(db, booking_id, current_user)
    service = BookingGuestService(db)
    try:
        guest = await service.update_guest(booking_id, guest_id, data, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {
        **{c.name: getattr(guest, c.name) for c in guest.__table__.columns},
        "document_count": 0,
    }


@router.delete(
    "/{booking_id}/guests/{guest_id}",
    response_model=MessageResponse,
    summary="Remove a companion",
)
async def remove_booking_guest(
    booking_id: UUID, guest_id: UUID, current_user: CurrentUser, db: DatabaseSession
):
    """Remove a companion. The patient cannot be removed from their own booking."""
    await _booking_for_caller(db, booking_id, current_user)
    service = BookingGuestService(db)
    try:
        removed = await service.remove_guest(booking_id, guest_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not removed:
        raise HTTPException(status_code=404, detail="Traveller not found on this booking")
    return MessageResponse(message="Traveller removed")


@router.get(
    "/{booking_id}/documents",
    response_model=list[BookingDocumentResponse],
    summary="Documents on a booking",
)
async def list_booking_documents(
    booking_id: UUID, current_user: CurrentUser, db: DatabaseSession
):
    """
    Uploaded passports, flight tickets, visas, and insurance.

    Use `download_url` to fetch a file — it needs the `Authorization` header, so a plain
    `<a href>` will not work.
    """
    await _booking_for_caller(db, booking_id, current_user)
    return await BookingGuestService(db).list_documents(booking_id)


@router.post(
    "/{booking_id}/documents",
    response_model=BookingDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a booking document",
)
async def upload_booking_document(
    booking_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
    file: UploadFile = File(..., description="JPG, PNG, WebP, or PDF — max 10 MB"),
    document_type: str = Form(
        ...,
        description="passport, flight_ticket, visa, insurance, medical_report, id_proof, other",
    ),
    guest_id: Optional[UUID] = Form(
        None, description="Attach to one traveller, e.g. their passport"
    ),
    notes: Optional[str] = Form(None, max_length=500),
):
    """
    Upload a flight ticket, passport photo, visa, or insurance document.

    Attach it to a traveller with `guest_id` — a passport belongs to a person. Leave it
    out for booking-level documents like a shared flight booking.
    """
    booking = await _booking_for_caller(db, booking_id, current_user)
    service = BookingGuestService(db)
    try:
        document = await service.add_document(
            booking=booking,
            file=file,
            document_type=document_type,
            uploaded_by=current_user.id,
            guest_id=guest_id,
            notes=notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    guest_name = None
    if document.guest_id:
        guest = await service.get_guest(booking_id, document.guest_id)
        guest_name = guest.full_name if guest else None

    return {
        "id": document.id,
        "booking_id": document.booking_id,
        "guest_id": document.guest_id,
        "guest_name": guest_name,
        "document_type": document.document_type,
        "file_name": document.file_name,
        "content_type": document.content_type,
        "file_size_bytes": document.file_size_bytes,
        "notes": document.notes,
        "download_url": document_download_url(document.booking_id, document.id),
        "created_at": document.created_at,
    }


@router.get(
    "/{booking_id}/documents/{document_id}",
    response_class=FileResponse,
    summary="Download a booking document",
)
async def download_booking_document(
    booking_id: UUID, document_id: UUID, current_user: CurrentUser, db: DatabaseSession
):
    """
    Stream a document back.

    Served through this endpoint rather than a static path because these are passports
    and medical reports — `file_path` is a server location and is never browser-reachable.
    Requires the `Authorization` header, so fetch it and use a blob URL.
    """
    await _booking_for_caller(db, booking_id, current_user)
    service = BookingGuestService(db)

    document = await service.get_document(booking_id, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    path = service.resolve_document_path(document)
    if not path:
        raise HTTPException(status_code=404, detail="Document file is missing from storage")

    return FileResponse(
        path=str(path),
        media_type=document.content_type or "application/octet-stream",
        filename=document.file_name,
    )


@router.delete(
    "/{booking_id}/documents/{document_id}",
    response_model=MessageResponse,
    summary="Delete a booking document",
)
async def delete_booking_document(
    booking_id: UUID, document_id: UUID, current_user: CurrentUser, db: DatabaseSession
):
    """Soft-delete a document. The file is retained on disk for auditability."""
    await _booking_for_caller(db, booking_id, current_user)
    if not await BookingGuestService(db).delete_document(
        booking_id, document_id, current_user.id
    ):
        raise HTTPException(status_code=404, detail="Document not found")
    return MessageResponse(message="Document deleted")

@router.get(
    "/{booking_id}/refund-preview",
    response_model=RefundPreviewResponse,
    summary="What cancelling this booking would refund",
)
async def preview_refund(
    booking_id: UUID, current_user: CurrentUser, db: DatabaseSession
):
    """
    Show the refund **before** cancelling, with the deductions itemised.

    Changes nothing. Call this from the cancel dialog so a customer sees the charge
    while they can still change their mind, rather than discovering it afterwards.
    """
    booking = await _booking_for_caller(db, booking_id, current_user)
    from app.services.refund_service import RefundService

    return await RefundService(db).preview(booking)

@router.get(
    "/{booking_id}/refund-status",
    response_model=PatientRefundStatus,
    summary="Refund status for a cancelled booking",
)
async def get_refund_status(
    booking_id: UUID, current_user: CurrentUser, db: DatabaseSession
):
    """
    Where the refund has got to, in words the patient can read.

    `status_label` and `message` are ready to display - use them rather than composing
    wording per screen. Note that "issued" is not "in your account": Razorpay takes
    5-7 working days to settle, which `expected_days` states.
    """
    booking = await _booking_for_caller(db, booking_id, current_user)
    from app.services.refund_service import RefundService

    return RefundService.patient_status(booking)
