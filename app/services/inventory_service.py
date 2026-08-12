"""Inventory overview, alerts, and bulk operations across properties."""

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.apartment import Apartment, ApartmentAvailability
from app.models.booking import Booking
from app.models.hotel import Hotel, Room, RoomAvailability
from app.models.restaurant import MenuItem, Restaurant
from app.utils.booking_helpers import OCCUPIED_BOOKING_STATUSES

logger = get_logger(__name__)

# A room priced for fewer than this many days ahead is flagged; roughly a month of
# forward visibility is the minimum for a property that takes advance bookings.
CALENDAR_HORIZON_DAYS = 30


class InventoryService:
    """Cross-property inventory reporting and bulk edits."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Summary ───────────────────────────────────────────────

    async def summary(self) -> dict:
        """Counts of what exists and how much of it is sellable."""
        async def scalar(stmt) -> int:
            return (await self.db.execute(stmt)).scalar() or 0

        hotels = await scalar(
            select(func.count(Hotel.id)).where(Hotel.is_deleted == False)
        )
        hotels_active = await scalar(
            select(func.count(Hotel.id)).where(
                Hotel.is_deleted == False, Hotel.is_active == True
            )
        )
        room_types = await scalar(
            select(func.count(Room.id)).where(Room.is_deleted == False)
        )
        room_units = await scalar(
            select(func.coalesce(func.sum(Room.total_rooms), 0)).where(
                Room.is_deleted == False, Room.is_available == True
            )
        )
        apartments = await scalar(
            select(func.count(Apartment.id)).where(Apartment.is_deleted == False)
        )
        apartments_active = await scalar(
            select(func.count(Apartment.id)).where(
                Apartment.is_deleted == False,
                Apartment.is_active == True,
                Apartment.is_available == True,
            )
        )
        restaurants = await scalar(
            select(func.count(Restaurant.id)).where(Restaurant.is_deleted == False)
        )
        menu_items = await scalar(
            select(func.count(MenuItem.id)).where(MenuItem.is_deleted == False)
        )
        menu_available = await scalar(
            select(func.count(MenuItem.id)).where(
                MenuItem.is_deleted == False, MenuItem.is_available == True
            )
        )

        today = datetime.now(timezone.utc).date()
        blocked_room_nights = await scalar(
            select(func.count(RoomAvailability.id)).where(
                RoomAvailability.is_deleted == False,
                RoomAvailability.is_blocked == True,
                RoomAvailability.date >= today,
            )
        )
        blocked_apartment_nights = await scalar(
            select(func.count(ApartmentAvailability.id)).where(
                ApartmentAvailability.is_deleted == False,
                ApartmentAvailability.is_blocked == True,
                ApartmentAvailability.date >= today,
            )
        )

        return {
            "hotels": hotels,
            "hotels_active": hotels_active,
            "room_types": room_types,
            "room_units_sellable": room_units,
            "apartments": apartments,
            "apartments_active": apartments_active,
            "restaurants": restaurants,
            "menu_items": menu_items,
            "menu_items_available": menu_available,
            "blocked_room_nights_ahead": blocked_room_nights,
            "blocked_apartment_nights_ahead": blocked_apartment_nights,
        }

    # ── Occupancy ─────────────────────────────────────────────

    async def occupancy(self, start: date, end: date) -> dict:
        """Occupancy across the window, plus a per-hotel breakdown.

        Capacity is room units × nights. Sold is booked room-nights. Apartments are
        counted separately since one apartment is one unit.
        """
        nights = max((end - start).days, 1)

        room_units = (
            await self.db.execute(
                select(func.coalesce(func.sum(Room.total_rooms), 0)).where(
                    Room.is_deleted == False, Room.is_available == True
                )
            )
        ).scalar() or 0

        booked_rows = (
            await self.db.execute(
                select(Booking.check_in_date, Booking.check_out_date).where(
                    Booking.is_deleted == False,
                    Booking.hotel_room_id.isnot(None),
                    Booking.status.in_(OCCUPIED_BOOKING_STATUSES),
                    Booking.check_in_date.isnot(None),
                    Booking.check_out_date.isnot(None),
                    Booking.check_in_date < end,
                    Booking.check_out_date > start,
                )
            )
        ).all()
        # Only the nights inside the window count towards occupancy.
        room_nights_sold = sum(
            max((min(co, end) - max(ci, start)).days, 0) for ci, co in booked_rows
        )

        capacity = room_units * nights

        per_hotel = []
        hotel_rows = (
            await self.db.execute(
                select(Hotel.id, Hotel.name, func.coalesce(func.sum(Room.total_rooms), 0))
                .outerjoin(Room, and_(Room.hotel_id == Hotel.id, Room.is_deleted == False))
                .where(Hotel.is_deleted == False)
                .group_by(Hotel.id, Hotel.name)
            )
        ).all()

        for hotel_id, name, units in hotel_rows:
            rows = (
                await self.db.execute(
                    select(Booking.check_in_date, Booking.check_out_date)
                    .where(
                        Booking.is_deleted == False,
                        Booking.status.in_(OCCUPIED_BOOKING_STATUSES),
                        Booking.check_in_date.isnot(None),
                        Booking.check_out_date.isnot(None),
                        Booking.check_in_date < end,
                        Booking.check_out_date > start,
                        Booking.hotel_room_id.in_(
                            select(Room.id).where(Room.hotel_id == hotel_id)
                        ),
                    )
                )
            ).all()
            sold = sum(max((min(co, end) - max(ci, start)).days, 0) for ci, co in rows)
            hotel_capacity = (units or 0) * nights
            per_hotel.append({
                "hotel_id": str(hotel_id),
                "name": name,
                "room_units": units or 0,
                "capacity_nights": hotel_capacity,
                "sold_nights": sold,
                "occupancy_percent": round(sold / hotel_capacity * 100, 1)
                if hotel_capacity
                else 0.0,
            })

        return {
            "start_date": start,
            "end_date": end,
            "nights": nights,
            "room_units": room_units,
            "capacity_nights": capacity,
            "sold_nights": room_nights_sold,
            "occupancy_percent": round(room_nights_sold / capacity * 100, 1)
            if capacity
            else 0.0,
            "by_hotel": sorted(per_hotel, key=lambda h: h["occupancy_percent"], reverse=True),
        }

    # ── Alerts ────────────────────────────────────────────────

    async def alerts(self) -> dict:
        """Concrete, actionable inventory problems — not general statistics."""
        today = datetime.now(timezone.utc).date()
        horizon = today + timedelta(days=CALENDAR_HORIZON_DAYS)
        alerts: List[dict] = []

        # Room types with no sellable units or no price.
        for room, hotel_name in (
            await self.db.execute(
                select(Room, Hotel.name)
                .join(Hotel, Room.hotel_id == Hotel.id)
                .where(Room.is_deleted == False, Room.is_available == True)
            )
        ).all():
            if not room.total_rooms:
                alerts.append({
                    "severity": "high",
                    "type": "room_no_units",
                    "message": f"'{room.room_type}' at {hotel_name} is on sale with total_rooms = 0",
                    "entity_type": "room",
                    "entity_id": str(room.id),
                })
            if not room.price_per_night:
                alerts.append({
                    "severity": "high",
                    "type": "room_no_price",
                    "message": f"'{room.room_type}' at {hotel_name} has no price set",
                    "entity_type": "room",
                    "entity_id": str(room.id),
                })

        # Rooms with no calendar coverage in the next month. They still sell at the
        # default rate, so this is a warning rather than an error.
        priced_room_ids = set(
            (
                await self.db.execute(
                    select(RoomAvailability.room_id)
                    .where(
                        RoomAvailability.is_deleted == False,
                        RoomAvailability.date >= today,
                        RoomAvailability.date < horizon,
                    )
                    .distinct()
                )
            )
            .scalars()
            .all()
        )
        for room_id, room_type, hotel_name in (
            await self.db.execute(
                select(Room.id, Room.room_type, Hotel.name)
                .join(Hotel, Room.hotel_id == Hotel.id)
                .where(Room.is_deleted == False, Room.is_available == True)
            )
        ).all():
            if room_id not in priced_room_ids:
                alerts.append({
                    "severity": "medium",
                    "type": "room_calendar_gap",
                    "message": (
                        f"'{room_type}' at {hotel_name} has no calendar entries for the "
                        f"next {CALENDAR_HORIZON_DAYS} days — selling at default rates"
                    ),
                    "entity_type": "room",
                    "entity_id": str(room_id),
                })

        # Menu items on sale at an inactive restaurant.
        for item_id, item_name, restaurant_name in (
            await self.db.execute(
                select(MenuItem.id, MenuItem.name, Restaurant.name)
                .join(Restaurant, MenuItem.restaurant_id == Restaurant.id)
                .where(
                    MenuItem.is_deleted == False,
                    MenuItem.is_available == True,
                    Restaurant.is_active == False,
                )
            )
        ).all():
            alerts.append({
                "severity": "medium",
                "type": "menu_item_at_inactive_restaurant",
                "message": f"'{item_name}' is available but {restaurant_name} is inactive",
                "entity_type": "menu_item",
                "entity_id": str(item_id),
            })

        # Items that have sold out today.
        for item_id, item_name, restaurant_name in (
            await self.db.execute(
                select(MenuItem.id, MenuItem.name, Restaurant.name)
                .join(Restaurant, MenuItem.restaurant_id == Restaurant.id)
                .where(
                    MenuItem.is_deleted == False,
                    MenuItem.is_available == True,
                    MenuItem.daily_quantity.isnot(None),
                    MenuItem.stock_date == today,
                    MenuItem.sold_today >= MenuItem.daily_quantity,
                )
            )
        ).all():
            alerts.append({
                "severity": "low",
                "type": "menu_item_sold_out",
                "message": f"'{item_name}' at {restaurant_name} has sold out today",
                "entity_type": "menu_item",
                "entity_id": str(item_id),
            })

        # Apartments on sale with no price at all.
        for apt_id, name in (
            await self.db.execute(
                select(Apartment.id, Apartment.name).where(
                    Apartment.is_deleted == False,
                    Apartment.is_active == True,
                    Apartment.price_per_night.is_(None),
                    Apartment.price_per_week.is_(None),
                    Apartment.price_per_month.is_(None),
                )
            )
        ).all():
            alerts.append({
                "severity": "high",
                "type": "apartment_no_price",
                "message": f"'{name}' is active but has no pricing configured — it cannot be booked",
                "entity_type": "apartment",
                "entity_id": str(apt_id),
            })

        by_severity = {"high": 0, "medium": 0, "low": 0}
        for alert in alerts:
            by_severity[alert["severity"]] += 1

        return {
            "total": len(alerts),
            "by_severity": by_severity,
            "alerts": sorted(
                alerts, key=lambda a: {"high": 0, "medium": 1, "low": 2}[a["severity"]]
            ),
        }

    # ── Bulk operations ───────────────────────────────────────

    async def bulk_room_pricing(
        self,
        start: date,
        end: date,
        updated_by: UUID,
        hotel_ids: Optional[List[UUID]] = None,
        room_ids: Optional[List[UUID]] = None,
        city: Optional[str] = None,
        percent_change: Optional[float] = None,
        set_price: Optional[float] = None,
        weekdays: Optional[List[int]] = None,
        dry_run: bool = True,
    ) -> dict:
        """Apply a price change across many rooms at once.

        Defaults to `dry_run=True`. A mistyped percentage across a city is expensive, so
        the caller has to ask for the write explicitly.
        """
        if end <= start:
            raise ValueError("end date must be after start date")
        if percent_change is None and set_price is None:
            raise ValueError("Provide percent_change or set_price")
        if percent_change is not None and set_price is not None:
            raise ValueError("Provide only one of percent_change or set_price")
        if set_price is not None and set_price < 0:
            raise ValueError("set_price cannot be negative")
        if percent_change is not None and percent_change < -100:
            raise ValueError("percent_change cannot take a price below zero")

        query = (
            select(Room, Hotel.name)
            .join(Hotel, Room.hotel_id == Hotel.id)
            .where(Room.is_deleted == False)
        )
        if room_ids:
            query = query.where(Room.id.in_(room_ids))
        if hotel_ids:
            query = query.where(Room.hotel_id.in_(hotel_ids))
        if city:
            query = query.where(Hotel.city.ilike(f"%{city}%"))

        rooms = (await self.db.execute(query)).all()
        if not rooms:
            return {
                "dry_run": dry_run, "rooms_matched": 0, "nights_affected": 0, "changes": []
            }

        from app.services.booking_service import BookingService

        booking_service = BookingService(self.db)
        changes = []
        nights_affected = 0

        for room, hotel_name in rooms:
            current = room.price_per_night or 0.0
            new_price = (
                round(set_price, 2)
                if set_price is not None
                else round(current * (1 + percent_change / 100), 2)
            )
            night_count = sum(
                1
                for offset in range((end - start).days)
                if weekdays is None or (start + timedelta(days=offset)).weekday() in weekdays
            )
            changes.append({
                "room_id": str(room.id),
                "room_type": room.room_type,
                "hotel_name": hotel_name,
                "current_price": current,
                "new_price": new_price,
                "nights": night_count,
            })
            nights_affected += night_count

            if not dry_run:
                await booking_service.set_room_calendar(
                    room_id=room.id,
                    start=start,
                    end=end,
                    updated_by=updated_by,
                    price=new_price,
                    weekdays=weekdays,
                )

        if not dry_run:
            logger.info(
                "bulk_room_pricing_applied",
                rooms=len(changes),
                nights=nights_affected,
                updated_by=str(updated_by),
            )

        return {
            "dry_run": dry_run,
            "rooms_matched": len(changes),
            "nights_affected": nights_affected,
            "changes": changes,
        }

    async def bulk_room_availability(
        self,
        start: date,
        end: date,
        updated_by: UUID,
        is_blocked: bool,
        hotel_ids: Optional[List[UUID]] = None,
        room_ids: Optional[List[UUID]] = None,
        city: Optional[str] = None,
        notes: Optional[str] = None,
        dry_run: bool = True,
    ) -> dict:
        """Block or reopen a date range across many rooms."""
        if end <= start:
            raise ValueError("end date must be after start date")

        query = (
            select(Room, Hotel.name)
            .join(Hotel, Room.hotel_id == Hotel.id)
            .where(Room.is_deleted == False)
        )
        if room_ids:
            query = query.where(Room.id.in_(room_ids))
        if hotel_ids:
            query = query.where(Room.hotel_id.in_(hotel_ids))
        if city:
            query = query.where(Hotel.city.ilike(f"%{city}%"))

        rooms = (await self.db.execute(query)).all()
        nights = (end - start).days

        if not dry_run and rooms:
            from app.services.booking_service import BookingService

            booking_service = BookingService(self.db)
            for room, _ in rooms:
                await booking_service.set_room_calendar(
                    room_id=room.id,
                    start=start,
                    end=end,
                    updated_by=updated_by,
                    is_blocked=is_blocked,
                    notes=notes,
                )
            logger.info(
                "bulk_room_availability_applied",
                rooms=len(rooms),
                is_blocked=is_blocked,
                updated_by=str(updated_by),
            )

        return {
            "dry_run": dry_run,
            "rooms_matched": len(rooms),
            "nights_affected": len(rooms) * nights,
            "is_blocked": is_blocked,
            "changes": [
                {"room_id": str(r.id), "room_type": r.room_type, "hotel_name": h, "nights": nights}
                for r, h in rooms
            ],
        }
