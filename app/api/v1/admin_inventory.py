"""Admin inventory overview, alerts, and bulk operations."""

from datetime import date, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.schemas.inventory import (
    BulkAvailabilityRequest,
    BulkOperationResponse,
    BulkPricingRequest,
    InventoryAlertsResponse,
    InventorySummaryResponse,
    OccupancyResponse,
)
from app.services.inventory_service import InventoryService

router = APIRouter()


@router.get(
    "/summary",
    response_model=InventorySummaryResponse,
    dependencies=[RequireAdmin],
    summary="Inventory summary",
)
async def get_summary(db: DatabaseSession):
    """What exists and how much of it is sellable, across every property type."""
    return await InventoryService(db).summary()


@router.get(
    "/occupancy",
    response_model=OccupancyResponse,
    dependencies=[RequireAdmin],
    summary="Occupancy over a date range",
)
async def get_occupancy(
    db: DatabaseSession,
    start_date: Optional[date] = Query(None, description="Defaults to today"),
    end_date: Optional[date] = Query(None, description="Exclusive; defaults to 30 days out"),
):
    """
    Room-night occupancy across the window, with a per-hotel breakdown sorted worst-first.

    Capacity is room units × nights, so it reflects `total_rooms` rather than treating a
    room type as one unit.
    """
    start = start_date or date.today()
    end = end_date or (start + timedelta(days=30))
    if end <= start:
        raise HTTPException(status_code=400, detail="end_date must be after start_date")
    if (end - start).days > 400:
        raise HTTPException(status_code=400, detail="Range cannot exceed 400 nights")

    return await InventoryService(db).occupancy(start, end)


@router.get(
    "/alerts",
    response_model=InventoryAlertsResponse,
    dependencies=[RequireAdmin],
    summary="Inventory problems needing attention",
)
async def get_alerts(db: DatabaseSession):
    """
    Concrete problems, not statistics — rooms on sale with no units or price, apartments
    that cannot be booked, calendar gaps in the next 30 days, menu items available at a
    closed restaurant, and today's sold-out items.

    Sorted high severity first. An empty list is the healthy state.
    """
    return await InventoryService(db).alerts()


@router.post(
    "/bulk/pricing",
    response_model=BulkOperationResponse,
    dependencies=[RequireAdmin],
    summary="Change room prices in bulk",
)
async def bulk_pricing(
    data: BulkPricingRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """
    Apply a price change across many rooms — by hotel, by city, or by explicit ids.

    **Defaults to a dry run.** The response lists every room with its current and new
    price and changes nothing until you send `dry_run: false`. A mistyped percentage
    across a whole city is expensive to undo.

    ```json
    {"start_date": "2026-12-20", "end_date": "2027-01-05",
     "city": "Ahmedabad", "percent_change": 15, "dry_run": true}
    ```
    """
    try:
        return await InventoryService(db).bulk_room_pricing(
            start=data.start_date,
            end=data.end_date,
            updated_by=current_user.id,
            hotel_ids=data.hotel_ids,
            room_ids=data.room_ids,
            city=data.city,
            percent_change=data.percent_change,
            set_price=data.set_price,
            weekdays=data.weekdays,
            dry_run=data.dry_run,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/bulk/availability",
    response_model=BulkOperationResponse,
    dependencies=[RequireAdmin],
    summary="Block or reopen dates in bulk",
)
async def bulk_availability(
    data: BulkAvailabilityRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """
    Block or reopen a date range across many rooms at once — a citywide event, a
    refurbishment programme, a seasonal closure.

    **Defaults to a dry run**, same as bulk pricing.
    """
    try:
        return await InventoryService(db).bulk_room_availability(
            start=data.start_date,
            end=data.end_date,
            updated_by=current_user.id,
            is_blocked=data.is_blocked,
            hotel_ids=data.hotel_ids,
            room_ids=data.room_ids,
            city=data.city,
            notes=data.notes,
            dry_run=data.dry_run,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
