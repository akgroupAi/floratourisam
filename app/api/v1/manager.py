"""Manager portal — self-service for hotel, apartment, and restaurant managers.

Every endpoint resolves the caller through `ManagerScope`, so a manager only ever sees
and edits the properties assigned to them. Admins reach everything here too, unscoped.

Managers previously had three list endpoints across the whole platform; routine work
like adding a room, changing a price, or blocking a date required an admin.
"""

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DatabaseSession
from app.core.manager_scope import ManagerScope, ManagerScopeDep
from app.schemas.apartment import (
    ApartmentCalendarDay,
    ApartmentCalendarUpdate,
    ApartmentCalendarUpdateResponse,
)
from app.schemas.booking import BookingCancelRequest
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.hotel import (
    RoomCalendarDay,
    RoomCalendarUpdate,
    RoomCalendarUpdateResponse,
    RoomResponse,
)
from app.schemas.refund import (
    PendingRefundItem,
    RefundApproveRequest,
    RefundApproveResponse,
    RefundRejectRequest,
)
from app.schemas.manager import (
    ManagerBookingItem,
    ManagerMenuItem,
    MenuStockUpdate,
    ManagerDashboardResponse,
    ManagerPropertiesResponse,
    ManagerReviewItem,
    ReviewResponseRequest,
)
from app.services.booking_service import BookingService
from app.services.manager_service import ManagerService

router = APIRouter()


# ============== MY PROPERTIES & DASHBOARD ==============


@router.get(
    "/me/properties",
    response_model=ManagerPropertiesResponse,
    summary="Properties I manage",
)
async def my_properties(db: DatabaseSession, scope: ManagerScope = ManagerScopeDep):
    """Every hotel, apartment, and restaurant assigned to the caller."""
    return await ManagerService(db, scope).my_properties()


@router.get(
    "/me/dashboard",
    response_model=ManagerDashboardResponse,
    summary="Today at my properties",
)
async def my_dashboard(db: DatabaseSession, scope: ManagerScope = ManagerScopeDep):
    """Arrivals, departures, in-house guests, unpaid bookings, and revenue."""
    return await ManagerService(db, scope).dashboard()


# ============== ROOMS ==============


@router.get(
    "/rooms",
    response_model=List[RoomResponse],
    summary="Rooms at my hotels",
)
async def list_rooms(
    db: DatabaseSession,
    scope: ManagerScope = ManagerScopeDep,
    hotel_id: Optional[UUID] = Query(None, description="Limit to one of my hotels"),
):
    """Room types across my hotels."""
    return await ManagerService(db, scope).list_rooms(hotel_id)


@router.get(
    "/rooms/{room_id}",
    response_model=RoomResponse,
    summary="Get one of my rooms",
)
async def get_room(
    room_id: UUID, db: DatabaseSession, scope: ManagerScope = ManagerScopeDep
):
    try:
        return await ManagerService(db, scope).get_room(room_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ============== ROOM CALENDAR ==============


@router.get(
    "/rooms/{room_id}/calendar",
    response_model=List[RoomCalendarDay],
    summary="Read a room's rate and availability calendar",
)
async def get_room_calendar(
    room_id: UUID,
    db: DatabaseSession,
    scope: ManagerScope = ManagerScopeDep,
    start_date: date = Query(...),
    end_date: date = Query(..., description="Exclusive"),
):
    """Per-night price, inventory, bookings, and blocks for one of my rooms."""
    try:
        await ManagerService(db, scope).get_room(room_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if end_date <= start_date:
        raise HTTPException(status_code=400, detail="end_date must be after start_date")
    if (end_date - start_date).days > 400:
        raise HTTPException(status_code=400, detail="Range cannot exceed 400 nights")

    return await BookingService(db).get_room_calendar(room_id, start_date, end_date)


@router.put(
    "/rooms/{room_id}/calendar",
    response_model=RoomCalendarUpdateResponse,
    summary="Set rates, inventory, or blocks on one of my rooms",
)
async def set_room_calendar(
    room_id: UUID,
    data: RoomCalendarUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
    scope: ManagerScope = ManagerScopeDep,
):
    """Same bulk upsert as the admin calendar, restricted to my rooms."""
    try:
        await ManagerService(db, scope).get_room(room_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if (data.end_date - data.start_date).days > 400:
        raise HTTPException(status_code=400, detail="Range cannot exceed 400 nights")

    try:
        days = await BookingService(db).set_room_calendar(
            room_id=room_id,
            start=data.start_date,
            end=data.end_date,
            updated_by=current_user.id,
            price=data.price,
            available_rooms=data.available_rooms,
            is_blocked=data.is_blocked,
            notes=data.notes,
            weekdays=data.weekdays,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return RoomCalendarUpdateResponse(
        room_id=room_id,
        days_updated=days,
        start_date=data.start_date,
        end_date=data.end_date,
    )


# ============== APARTMENT CALENDAR ==============


@router.get(
    "/apartments/{apartment_id}/calendar",
    response_model=List[ApartmentCalendarDay],
    summary="Read one of my apartments' calendar",
)
async def get_apartment_calendar(
    apartment_id: UUID,
    db: DatabaseSession,
    scope: ManagerScope = ManagerScopeDep,
    start_date: date = Query(...),
    end_date: date = Query(..., description="Exclusive"),
):
    scope.assert_apartment(apartment_id)
    if end_date <= start_date:
        raise HTTPException(status_code=400, detail="end_date must be after start_date")
    if (end_date - start_date).days > 400:
        raise HTTPException(status_code=400, detail="Range cannot exceed 400 nights")

    try:
        return await BookingService(db).get_apartment_calendar(
            apartment_id, start_date, end_date
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put(
    "/apartments/{apartment_id}/calendar",
    response_model=ApartmentCalendarUpdateResponse,
    summary="Set rates, minimum stay, or blocks on one of my apartments",
)
async def set_apartment_calendar(
    apartment_id: UUID,
    data: ApartmentCalendarUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
    scope: ManagerScope = ManagerScopeDep,
):
    scope.assert_apartment(apartment_id)
    if (data.end_date - data.start_date).days > 400:
        raise HTTPException(status_code=400, detail="Range cannot exceed 400 nights")

    try:
        days = await BookingService(db).set_apartment_calendar(
            apartment_id=apartment_id,
            start=data.start_date,
            end=data.end_date,
            updated_by=current_user.id,
            price=data.price,
            is_blocked=data.is_blocked,
            minimum_nights=data.minimum_nights,
            notes=data.notes,
            weekdays=data.weekdays,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return ApartmentCalendarUpdateResponse(
        apartment_id=apartment_id,
        days_updated=days,
        start_date=data.start_date,
        end_date=data.end_date,
    )


# ============== BOOKINGS ==============


@router.get(
    "/bookings",
    response_model=PaginatedResponse[ManagerBookingItem],
    summary="Bookings at my properties",
)
async def list_bookings(
    db: DatabaseSession,
    scope: ManagerScope = ManagerScopeDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    booking_type: Optional[str] = Query(None, description="hotel, apartment, restaurant"),
    from_date: Optional[date] = Query(None, description="Check-in on or after"),
    to_date: Optional[date] = Query(None, description="Check-in on or before"),
    search: Optional[str] = Query(None, description="Booking reference"),
):
    """Every booking at a property I manage, newest first."""
    items, total = await ManagerService(db, scope).list_bookings(
        PaginationParams(page=page, page_size=page_size),
        status=status,
        booking_type=booking_type,
        from_date=from_date,
        to_date=to_date,
        search=search,
    )
    return PaginatedResponse.create(items, total, page, page_size)


@router.get(
    "/bookings/{booking_id}",
    response_model=ManagerBookingItem,
    summary="Get a booking at one of my properties",
)
async def get_booking(
    booking_id: UUID, db: DatabaseSession, scope: ManagerScope = ManagerScopeDep
):
    try:
        return await ManagerService(db, scope).get_booking(booking_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/bookings/{booking_id}/confirm",
    response_model=MessageResponse,
    summary="Confirm a pending booking",
)
async def confirm_booking(
    booking_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
    scope: ManagerScope = ManagerScopeDep,
):
    """Confirm a booking the guest has made at one of my properties."""
    service = ManagerService(db, scope)
    try:
        booking = await service.get_booking(booking_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    from app.schemas.booking import BookingStatusUpdate
    from app.utils.enums import BookingStatus

    if booking.status not in (BookingStatus.PENDING.value,):
        raise HTTPException(
            status_code=400,
            detail=f"Only pending bookings can be confirmed (this one is {booking.status})",
        )

    try:
        await BookingService(db).update_status(
            booking,
            BookingStatusUpdate(status=BookingStatus.CONFIRMED),
            updated_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return MessageResponse(message="Booking confirmed")


@router.post(
    "/bookings/{booking_id}/cancel",
    response_model=MessageResponse,
    summary="Cancel a booking at one of my properties",
)
async def cancel_booking(
    booking_id: UUID,
    data: BookingCancelRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
    scope: ManagerScope = ManagerScopeDep,
):
    """Cancel on the guest's behalf — a no-show, or a property-side problem."""
    service = ManagerService(db, scope)
    try:
        booking = await service.get_booking(booking_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    try:
        await BookingService(db).cancel(booking, data, cancelled_by=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return MessageResponse(message="Booking cancelled")


# ============== REVIEWS ==============


@router.get(
    "/reviews",
    response_model=PaginatedResponse[ManagerReviewItem],
    summary="Reviews of my properties",
)
async def list_reviews(
    db: DatabaseSession,
    scope: ManagerScope = ManagerScopeDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unanswered_only: bool = Query(False, description="Only reviews without a response"),
    max_rating: Optional[int] = Query(None, ge=1, le=5, description="e.g. 3 for the unhappy ones"),
):
    """Reviews of my properties. `unanswered_only` plus `max_rating=3` is the queue that matters."""
    items, total = await ManagerService(db, scope).list_reviews(
        PaginationParams(page=page, page_size=page_size),
        unanswered_only=unanswered_only,
        max_rating=max_rating,
    )
    return PaginatedResponse.create(items, total, page, page_size)


@router.post(
    "/reviews/{review_id}/respond",
    response_model=MessageResponse,
    summary="Respond to a review of my property",
)
async def respond_to_review(
    review_id: UUID,
    data: ReviewResponseRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
    scope: ManagerScope = ManagerScopeDep,
):
    """Publish a reply. Managers may respond to their own properties' reviews only."""
    from sqlalchemy import select

    from app.models.review import Review

    review = (
        await db.execute(
            select(Review).where(Review.id == review_id, Review.is_deleted == False)
        )
    ).scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    if review.entity_type == "hotel":
        scope.assert_hotel(review.entity_id)
    elif review.entity_type == "apartment":
        scope.assert_apartment(review.entity_id)
    elif review.entity_type == "restaurant":
        scope.assert_restaurant(review.entity_id)
    elif not scope.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not manage this property",
        )

    from datetime import datetime, timezone

    review.response_text = data.response_text
    review.response_date = datetime.now(timezone.utc)
    review.response_by = current_user.id
    review.updated_by = current_user.id
    await db.commit()
    return MessageResponse(message="Response published")


# ============== MENU & DAILY STOCK ==============


@router.get(
    "/menu",
    response_model=List[ManagerMenuItem],
    summary="Menu items at my restaurants",
)
async def list_menu(
    db: DatabaseSession,
    scope: ManagerScope = ManagerScopeDep,
    restaurant_id: Optional[UUID] = Query(None, description="Limit to one of my restaurants"),
    sold_out_only: bool = Query(False, description="Only items that have run out today"),
):
    """
    Menu items with today's stock resolved.

    `remaining_today` is null for unlimited items. The sold counter is scoped to a date,
    so it resets itself overnight without a scheduled job.
    """
    return await ManagerService(db, scope).list_menu(restaurant_id, sold_out_only)


@router.put(
    "/menu/{item_id}/stock",
    response_model=ManagerMenuItem,
    summary="Set today's stock for a menu item",
)
async def set_menu_stock(
    item_id: UUID,
    data: MenuStockUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
    scope: ManagerScope = ManagerScopeDep,
):
    """
    Mark an item sold out, set a daily limit, or restock it.

    - `{"daily_quantity": 20}` — 20 available today
    - `{"sold_today": 20}` — sold out if the limit is 20
    - `{"reset": true}` — restocked, counter back to zero
    - `{"unlimited": true}` — no daily limit
    - `{"is_available": false}` — off the menu entirely, not just today
    """
    service = ManagerService(db, scope)
    try:
        item = await service.set_menu_stock(
            item_id,
            updated_by=current_user.id,
            daily_quantity=data.daily_quantity,
            unlimited=data.unlimited,
            sold_today=data.sold_today,
            is_available=data.is_available,
            reset=data.reset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    from datetime import datetime as _dt, timezone as _tz

    today = _dt.now(_tz.utc).date()
    remaining = ManagerService.remaining_stock(item, today)
    return ManagerMenuItem(
        id=item.id,
        restaurant_id=item.restaurant_id,
        name=item.name,
        category=item.category,
        price=item.price,
        currency=item.currency,
        is_available=item.is_available,
        available_for=item.available_for or [],
        daily_quantity=item.daily_quantity,
        sold_today=item.sold_today if item.stock_date == today else 0,
        remaining_today=remaining,
        is_sold_out=remaining is not None and remaining <= 0,
        image_url=item.image_url,
    )

# ============== REFUNDS ==============
#
# A manager can release refunds for their own properties. The scope check is the same
# one every other manager route uses, so a manager can never touch another property's
# money.


@router.get(
    "/refunds",
    response_model=PaginatedResponse[PendingRefundItem],
    summary="Refunds awaiting action at my properties",
)
async def list_manager_refunds(
    db: DatabaseSession,
    scope: ManagerScope = ManagerScopeDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="pending | failed | processed | rejected"),
):
    """Refunds on bookings at properties I manage, longest-waiting first."""
    from app.services.refund_service import RefundService

    items, total = await RefundService(db).list_pending(
        PaginationParams(page=page, page_size=page_size),
        status=status,
        scope=scope,
    )
    return PaginatedResponse.create(items, total, page, page_size)


@router.post(
    "/refunds/{booking_id}/approve",
    response_model=RefundApproveResponse,
    summary="Release a refund for one of my properties",
)
async def approve_manager_refund(
    booking_id: UUID,
    data: RefundApproveRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
    scope: ManagerScope = ManagerScopeDep,
):
    """
    **This moves real money.** Same behaviour as the admin endpoint, restricted to
    bookings at properties I manage.

    Send an empty body to pay what the policy calculated, or `amount` to override.
    """
    await ManagerService(db, scope).get_booking(booking_id)  # 404 unless it is mine

    from app.services.refund_service import RefundService

    try:
        return await RefundService(db).approve(
            booking_id, approved_by=current_user.id, amount=data.amount
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/refunds/{booking_id}/reject",
    response_model=MessageResponse,
    summary="Decline a refund for one of my properties",
)
async def reject_manager_refund(
    booking_id: UUID,
    data: RefundRejectRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
    scope: ManagerScope = ManagerScopeDep,
):
    """Decline a queued refund. The reason is stored and emailed to the customer."""
    await ManagerService(db, scope).get_booking(booking_id)  # 404 unless it is mine

    from app.services.refund_service import RefundService

    try:
        await RefundService(db).reject(booking_id, rejected_by=current_user.id, reason=data.reason)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return MessageResponse(message="Refund declined")
