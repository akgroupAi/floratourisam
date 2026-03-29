"""Restaurant service."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.restaurant import Restaurant, MenuItem
from app.schemas.common import PaginationParams

logger = get_logger(__name__)


class RestaurantService:
    """Service for restaurant operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, restaurant_id: UUID) -> Optional[Restaurant]:
        """Get restaurant by ID."""
        result = await self.db.execute(
            select(Restaurant).where(Restaurant.id == restaurant_id, Restaurant.is_active == True)
        )
        return result.scalar_one_or_none()

    async def get_list_minimal(self) -> List[Restaurant]:
        """Get minimal list of all active restaurants."""
        query = select(Restaurant).where(Restaurant.is_active == True).order_by(Restaurant.name.asc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_list(
        self,
        pagination: PaginationParams,
        city: Optional[str] = None,
    ) -> tuple[List[Restaurant], int]:
        """Get paginated list of restaurants."""
        query = select(Restaurant).where(Restaurant.is_active == True)

        if city:
            query = query.where(func.lower(Restaurant.city) == city.lower())

        # Get count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        query = query.order_by(Restaurant.name.asc())
        query = query.offset(pagination.offset).limit(pagination.page_size)

        result = await self.db.execute(query)
        restaurants = result.scalars().all()

        return list(restaurants), total

    async def get_menu(self, restaurant_id: UUID) -> List[MenuItem]:
        """Get menu for a restaurant."""
        result = await self.db.execute(
            select(MenuItem).where(MenuItem.restaurant_id == restaurant_id, MenuItem.is_available == True)
            .order_by(MenuItem.category, MenuItem.display_order)
        )
        return list(result.scalars().all())
