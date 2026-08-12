"""Hotel service."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import Float, cast, func, select, or_
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
        """Get hotel by ID with base price calculation."""
        result = await self.db.execute(
            select(Hotel).where(Hotel.id == hotel_id, Hotel.is_active == True, Hotel.is_deleted == False)
        )
        hotel = result.scalar_one_or_none()
        if hotel:
            hotel = await self._enrich_hotel_with_base_price(hotel)
        return hotel

    async def _calculate_base_price(self, hotel_id: UUID) -> Optional[float]:
        """Calculate base price per night from minimum room price."""
        result = await self.db.execute(
            select(func.min(Room.price_per_night))
            .where(
                Room.hotel_id == hotel_id,
                Room.price_per_night.isnot(None),  # Only rooms with price set
                Room.is_deleted == False
            )
        )
        min_price = result.scalar_one_or_none()
        return min_price

    async def _enrich_hotel_with_base_price(self, hotel: Hotel) -> Hotel:
        """Enrich hotel with calculated base_price_per_night if null."""
        if hotel and hotel.base_price_per_night is None:
            calculated_price = await self._calculate_base_price(hotel.id)
            if calculated_price:
                hotel.base_price_per_night = calculated_price
        return hotel

    async def _enrich_hotels_with_base_prices(self, hotels: List[Hotel]) -> List[Hotel]:
        """Enrich multiple hotels with calculated base prices."""
        for hotel in hotels:
            await self._enrich_hotel_with_base_price(hotel)
        return hotels

    async def get_list(
        self,
        pagination: PaginationParams,
        search: Optional[str] = None,
        city: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_rating: Optional[float] = None,
        amenities: Optional[List[str]] = None,
        sort_by: Optional[str] = "recommended",
    ) -> tuple[List[Hotel], int]:
        """Get paginated list of hotels."""
        query = select(Hotel).where(Hotel.is_active == True, Hotel.is_deleted == False)

        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                or_(
                    func.lower(Hotel.name).ilike(search_pattern),
                    func.lower(Hotel.description).ilike(search_pattern),
                    func.lower(Hotel.short_description).ilike(search_pattern),
                    func.lower(Hotel.city).ilike(search_pattern),
                )
            )

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

        # Enrich hotels with calculated base prices
        hotels = await self._enrich_hotels_with_base_prices(list(hotels))

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
        check_out: str,
    ) -> bool:
        """Whether the room type has a unit free for the whole date range.

        Delegates to BookingService so this and the booking flow can never disagree.
        It previously returned True unconditionally, which told customers rooms were
        bookable when they were not.
        """
        from datetime import date as _date

        from app.services.booking_service import BookingService

        check_in_date = check_in if isinstance(check_in, _date) else _date.fromisoformat(str(check_in))
        check_out_date = check_out if isinstance(check_out, _date) else _date.fromisoformat(str(check_out))
        if check_out_date <= check_in_date:
            raise ValueError("check_out must be after check_in")

        return await BookingService(self.db).check_room_availability(
            room_id, check_in_date, check_out_date
        )
