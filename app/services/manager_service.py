"""Manager portal service — everything scoped to the caller's own properties.

Reads and writes here always go through a ManagerScope, so a manager can only ever
touch the hotels, apartments, and restaurants assigned to them.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.manager_scope import ManagerScope
from app.models.apartment import Apartment
from app.models.booking import Booking
from app.models.hotel import Hotel, Room
from app.models.restaurant import MenuItem, Restaurant
from app.models.review import Review
from app.schemas.common import PaginationParams
from app.utils.booking_helpers import OCCUPIED_BOOKING_STATUSES
from app.utils.enums import BookingStatus

logger = get_logger(__name__)


class ManagerService:
    """Property-scoped operations for hotel, apartment, and restaurant managers."""

    def __init__(self, db: AsyncSession, scope: ManagerScope):
        self.db = db
        self.scope = scope

    # ── Properties ────────────────────────────────────────────

    async def my_properties(self) -> dict:
        """Every property the caller manages, grouped by type."""
        hotels, apartments, restaurants = [], [], []

        if self.scope.is_admin or self.scope.hotel_ids:
            query = select(Hotel).where(Hotel.is_deleted == False)
            if not self.scope.is_admin:
                query = query.where(Hotel.id.in_(self.scope.hotel_ids))
            hotels = [
                {
                    "id": h.id, "name": h.name, "city": h.city, "country": h.country,
                    "is_active": h.is_active, "rating": h.rating,
                    "image_url": h.cover_image_url,
                }
                for h in (await self.db.execute(query)).scalars().all()
            ]

        if self.scope.is_admin or self.scope.apartment_ids:
            query = select(Apartment).where(Apartment.is_deleted == False)
            if not self.scope.is_admin:
                query = query.where(Apartment.id.in_(self.scope.apartment_ids))
            apartments = [
                {
                    "id": a.id, "name": a.name, "city": a.city, "country": a.country,
                    "is_active": a.is_active, "rating": a.rating,
                    "image_url": a.cover_image_url,
                }
                for a in (await self.db.execute(query)).scalars().all()
            ]

        if self.scope.is_admin or self.scope.restaurant_ids:
            query = select(Restaurant).where(Restaurant.is_deleted == False)
            if not self.scope.is_admin:
                query = query.where(Restaurant.id.in_(self.scope.restaurant_ids))
            restaurants = [
                {
                    "id": r.id, "name": r.name, "city": r.city, "country": r.country,
                    "is_active": r.is_active, "rating": r.rating,
                    "image_url": r.cover_image_url,
                }
                for r in (await self.db.execute(query)).scalars().all()
            ]

        return {
            "role": self.scope.role,
            "hotels": hotels,
            "apartments": apartments,
            "restaurants": restaurants,
            "total": len(hotels) + len(apartments) + len(restaurants),
        }

    # ── Dashboard ─────────────────────────────────────────────

    async def dashboard(self) -> dict:
        """Today at my properties: arrivals, departures, in-house, revenue."""
        today = datetime.now(timezone.utc).date()
        scope_clause = self.scope.booking_filter(Booking)
        base = [Booking.is_deleted == False]
        if scope_clause is not None:
            base.append(scope_clause)

        async def count(*extra) -> int:
            return (
                await self.db.execute(
                    select(func.count(Booking.id)).where(*base, *extra)
                )
            ).scalar() or 0

        arrivals = await count(
            Booking.check_in_date == today,
            Booking.status.in_(OCCUPIED_BOOKING_STATUSES),
        )
        departures = await count(
            Booking.check_out_date == today,
            Booking.status.in_(OCCUPIED_BOOKING_STATUSES),
        )
        in_house = await count(
            Booking.check_in_date <= today,
            Booking.check_out_date > today,
            Booking.status.in_(OCCUPIED_BOOKING_STATUSES),
        )
        pending = await count(Booking.status == BookingStatus.PENDING.value)
        unpaid = await count(
            Booking.is_paid == False,
            Booking.status.in_(OCCUPIED_BOOKING_STATUSES),
        )

        month_start = today.replace(day=1)
        revenue_month = float(
            (
                await self.db.execute(
                    select(func.coalesce(func.sum(Booking.total_price), 0.0)).where(
                        *base,
                        Booking.status.in_(OCCUPIED_BOOKING_STATUSES),
                        Booking.booking_date >= datetime(
                            month_start.year, month_start.month, month_start.day,
                            tzinfo=timezone.utc,
                        ),
                    )
                )
            ).scalar()
            or 0
        )
        revenue_today = float(
            (
                await self.db.execute(
                    select(func.coalesce(func.sum(Booking.total_price), 0.0)).where(
                        *base,
                        Booking.status.in_(OCCUPIED_BOOKING_STATUSES),
                        func.date(Booking.booking_date) == today,
                    )
                )
            ).scalar()
            or 0
        )

        cancellations_week = await count(
            Booking.status == BookingStatus.CANCELLED.value,
            Booking.cancelled_at >= datetime.now(timezone.utc) - timedelta(days=7),
        )

        return {
            "date": today,
            "arrivals_today": arrivals,
            "departures_today": departures,
            "in_house": in_house,
            "pending_bookings": pending,
            "unpaid_bookings": unpaid,
            "cancellations_last_7d": cancellations_week,
            "revenue_today": round(revenue_today, 2),
            "revenue_this_month": round(revenue_month, 2),
            "property_count": (
                len(self.scope.hotel_ids)
                + len(self.scope.apartment_ids)
                + len(self.scope.restaurant_ids)
            ),
        }

    # ── Rooms ─────────────────────────────────────────────────

    async def list_rooms(self, hotel_id: Optional[UUID] = None) -> List[Room]:
        """Rooms across my hotels, or one of them."""
        query = select(Room).where(Room.is_deleted == False)
        if hotel_id:
            self.scope.assert_hotel(hotel_id)
            query = query.where(Room.hotel_id == hotel_id)
        else:
            room_clause = self.scope.room_filter(Room.id)
            if room_clause is not None:
                query = query.where(room_clause)
        return list((await self.db.execute(query.order_by(Room.room_type))).scalars().all())

    async def get_room(self, room_id: UUID) -> Room:
        """Fetch a room and confirm the caller manages its hotel."""
        room = (
            await self.db.execute(
                select(Room).where(Room.id == room_id, Room.is_deleted == False)
            )
        ).scalar_one_or_none()
        if not room:
            raise ValueError("Room not found")
        self.scope.assert_hotel(room.hotel_id)
        return room

    # ── Bookings ──────────────────────────────────────────────

    async def list_bookings(
        self,
        pagination: PaginationParams,
        status: Optional[str] = None,
        booking_type: Optional[str] = None,
        from_date=None,
        to_date=None,
        search: Optional[str] = None,
    ) -> Tuple[List[Booking], int]:
        """Bookings at my properties."""
        filters = [Booking.is_deleted == False]
        scope_clause = self.scope.booking_filter(Booking)
        if scope_clause is not None:
            filters.append(scope_clause)
        if status:
            filters.append(Booking.status == status)
        if booking_type:
            filters.append(Booking.booking_type == booking_type)
        if from_date:
            filters.append(Booking.check_in_date >= from_date)
        if to_date:
            filters.append(Booking.check_in_date <= to_date)
        if search:
            filters.append(Booking.reference_number.ilike(f"%{search}%"))

        total = (
            await self.db.execute(
                select(func.count()).select_from(
                    select(Booking.id).where(*filters).subquery()
                )
            )
        ).scalar() or 0

        rows = (
            await self.db.execute(
                select(Booking)
                .where(*filters)
                .order_by(Booking.created_at.desc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        ).scalars().all()
        return list(rows), total

    async def get_booking(self, booking_id: UUID) -> Booking:
        """Fetch a booking and confirm it belongs to one of my properties."""
        filters = [Booking.id == booking_id, Booking.is_deleted == False]
        scope_clause = self.scope.booking_filter(Booking)
        if scope_clause is not None:
            filters.append(scope_clause)

        booking = (
            await self.db.execute(select(Booking).where(*filters))
        ).scalar_one_or_none()
        if not booking:
            # Deliberately identical whether it does not exist or is not theirs.
            raise ValueError("Booking not found at one of your properties")
        return booking

    # ── Menu & daily stock ────────────────────────────────────

    @staticmethod
    def remaining_stock(item: MenuItem, today=None) -> Optional[int]:
        """Units left today, or None when the item is unlimited.

        `sold_today` is only meaningful for `stock_date`; on any other day the counter
        is stale and the item is treated as fully restocked. That avoids needing a
        nightly reset job — the date comparison is the reset.
        """
        if item.daily_quantity is None:
            return None
        today = today or datetime.now(timezone.utc).date()
        sold = item.sold_today if item.stock_date == today else 0
        return max(item.daily_quantity - sold, 0)

    @classmethod
    def is_sold_out(cls, item: MenuItem, today=None) -> bool:
        remaining = cls.remaining_stock(item, today)
        return remaining is not None and remaining <= 0

    async def list_menu(
        self, restaurant_id: Optional[UUID] = None, sold_out_only: bool = False
    ) -> List[dict]:
        """Menu items at my restaurants, with today's stock resolved."""
        query = select(MenuItem).where(MenuItem.is_deleted == False)
        if restaurant_id:
            self.scope.assert_restaurant(restaurant_id)
            query = query.where(MenuItem.restaurant_id == restaurant_id)
        else:
            clause = self.scope.restaurant_filter(MenuItem.restaurant_id)
            if clause is not None:
                query = query.where(clause)

        today = datetime.now(timezone.utc).date()
        items = []
        for item in (await self.db.execute(query.order_by(MenuItem.display_order))).scalars().all():
            remaining = self.remaining_stock(item, today)
            sold_out = remaining is not None and remaining <= 0
            if sold_out_only and not sold_out:
                continue
            items.append({
                "id": item.id,
                "restaurant_id": item.restaurant_id,
                "name": item.name,
                "category": item.category,
                "price": item.price,
                "currency": item.currency,
                "is_available": item.is_available,
                "available_for": item.available_for or [],
                "daily_quantity": item.daily_quantity,
                "sold_today": item.sold_today if item.stock_date == today else 0,
                "remaining_today": remaining,
                "is_sold_out": sold_out,
                "image_url": item.image_url,
            })
        return items

    async def get_menu_item(self, item_id: UUID) -> MenuItem:
        item = (
            await self.db.execute(
                select(MenuItem).where(MenuItem.id == item_id, MenuItem.is_deleted == False)
            )
        ).scalar_one_or_none()
        if not item:
            raise ValueError("Menu item not found")
        self.scope.assert_restaurant(item.restaurant_id)
        return item

    async def set_menu_stock(
        self,
        item_id: UUID,
        updated_by: UUID,
        daily_quantity: Optional[int] = None,
        unlimited: bool = False,
        sold_today: Optional[int] = None,
        is_available: Optional[bool] = None,
        reset: bool = False,
    ) -> MenuItem:
        """Set today's stock for one item.

        `unlimited=True` clears the quantity. `reset=True` puts the sold counter back to
        zero — the "we've restocked" button.
        """
        item = await self.get_menu_item(item_id)
        today = datetime.now(timezone.utc).date()

        if unlimited:
            item.daily_quantity = None
        elif daily_quantity is not None:
            if daily_quantity < 0:
                raise ValueError("daily_quantity cannot be negative")
            item.daily_quantity = daily_quantity

        if reset:
            item.sold_today = 0
            item.stock_date = today
        elif sold_today is not None:
            if sold_today < 0:
                raise ValueError("sold_today cannot be negative")
            item.sold_today = sold_today
            item.stock_date = today

        if is_available is not None:
            item.is_available = is_available

        item.updated_by = updated_by
        await self.db.commit()
        await self.db.refresh(item)
        logger.info(
            "menu_stock_updated",
            item_id=str(item_id),
            daily_quantity=item.daily_quantity,
            sold_today=item.sold_today,
            updated_by=str(updated_by),
        )
        return item

    # ── Reviews ───────────────────────────────────────────────

    async def list_reviews(
        self,
        pagination: PaginationParams,
        unanswered_only: bool = False,
        max_rating: Optional[int] = None,
    ) -> Tuple[List[Review], int]:
        """Reviews of my properties, newest first."""
        entity_clauses = []
        if self.scope.is_admin:
            entity_clauses = None
        else:
            if self.scope.hotel_ids:
                entity_clauses.append(
                    and_(Review.entity_type == "hotel", Review.entity_id.in_(self.scope.hotel_ids))
                )
            if self.scope.apartment_ids:
                entity_clauses.append(
                    and_(
                        Review.entity_type == "apartment",
                        Review.entity_id.in_(self.scope.apartment_ids),
                    )
                )
            if self.scope.restaurant_ids:
                entity_clauses.append(
                    and_(
                        Review.entity_type == "restaurant",
                        Review.entity_id.in_(self.scope.restaurant_ids),
                    )
                )

        filters = [Review.is_deleted == False]
        if entity_clauses is not None:
            filters.append(or_(*entity_clauses) if entity_clauses else Review.id.is_(None))
        if unanswered_only:
            filters.append(
                or_(Review.response_text.is_(None), Review.response_text == "")
            )
        if max_rating is not None:
            filters.append(Review.rating <= max_rating)

        total = (
            await self.db.execute(
                select(func.count()).select_from(
                    select(Review.id).where(*filters).subquery()
                )
            )
        ).scalar() or 0

        rows = (
            await self.db.execute(
                select(Review)
                .where(*filters)
                .order_by(Review.created_at.desc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        ).scalars().all()
        return list(rows), total
