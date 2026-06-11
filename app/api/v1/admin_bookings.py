"""Admin booking management endpoints."""

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.schemas.booking import (
    AdminBookingDashboardResponse,
    AdminBookingDetailResponse,
    AdminBookingUpdate,
    BookingCancelRequest,
    BookingResponse,
    BookingReportSummary,
)
from app.schemas.common import PaginationParams
from app.services.booking_service import BookingService
from app.utils.enums import BookingType

router = APIRouter()


@router.get(
    "/",
    response_model=AdminBookingDashboardResponse,
    summary="List bookings with KPIs",
    description="Returns a list of bookings and key performance indicators for the admin dashboard.",
    dependencies=[RequireAdmin],
)
async def list_bookings(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    booking_type: Optional[BookingType] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    service = BookingService(db)
    kpis = await service.get_admin_dashboard_stats()
    items, total = await service.get_admin_list(
        PaginationParams(page=page, page_size=page_size),
        booking_type=booking_type,
        status=status,
        search=search,
    )
    return AdminBookingDashboardResponse(
        kpis=kpis,
        bookings=items,
        total_count=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/report/dashboard",
    response_model=BookingReportSummary,
    summary="Booking reports summary for dashboard",
    description="Returns brief report summary of bookings for all KPIs including trends.",
    dependencies=[RequireAdmin],
)
async def get_booking_reports_dashboard(
    db: DatabaseSession,
    start_date: date = Query(..., description="Start date for reports"),
    end_date: date = Query(..., description="End date for reports"),
    property_type: str = Query("all", pattern="^(all|hotel|apartment)$")
):
    service = BookingService(db)
    return await service.get_booking_reports(start_date, end_date, property_type)


@router.get(
    "/{booking_id}",
    response_model=AdminBookingDetailResponse,
    summary="View booking details",
    description="Returns full details of a particular booking, including timeline.",
    dependencies=[RequireAdmin],
)
async def get_booking_detail(
    booking_id: UUID,
    db: DatabaseSession,
):
    service = BookingService(db)
    try:
        return await service.get_admin_detail(booking_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch(
    "/{booking_id}",
    response_model=BookingResponse,
    summary="Modify a booking",
    description="Updates booking details such as dates, guest count, or status.",
    dependencies=[RequireAdmin],
)
async def modify_booking(
    booking_id: UUID,
    data: AdminBookingUpdate,
    db: DatabaseSession,
    current_user: CurrentUser,
):
    service = BookingService(db)
    try:
        return await service.admin_update(booking_id, data, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/{booking_id}/cancel",
    response_model=BookingResponse,
    summary="Cancel a booking",
    description="Cancels the booking with a provided reason.",
    dependencies=[RequireAdmin],
)
async def cancel_booking(
    booking_id: UUID,
    data: BookingCancelRequest,
    db: DatabaseSession,
    current_user: CurrentUser,
):
    service = BookingService(db)
    booking = await service.get_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    try:
        return await service.cancel(booking, data, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
