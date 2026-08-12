"""Apartment service."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import Float, cast, func, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import String
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.apartment import Apartment
from app.schemas.common import PaginationParams

logger = get_logger(__name__)


class ApartmentService:
    """Service for apartment operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, apartment_id: UUID) -> Optional[Apartment]:
        """Get apartment by ID."""
        result = await self.db.execute(
            select(Apartment).where(
                Apartment.id == apartment_id,
                Apartment.is_active == True,
                Apartment.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def get_list(
        self,
        pagination: PaginationParams,
        city: Optional[str] = None,
        bedroom_type: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_rating: Optional[float] = None,
        amenities: Optional[List[str]] = None,
        sort_by: Optional[str] = "recommended",
    ) -> tuple[List[Apartment], int]:
        """Get paginated list of apartments with filters and sorting."""
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

        if min_rating is not None:
            query = query.where(Apartment.rating >= min_rating)

        if amenities:
            for amenity in amenities:
                query = query.where(
                    Apartment.amenities.contains(cast([amenity], ARRAY(String)))
                )

        # Get count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting
        if sort_by == "price_low_to_high":
            query = query.order_by(Apartment.price_per_night.asc().nullslast())
        elif sort_by == "price_high_to_low":
            query = query.order_by(Apartment.price_per_night.desc().nullslast())
        elif sort_by == "highest_rated":
            query = query.order_by(Apartment.rating.desc().nullslast())
        elif sort_by == "most_reviews":
            query = query.order_by(Apartment.total_reviews.desc())
        else:
            # recommended: featured first, then by rating, then by reviews
            query = query.order_by(
                Apartment.is_featured.desc(),
                Apartment.rating.desc().nullslast(),
                Apartment.total_reviews.desc(),
            )

        query = query.offset(pagination.offset).limit(pagination.page_size)

        result = await self.db.execute(query)
        apartments = result.scalars().all()

        return list(apartments), total

    async def check_availability(
        self,
        apartment_id: UUID,
        check_in: str,
        check_out: str,
    ) -> bool:
        """Whether the apartment can be booked for these dates.

        Delegates to BookingService so this, /stays, and the booking path give the same
        answer. This used to count any non-cancelled booking as a conflict, so an
        abandoned unpaid booking made the apartment look unbookable while the booking
        path would still accept it.
        """
        from datetime import date as date_type

        from app.services.booking_service import BookingService

        check_in_date = (
            check_in if isinstance(check_in, date_type) else date_type.fromisoformat(str(check_in))
        )
        check_out_date = (
            check_out if isinstance(check_out, date_type) else date_type.fromisoformat(str(check_out))
        )

        return await BookingService(self.db).check_apartment_availability(
            apartment_id, check_in_date, check_out_date
        )
