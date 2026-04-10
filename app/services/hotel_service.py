"""Hotel service."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import Float, cast, func, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import String
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.hotel import Hotel, Room, RoomAvailability
from app.schemas.common import PaginationParams

logger = get_logger(__name__)


class HotelService:
    """Service for hotel operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, hotel_id: UUID) -> Optional[Hotel]:
        """Get hotel by ID."""
        result = await self.db.execute(
            select(Hotel).where(Hotel.id == hotel_id, Hotel.is_active == True)
        )
        return result.scalar_one_or_none()

    async def get_list(
        self,
        pagination: PaginationParams,
        city: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_rating: Optional[float] = None,
        amenities: Optional[List[str]] = None,
        sort_by: Optional[str] = "recommended",
    ) -> tuple[List[Hotel], int]:
        """Get paginated list of hotels."""
        query = select(Hotel).where(Hotel.is_active == True)

        if city:
            query = query.where(func.lower(Hotel.city) == city.lower())

        if min_price is not None:
            query = query.where(Hotel.base_price_per_night >= min_price)

        if max_price is not None:
            query = query.where(Hotel.base_price_per_night <= max_price)

        if min_rating is not None:
            query = query.where(Hotel.rating >= min_rating)

        if amenities:
            for amenity in amenities:
                query = query.where(
                    Hotel.amenities.contains(cast([amenity], ARRAY(String)))
                )

        # Get count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting
        if sort_by == "price_low_to_high":
            query = query.order_by(Hotel.base_price_per_night.asc().nullslast())
        elif sort_by == "price_high_to_low":
            query = query.order_by(Hotel.base_price_per_night.desc().nullslast())
        elif sort_by == "highest_rated":
            query = query.order_by(Hotel.rating.desc().nullslast())
        elif sort_by == "most_reviews":
            query = query.order_by(Hotel.total_reviews.desc())
        else:
            # recommended: featured first, then by rating, then by reviews
            query = query.order_by(
                Hotel.is_featured.desc(),
                Hotel.rating.desc().nullslast(),
                Hotel.total_reviews.desc(),
            )

        query = query.offset(pagination.offset).limit(pagination.page_size)

        result = await self.db.execute(query)
        hotels = result.scalars().all()

        return list(hotels), total

    async def get_rooms(self, hotel_id: UUID) -> List[Room]:
        """Get rooms for a hotel."""
        result = await self.db.execute(
            select(Room).where(Room.hotel_id == hotel_id, Room.is_available == True)
        )
        return list(result.scalars().all())

    async def check_availability(
        self,
        room_id: UUID,
        check_in: str,
        check_out: str
    ) -> bool:
        """Check room availability for dates. (Placeholder implementation)"""
        # In a real implementation, we would check the RoomAvailability table
        # against the requested date range.
        return True
