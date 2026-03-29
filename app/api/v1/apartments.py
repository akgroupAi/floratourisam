"""Public apartment browsing endpoints.

Patients browse available apartments before booking via POST /bookings/apartment.
"""

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.api.deps import DatabaseSession
from app.models.apartment import Apartment
from app.schemas.common import PaginatedResponse, PaginationParams

router = APIRouter()


# ---------------------------------------------------------------------------
# Minimal response schema (inline — no separate file needed)
# ---------------------------------------------------------------------------
from pydantic import BaseModel
from app.schemas.common import BaseSchema
from typing import List


class ApartmentResponse(BaseSchema):
    """Apartment listing response."""

    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    bedroom_type: str
    capacity: int
    price_per_night: Optional[float] = None
    price_per_week: Optional[float] = None
    price_per_month: Optional[float] = None
    currency: str
    address_line1: str
    city: str
    country: str
    cover_image_url: Optional[str] = None
    amenities: Optional[List[str]] = None
    rating: Optional[float] = None
    total_reviews: int
    is_available: bool
    is_featured: bool


@router.get(
    "",
    response_model=PaginatedResponse[ApartmentResponse],
    summary="List available apartments",
)
async def list_apartments(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    city: Optional[str] = Query(default=None, description="Filter by city"),
    bedroom_type: Optional[str] = Query(default=None, description="studio | 1BR | 2BR | 3BR | 4BR+"),
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
    "/{apartment_id}",
    response_model=ApartmentResponse,
    summary="Get apartment details",
)
async def get_apartment(apartment_id: UUID, db: DatabaseSession):
    result = await db.execute(
        select(Apartment).where(
            Apartment.id == apartment_id,
            Apartment.is_active == True,
            Apartment.is_deleted == False,
        )
    )
    apartment = result.scalar_one_or_none()
    if not apartment:
        raise HTTPException(status_code=404, detail="Apartment not found")
    return apartment


@router.get(
    "/{apartment_id}/availability",
    summary="Check apartment availability for a date range",
    description=(
        "Checks whether the apartment has any confirmed bookings overlapping "
        "the requested check-in / check-out dates."
    ),
)
async def check_apartment_availability(
    apartment_id: UUID,
    db: DatabaseSession,
    check_in: date = Query(...),
    check_out: date = Query(...),
):
    if check_out <= check_in:
        raise HTTPException(status_code=400, detail="check_out must be after check_in")

    from sqlalchemy import and_
    from app.models.booking import Booking
    from app.utils.enums import BookingStatus

    conflict = await db.execute(
        select(Booking.id).where(
            and_(
                Booking.apartment_id == apartment_id,
                Booking.is_deleted == False,
                Booking.status.notin_([BookingStatus.CANCELLED.value]),
                Booking.check_in_date < check_out,
                Booking.check_out_date > check_in,
            )
        )
    )
    is_available = conflict.scalar_one_or_none() is None

    nights = (check_out - check_in).days
    return {
        "apartment_id": apartment_id,
        "check_in": check_in,
        "check_out": check_out,
        "nights": nights,
        "available": is_available,
    }
