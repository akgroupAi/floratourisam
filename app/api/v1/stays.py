"""Public /stays endpoints — alias for the apartments browsing flow.

The frontend uses `/stays` and `/stay/:id` routes which map to the same
apartment data as `/apartments`. This module re-exports the same handlers
so both URL prefixes work without duplicating logic.
"""

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import and_, func, select

from app.api.deps import DatabaseSession
from app.models.apartment import Apartment
from app.models.booking import Booking
from app.utils.enums import BookingStatus

# Import the response schema from apartments module
from app.api.v1.apartments import ApartmentResponse
from app.schemas.common import PaginatedResponse, PaginationParams

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse[ApartmentResponse],
    summary="List available stays (apartments)",
    description=(
        "Alias for GET /apartments. The frontend /stays route maps here. "
        "Returns available apartments suitable for extended medical tourism stays."
    ),
)
async def list_stays(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    city: Optional[str] = Query(default=None),
    bedroom_type: Optional[str] = Query(default=None),
    min_price: Optional[float] = Query(default=None, ge=0),
    max_price: Optional[float] = Query(default=None, ge=0),
):
    query = select(Apartment).where(
        Apartment.is_active == True,
        Apartment.is_available == True,
        Apartment.is_deleted == False,
    )
    if city:
        query = query.where(func.lower(Apartment.city) == city.lower())
    if bedroom_type:
        query = query.where(Apartment.bedroom_type == bedroom_type)
    if min_price is not None:
        query = query.where(Apartment.price_per_night >= min_price)
    if max_price is not None:
        query = query.where(Apartment.price_per_night <= max_price)

    total = (
        await db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar() or 0

    pagination = PaginationParams(page=page, page_size=page_size)
    query = (
        query.order_by(Apartment.priority.desc(), Apartment.name.asc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    rows = await db.execute(query)
    return PaginatedResponse.create(list(rows.scalars().all()), total, page, page_size)


@router.get(
    "/{stay_id}",
    response_model=ApartmentResponse,
    summary="Get stay (apartment) details",
    description="Alias for GET /apartments/{id}. Used by /stay/:id frontend route.",
)
async def get_stay(stay_id: UUID, db: DatabaseSession):
    result = await db.execute(
        select(Apartment).where(
            Apartment.id == stay_id,
            Apartment.is_active == True,
            Apartment.is_deleted == False,
        )
    )
    apartment = result.scalar_one_or_none()
    if not apartment:
        raise HTTPException(status_code=404, detail="Stay not found")
    return apartment


@router.get(
    "/{stay_id}/availability",
    summary="Check stay availability for a date range",
)
async def check_stay_availability(
    stay_id: UUID,
    db: DatabaseSession,
    check_in: date = Query(...),
    check_out: date = Query(...),
):
    if check_out <= check_in:
        raise HTTPException(status_code=400, detail="check_out must be after check_in")

    # Shared with /apartments/{id}/availability and the booking path — this used to run
    # its own query with a different status rule and disagree with both.
    from app.services.booking_service import BookingService

    is_available = await BookingService(db).check_apartment_availability(
        stay_id, check_in, check_out
    )
    return {
        "stay_id": stay_id,
        "check_in": check_in,
        "check_out": check_out,
        "nights": (check_out - check_in).days,
        "available": is_available,
    }
