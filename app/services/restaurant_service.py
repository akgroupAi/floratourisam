"""Restaurant service."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import Float, String, cast, func, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.restaurant import Restaurant, MenuItem
from app.schemas.common import PaginationParams

logger = get_logger(__name__)

# Price range ordering for sort
PRICE_RANGE_ORDER = {"$": 1, "$$": 2, "$$$": 3, "$$$$": 4}


class RestaurantService:
    """Service for restaurant operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, restaurant_id: UUID) -> Optional[Restaurant]:
        """Get restaurant by ID."""
        result = await self.db.execute(
            select(Restaurant).where(Restaurant.id == restaurant_id, Restaurant.is_active == True, Restaurant.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_list_minimal(self) -> List[Restaurant]:
        """Get minimal list of all active restaurants."""
        query = select(Restaurant).where(Restaurant.is_active == True, Restaurant.is_deleted == False).order_by(Restaurant.name.asc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_list(
        self,
        pagination: PaginationParams,
        city: Optional[str] = None,
        cuisine_type: Optional[str] = None,
        min_rating: Optional[float] = None,
        dietary_options: Optional[List[str]] = None,
        price_range: Optional[str] = None,
        sort_by: Optional[str] = "recommended",
        user_lat: Optional[float] = None,
        user_lng: Optional[float] = None,
    ) -> tuple[List[Restaurant], int]:
        """Get paginated list of restaurants with filters and sorting."""
        query = select(Restaurant).where(Restaurant.is_active == True, Restaurant.is_deleted == False)

        if city:
            query = query.where(func.lower(Restaurant.city) == city.lower())

        if cuisine_type:
            query = query.where(
                Restaurant.cuisine_types.contains(cast([cuisine_type], ARRAY(String)))
            )

        if min_rating is not None:
            query = query.where(Restaurant.rating >= min_rating)

        if dietary_options:
            for option in dietary_options:
                query = query.where(
                    Restaurant.dietary_options.contains(cast([option], ARRAY(String)))
                )

        if price_range:
            query = query.where(Restaurant.price_range == price_range)

        # Get count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting
        if sort_by == "highest_rated":
            query = query.order_by(Restaurant.rating.desc().nullslast())
        elif sort_by == "most_reviews":
            query = query.order_by(Restaurant.total_reviews.desc())
        elif sort_by == "nearest_first" and user_lat is not None and user_lng is not None:
            # Approximate distance using Euclidean on lat/lng
            distance = func.sqrt(
                func.pow(Restaurant.latitude - user_lat, 2)
                + func.pow(Restaurant.longitude - user_lng, 2)
            )
            query = query.order_by(distance.asc().nullslast())
        else:
            # recommended: featured first, then rating, then reviews
            query = query.order_by(
                Restaurant.is_featured.desc(),
                Restaurant.rating.desc().nullslast(),
                Restaurant.total_reviews.desc(),
            )

        # Apply pagination
        query = query.offset(pagination.offset).limit(pagination.page_size)

        result = await self.db.execute(query)
        restaurants = result.scalars().all()

        return list(restaurants), total

    async def get_menu(self, restaurant_id: UUID) -> List[MenuItem]:
        """Get menu for a restaurant."""
        result = await self.db.execute(
            select(MenuItem).where(MenuItem.restaurant_id == restaurant_id, MenuItem.is_available == True, MenuItem.is_deleted == False)
            .order_by(MenuItem.category, MenuItem.display_order)
        )
        return list(result.scalars().all())
