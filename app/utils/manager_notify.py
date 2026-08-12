"""Notify the manager of the property a thing just happened at.

Managers previously learned about a booking only by going to look for it. These helpers
resolve a booking or review to its property's manager and push a notification.

Every function is best-effort: a notification failure must never roll back the booking
that triggered it.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.apartment import Apartment
from app.models.booking import Booking
from app.models.hotel import Hotel, Room
from app.models.restaurant import Restaurant
from app.utils.notifications import notify

logger = get_logger(__name__)


async def _manager_for_booking(db: AsyncSession, booking: Booking) -> Optional[UUID]:
    """The manager responsible for whichever property this booking belongs to."""
    try:
        if booking.hotel_room_id:
            return (
                await db.execute(
                    select(Hotel.manager_id)
                    .join(Room, Room.hotel_id == Hotel.id)
                    .where(Room.id == booking.hotel_room_id)
                )
            ).scalar_one_or_none()
        if booking.apartment_id:
            return (
                await db.execute(
                    select(Apartment.manager_id).where(Apartment.id == booking.apartment_id)
                )
            ).scalar_one_or_none()
        if booking.restaurant_id:
            return (
                await db.execute(
                    select(Restaurant.manager_id).where(
                        Restaurant.id == booking.restaurant_id
                    )
                )
            ).scalar_one_or_none()
    except Exception as exc:  # noqa: BLE001
        logger.error("manager_lookup_failed", booking_id=str(booking.id), error=str(exc))
    return None


async def notify_manager_new_booking(db: AsyncSession, booking: Booking) -> None:
    """Tell the property manager a booking has come in."""
    manager_id = await _manager_for_booking(db, booking)
    if not manager_id:
        return

    dates = ""
    if booking.check_in_date and booking.check_out_date:
        dates = f" for {booking.check_in_date} to {booking.check_out_date}"

    try:
        await notify(
            db=db,
            user_id=manager_id,
            title="New booking",
            message=(
                f"Booking {booking.reference_number}{dates} — "
                f"{booking.currency or ''} {booking.total_price:.2f}".strip()
            ),
            notification_type="booking_confirmed",
            entity_type="booking",
            entity_id=booking.id,
            action_url=f"/manager/bookings/{booking.id}",
            action_text="View booking",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "manager_booking_notification_failed",
            booking_id=str(booking.id),
            error=str(exc),
        )


async def notify_manager_cancellation(db: AsyncSession, booking: Booking) -> None:
    """Tell the property manager a booking was cancelled."""
    manager_id = await _manager_for_booking(db, booking)
    if not manager_id:
        return

    try:
        await notify(
            db=db,
            user_id=manager_id,
            title="Booking cancelled",
            message=(
                f"Booking {booking.reference_number} was cancelled"
                + (f": {booking.cancellation_reason}" if booking.cancellation_reason else "")
            ),
            notification_type="booking_cancelled",
            entity_type="booking",
            entity_id=booking.id,
            action_url=f"/manager/bookings/{booking.id}",
            action_text="View booking",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "manager_cancellation_notification_failed",
            booking_id=str(booking.id),
            error=str(exc),
        )


async def notify_manager_new_review(
    db: AsyncSession, entity_type: str, entity_id: UUID, rating: int, review_id: UUID
) -> None:
    """Tell the property manager about a new review, flagging the poor ones."""
    model = {"hotel": Hotel, "apartment": Apartment, "restaurant": Restaurant}.get(entity_type)
    if model is None:
        return

    try:
        manager_id = (
            await db.execute(select(model.manager_id).where(model.id == entity_id))
        ).scalar_one_or_none()
    except Exception as exc:  # noqa: BLE001
        logger.error("manager_lookup_failed", entity_id=str(entity_id), error=str(exc))
        return

    if not manager_id:
        return

    poor = rating <= 3
    try:
        await notify(
            db=db,
            user_id=manager_id,
            title="Negative review" if poor else "New review",
            message=(
                f"Your property received a {rating}-star review"
                + (" — worth a response" if poor else "")
            ),
            notification_type="system",
            entity_type="review",
            entity_id=review_id,
            action_url="/manager/reviews?unanswered_only=true",
            action_text="Respond",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "manager_review_notification_failed", review_id=str(review_id), error=str(exc)
        )
