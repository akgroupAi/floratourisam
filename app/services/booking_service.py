"""Booking service."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.booking import Booking
from app.schemas.booking import (
    BookingCancelRequest,
    BookingStatusUpdate,
    BookingUpdate,
    HotelBookingCreate,
    RestaurantBookingCreate,
)
from app.schemas.common import PaginationParams
from app.utils.enums import BookingStatus, BookingType
from app.utils.helpers import generate_reference_id

logger = get_logger(__name__)


class BookingService:
    """Service for booking operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, booking_id: UUID) -> Optional[Booking]:
        """Get booking by ID."""
        result = await self.db.execute(
            select(Booking).where(Booking.id == booking_id, Booking.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_by_reference(self, reference_number: str) -> Optional[Booking]:
        """Get booking by reference number."""
        result = await self.db.execute(
            select(Booking).where(
                Booking.reference_number == reference_number,
                Booking.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def get_list(
        self,
        pagination: PaginationParams,
        patient_id: Optional[UUID] = None,
        booking_type: Optional[BookingType] = None,
        status: Optional[BookingStatus] = None,
    ) -> tuple[List[Booking], int]:
        """Get paginated list of bookings."""
        query = select(Booking).where(Booking.is_deleted == False)

        if patient_id:
            query = query.where(Booking.patient_id == patient_id)
        if booking_type:
            query = query.where(Booking.booking_type == booking_type.value)
        if status:
            query = query.where(Booking.status == status.value)

        # Get count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        query = query.order_by(Booking.created_at.desc())
        query = query.offset(pagination.offset).limit(pagination.page_size)

        result = await self.db.execute(query)
        bookings = result.scalars().all()

        return list(bookings), total

    async def create_hotel_booking(
        self,
        patient_id: UUID,
        data: HotelBookingCreate,
        created_by: Optional[UUID] = None,
    ) -> Booking:
        """Create a hotel booking."""
        # Fetch room to get price
        from app.models.hotel import Room
        result = await self.db.execute(select(Room).where(Room.id == data.room_id))
        room = result.scalar_one_or_none()
        
        if not room:
            raise ValueError(f"Room with ID {data.room_id} not found")

        # Calculate nights and price
        nights = (data.check_out_date - data.check_in_date).days
        if nights < 1:
            nights = 1
            
        base_price = room.price_per_night * nights

        booking = Booking(
            patient_id=patient_id,
            booking_type=BookingType.HOTEL.value,
            reference_number=generate_reference_id("HTL"),
            hotel_room_id=data.room_id,
            check_in_date=data.check_in_date,
            check_out_date=data.check_out_date,
            booking_date=datetime.now(timezone.utc),
            guest_count=data.guest_count,
            guest_details=data.guest_details,
            base_price=base_price,
            taxes=base_price * 0.1,
            total_price=base_price * 1.1,
            special_requests=data.special_requests,
            notes=data.notes,
            status=BookingStatus.PENDING.value,
            created_by=created_by,
        )

        self.db.add(booking)
        await self.db.commit()
        await self.db.refresh(booking)

        logger.info("hotel_booking_created", booking_id=str(booking.id))

        return booking

    async def create_restaurant_booking(
        self,
        patient_id: UUID,
        data: RestaurantBookingCreate,
        created_by: Optional[UUID] = None,
    ) -> Booking:
        """Create a restaurant booking."""
        booking = Booking(
            patient_id=patient_id,
            booking_type=BookingType.RESTAURANT.value,
            reference_number=generate_reference_id("RST"),
            restaurant_id=data.restaurant_id,
            booking_date=datetime.now(timezone.utc),
            scheduled_time=datetime.combine(data.booking_date, data.booking_time),
            guest_count=data.guest_count,
            special_requests=data.special_requests or data.dietary_requirements,
            notes=data.notes,
            status=BookingStatus.PENDING.value,
            base_price=0.0,
            taxes=0.0,
            total_price=0.0,
            created_by=created_by,
        )

        self.db.add(booking)
        await self.db.commit()
        await self.db.refresh(booking)

        logger.info("restaurant_booking_created", booking_id=str(booking.id))

        return booking

    async def update(
        self,
        booking: Booking,
        data: BookingUpdate,
        updated_by: Optional[UUID] = None,
    ) -> Booking:
        """Update booking."""
        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(booking, field, value)

        booking.updated_by = updated_by
        booking.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(booking)

        return booking

    async def update_status(
        self,
        booking: Booking,
        data: BookingStatusUpdate,
        updated_by: UUID,
    ) -> Booking:
        """Update booking status."""
        booking.status = data.status.value
        if data.internal_notes:
            booking.internal_notes = data.internal_notes
        booking.updated_by = updated_by
        booking.updated_at = datetime.now(timezone.utc)

        if data.status == BookingStatus.CONFIRMED:
            booking.confirmed_at = datetime.now(timezone.utc)
            booking.confirmed_by = updated_by

        await self.db.commit()
        await self.db.refresh(booking)

        logger.info(
            "booking_status_updated",
            booking_id=str(booking.id),
            status=data.status.value,
        )

        return booking

    async def cancel(
        self,
        booking: Booking,
        data: BookingCancelRequest,
        cancelled_by: UUID,
    ) -> Booking:
        """Cancel a booking."""
        booking.status = BookingStatus.CANCELLED.value
        booking.cancelled_at = datetime.now(timezone.utc)
        booking.cancellation_reason = data.cancellation_reason
        booking.cancelled_by = cancelled_by

        # Calculate refund if applicable
        if booking.is_paid:
            booking.refund_amount = booking.total_price * 0.8  # 80% refund

        await self.db.commit()
        await self.db.refresh(booking)

        logger.info("booking_cancelled", booking_id=str(booking.id))

        return booking

    async def get_stats(
        self,
        patient_id: Optional[UUID] = None,
    ) -> dict:
        """Get booking statistics."""
        base_query = select(Booking).where(Booking.is_deleted == False)
        if patient_id:
            base_query = base_query.where(Booking.patient_id == patient_id)

        # Total bookings
        total_result = await self.db.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total_bookings = total_result.scalar() or 0

        # By status
        status_result = await self.db.execute(
            select(Booking.status, func.count())
            .where(Booking.is_deleted == False)
            .group_by(Booking.status)
        )
        bookings_by_status = {status: count for status, count in status_result.all()}

        # By type
        type_result = await self.db.execute(
            select(Booking.booking_type, func.count())
            .where(Booking.is_deleted == False)
            .group_by(Booking.booking_type)
        )
        bookings_by_type = {btype: count for btype, count in type_result.all()}

        # Total revenue
        revenue_result = await self.db.execute(
            select(func.sum(Booking.total_price))
            .where(Booking.is_deleted == False, Booking.is_paid == True)
        )
        total_revenue = revenue_result.scalar() or 0.0

        return {
            "total_bookings": total_bookings,
            "confirmed_bookings": bookings_by_status.get(BookingStatus.CONFIRMED.value, 0),
            "cancelled_bookings": bookings_by_status.get(BookingStatus.CANCELLED.value, 0),
            "pending_bookings": bookings_by_status.get(BookingStatus.PENDING.value, 0),
            "total_revenue": total_revenue,
            "bookings_by_type": bookings_by_type,
            "bookings_by_status": bookings_by_status,
        }
