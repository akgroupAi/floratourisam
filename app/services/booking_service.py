"""Booking service.

Handles hotel, apartment, and restaurant bookings:
- Room/apartment availability checking against RoomAvailability calendar
- MealBooking record creation for restaurant pre-orders
- Confirmation emails for all booking types
"""

from datetime import date, datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select, cast, Date, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.booking import Booking
from app.models.hotel import Room, RoomAvailability
from app.models.apartment import Apartment
from app.models.restaurant import MealBooking, MenuItem, Restaurant
from app.models.user import User
from app.schemas.booking import (
    ApartmentBookingCreate,
    BookingCancelRequest,
    BookingListResponse,
    BookingStatusUpdate,
    BookingUpdate,
    HotelBookingCreate,
    RestaurantBookingCreate,
    AdminBookingKPIs,
    AdminBookingListItem,
    AdminBookingDashboardResponse,
    AdminBookingDetailResponse,
    BookingTimelineItem,
    AdminBookingUpdate,
    BookingReportSummary,
    KPITrend,
    PropertyBooking,
)
from app.schemas.common import PaginationParams
from app.utils.email_sender import (
    render_apartment_booking_confirmation_html,
    render_hotel_booking_confirmation_html,
    render_restaurant_booking_confirmation_html,
    send_email,
)
from app.utils.enums import BookingStatus, BookingType
from app.utils.helpers import generate_reference_id
from app.utils.notifications import notify
from sqlalchemy.orm import selectinload, joinedload

logger = get_logger(__name__)


class BookingService:
    """Service for all booking types."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_by_id(self, booking_id: UUID) -> Optional[Booking]:
        result = await self.db.execute(
            select(Booking).where(Booking.id == booking_id, Booking.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_by_reference(self, reference_number: str) -> Optional[Booking]:
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
    ) -> tuple[List[BookingListResponse], int]:
        from app.models.hotel import Hotel, Room
        from app.models.apartment import Apartment
        from app.models.restaurant import Restaurant

        query = select(Booking).where(Booking.is_deleted == False)

        if patient_id:
            query = query.where(Booking.patient_id == patient_id)
        if booking_type:
            query = query.where(Booking.booking_type == booking_type.value)
        if status:
            query = query.where(Booking.status == status.value)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = (
            query.order_by(Booking.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
        result = await self.db.execute(query)
        bookings = result.scalars().all()

        items = []
        for b in bookings:
            entity_name = None
            if b.hotel_room_id:
                room_res = await self.db.execute(
                    select(Room).options(joinedload(Room.hotel)).where(Room.id == b.hotel_room_id)
                )
                room = room_res.scalar_one_or_none()
                if room:
                    entity_name = room.hotel.name if room.hotel else "Hotel"
            elif b.apartment_id:
                apt_res = await self.db.execute(select(Apartment).where(Apartment.id == b.apartment_id))
                apt = apt_res.scalar_one_or_none()
                entity_name = apt.name if apt else "Apartment"
            elif b.restaurant_id:
                rest_res = await self.db.execute(select(Restaurant).where(Restaurant.id == b.restaurant_id))
                rest = rest_res.scalar_one_or_none()
                entity_name = rest.name if rest else "Restaurant"

            items.append(BookingListResponse(
                id=b.id,
                reference_number=b.reference_number,
                booking_type=b.booking_type,
                status=b.status,
                booking_date=b.booking_date,
                check_in_date=b.check_in_date,
                check_out_date=b.check_out_date,
                scheduled_time=b.scheduled_time,
                guest_count=b.guest_count,
                total_price=b.total_price,
                currency=b.currency,
                is_paid=b.is_paid,
                created_at=b.created_at,
                entity_name=entity_name,
            ))

        return items, total

    # ------------------------------------------------------------------
    # Admin Reads
    # ------------------------------------------------------------------

    async def get_admin_dashboard_stats(self) -> AdminBookingKPIs:
        """Calculate admin dashboard KPIs."""
        total = await self.db.scalar(select(func.count(Booking.id)).where(Booking.is_deleted == False)) or 0
        active_confirmed = await self.db.scalar(
            select(func.count(Booking.id)).where(
                Booking.is_deleted == False, 
                Booking.status.in_([BookingStatus.CONFIRMED.value, "checked_in"])
            )
        ) or 0
        pending = await self.db.scalar(
            select(func.count(Booking.id)).where(
                Booking.is_deleted == False, 
                Booking.status == BookingStatus.PENDING.value
            )
        ) or 0
        revenue = await self.db.scalar(
            select(func.sum(Booking.total_price)).where(
                Booking.is_deleted == False, 
                Booking.is_paid == True
            )
        ) or 0.0

        return AdminBookingKPIs(
            total_bookings=total,
            active_confirmed=active_confirmed,
            pending_approval=pending,
            collected_revenue=float(revenue)
        )

    async def get_admin_list(
        self,
        pagination: PaginationParams,
        booking_type: Optional[BookingType] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[List[AdminBookingListItem], int]:
        """Fetch bookings with patient and entity info for admin list."""
        from app.models.patient import Patient
        from app.models.user import User
        from app.models.hotel import Hotel, Room
        from app.models.apartment import Apartment
        from app.models.restaurant import Restaurant

        query = select(Booking).options(
            joinedload(Booking.patient).joinedload(Patient.user)
        ).where(Booking.is_deleted == False)

        if booking_type:
            query = query.where(Booking.booking_type == booking_type.value)
        if status:
            query = query.where(Booking.status == status)
        if search:
            search_filter = f"%{search}%"
            query = query.join(Patient).join(User).where(
                (Booking.reference_number.ilike(search_filter)) |
                (User.full_name.ilike(search_filter)) |
                (User.email.ilike(search_filter))
            )

        count_result = await self.db.execute(select(func.count()).select_from(query.subquery()))
        total = count_result.scalar() or 0

        query = query.order_by(Booking.created_at.desc()).offset(pagination.offset).limit(pagination.page_size)
        result = await self.db.execute(query)
        bookings = result.scalars().all()

        items = []
        for b in bookings:
            entity_name = None
            room_name = None
            if b.hotel_room_id:
                room_res = await self.db.execute(select(Room).options(joinedload(Room.hotel)).where(Room.id == b.hotel_room_id))
                room = room_res.scalar_one_or_none()
                if room:
                    entity_name = room.hotel.name if room.hotel else "Hotel"
                    room_name = room.name
            elif b.apartment_id:
                apt_res = await self.db.execute(select(Apartment).where(Apartment.id == b.apartment_id))
                apt = apt_res.scalar_one_or_none()
                entity_name = apt.name if apt else "Apartment"
            elif b.restaurant_id:
                rest_res = await self.db.execute(select(Restaurant).where(Restaurant.id == b.restaurant_id))
                rest = rest_res.scalar_one_or_none()
                entity_name = rest.name if rest else "Restaurant"

            items.append(AdminBookingListItem(
                id=b.id,
                reference_number=b.reference_number,
                booking_type=b.booking_type,
                status=b.status,
                booking_date=b.booking_date,
                check_in_date=b.check_in_date,
                check_out_date=b.check_out_date,
                scheduled_time=b.scheduled_time,
                guest_count=b.guest_count,
                total_price=b.total_price,
                currency=b.currency,
                is_paid=b.is_paid,
                created_at=b.created_at,
                patient_name=b.patient.user.full_name if b.patient and b.patient.user else "Unknown",
                patient_email=b.patient.user.email if b.patient and b.patient.user else None,
                property_name=entity_name,
                room_name=room_name
            ))

        return items, total

    async def get_admin_detail(self, booking_id: UUID) -> AdminBookingDetailResponse:
        """Fetch detailed booking info with timeline for admin."""
        from app.models.patient import Patient
        from app.models.hotel import Hotel, Room
        from app.models.apartment import Apartment
        from app.models.restaurant import Restaurant

        result = await self.db.execute(
            select(Booking).options(
                joinedload(Booking.patient).joinedload(Patient.user)
            ).where(Booking.id == booking_id, Booking.is_deleted == False)
        )
        b = result.scalar_one_or_none()
        if not b:
            raise ValueError("Booking not found")

        entity_name = None
        entity_address = None
        room_name = None
        room_no = None
        if b.hotel_room_id:
            room_res = await self.db.execute(select(Room).options(joinedload(Room.hotel)).where(Room.id == b.hotel_room_id))
            room = room_res.scalar_one_or_none()
            if room:
                entity_name = room.hotel.name if room.hotel else "Hotel"
                entity_address = room.hotel.address if room.hotel else None
                room_name = room.name
                room_no = room.room_no # Assuming this exists or using name as no
        elif b.apartment_id:
            apt_res = await self.db.execute(select(Apartment).where(Apartment.id == b.apartment_id))
            apt = apt_res.scalar_one_or_none()
            if apt:
                entity_name = apt.name
                entity_address = apt.address_line1

        # Timeline
        timeline = [
            BookingTimelineItem(
                status="Created",
                description="Booking request initiated by patient",
                timestamp=b.created_at,
                actor_name=b.patient.user.full_name if b.patient and b.patient.user else "Patient"
            )
        ]
        if b.is_paid:
            timeline.append(BookingTimelineItem(
                status="Paid",
                description=f"Payment received via {b.currency}",
                timestamp=b.paid_at or b.created_at,
                actor_name="System"
            ))
        if b.confirmed_at:
            timeline.append(BookingTimelineItem(
                status="Confirmed",
                description="Booking confirmed by administration",
                timestamp=b.confirmed_at,
                actor_name="Admin"
            ))
        if b.status == BookingStatus.CANCELLED.value:
            timeline.append(BookingTimelineItem(
                status="Cancelled",
                description=f"Booking cancelled. Reason: {b.cancellation_reason}",
                timestamp=b.cancelled_at or b.updated_at,
                actor_name="Admin"
            ))

        timeline.sort(key=lambda x: x.timestamp)

        paid_amount = b.total_price if b.is_paid else 0.0
        balance = b.total_price - paid_amount
        progress = 100.0 if b.is_paid else 0.0

        return AdminBookingDetailResponse(
            **b.__dict__,
            patient_name=b.patient.user.full_name if b.patient and b.patient.user else "Unknown",
            patient_email=b.patient.user.email if b.patient and b.patient.user else None,
            patient_phone=b.patient.user.phone if b.patient and b.patient.user else None,
            property_name=entity_name,
            entity_name=entity_name,
            entity_address=entity_address,
            room_name=room_name,
            room_no=room_no,
            timeline=timeline,
            payment_progress=progress,
            paid_amount=paid_amount,
            balance_amount=balance
        )

    async def admin_update(self, booking_id: UUID, data: AdminBookingUpdate, updated_by: UUID) -> Booking:
        """Comprehensive update for admin."""
        b = await self.get_by_id(booking_id)
        if not b:
            raise ValueError("Booking not found")
        
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "status":
                b.status = value.value
            else:
                setattr(b, field, value)
        
        b.updated_by = updated_by
        await self.db.commit()
        await self.db.refresh(b)
        return b

    # ------------------------------------------------------------------
    # Hotel booking
    # ------------------------------------------------------------------

    async def create_hotel_booking(
        self,
        patient_id: UUID,
        data: HotelBookingCreate,
        created_by: Optional[UUID] = None,
        user: Optional[User] = None,
    ) -> Booking:
        """Book a hotel room after checking date-range availability."""
        room_result = await self.db.execute(
            select(Room).where(Room.id == data.room_id, Room.is_available == True)
        )
        room: Optional[Room] = room_result.scalar_one_or_none()
        if not room:
            raise ValueError("Room not found or unavailable")

        # Check RoomAvailability calendar for conflicts
        await self._assert_room_available(data.room_id, data.check_in_date, data.check_out_date)

        # Pull hotel name for email
        from app.models.hotel import Hotel
        hotel_result = await self.db.execute(
            select(Hotel).where(Hotel.id == room.hotel_id)
        )
        hotel = hotel_result.scalar_one_or_none()

        nights = max((data.check_out_date - data.check_in_date).days, 1)
        base_price = round(room.price_per_night * nights, 2)
        taxes = round(base_price * 0.10, 2)

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
            taxes=taxes,
            discount=0.0,
            total_price=round(base_price + taxes, 2),
            currency=hotel.currency if hotel else "USD",
            special_requests=data.special_requests,
            notes=data.notes,
            status=BookingStatus.CONFIRMED.value,
            confirmed_at=datetime.now(timezone.utc),
            confirmed_by=created_by,
            created_by=created_by,
            booking_metadata={
                "price_per_night": room.price_per_night,
                "nights": nights,
                "room_name": room.name,
                "hotel_name": hotel.name if hotel else None,
            },
        )
        self.db.add(booking)
        await self.db.commit()
        await self.db.refresh(booking)
        logger.info("hotel_booking_created", booking_id=str(booking.id), ref=booking.reference_number)

        # Send confirmation email (best-effort)
        if user:
            try:
                html = render_hotel_booking_confirmation_html(
                    guest_name=user.full_name,
                    hotel_name=hotel.name if hotel else "Hotel",
                    room_name=room.name,
                    room_type=room.room_type,
                    check_in_date=data.check_in_date.strftime("%B %d, %Y"),
                    check_out_date=data.check_out_date.strftime("%B %d, %Y"),
                    nights=nights,
                    guest_count=data.guest_count,
                    total_price=booking.total_price,
                    currency=booking.currency,
                    reference_number=booking.reference_number,
                    special_requests=data.special_requests,
                )
                await send_email(
                    db=self.db,
                    to_email=user.email,
                    to_name=user.full_name,
                    subject=f"Hotel Booking Confirmed — {booking.reference_number}",
                    body_html=html,
                    category="booking",
                    user_id=user.id,
                )
            except Exception as exc:
                logger.error("hotel_booking_email_failed", error=str(exc))

        return booking

    async def check_room_availability(
        self, room_id: UUID, check_in: date, check_out: date
    ) -> bool:
        """Return True if the room is available for the given date range."""
        try:
            await self._assert_room_available(room_id, check_in, check_out)
            return True
        except ValueError:
            return False

    # ------------------------------------------------------------------
    # Apartment booking
    # ------------------------------------------------------------------

    async def check_apartment_availability(
        self, apartment_id: UUID, check_in: date, check_out: date
    ) -> bool:
        """Return True if the apartment has no overlapping bookings."""
        conflict = await self.db.execute(
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
        return conflict.scalar_one_or_none() is None

    async def create_apartment_booking(
        self,
        patient_id: UUID,
        data: ApartmentBookingCreate,
        created_by: Optional[UUID] = None,
        user: Optional[User] = None,
    ) -> Booking:
        """Book an apartment for a date range."""
        apt_result = await self.db.execute(
            select(Apartment).where(
                Apartment.id == data.apartment_id,
                Apartment.is_active == True,
                Apartment.is_available == True,
            )
        )
        apartment: Optional[Apartment] = apt_result.scalar_one_or_none()
        if not apartment:
            raise ValueError("Apartment not found or not available")

        # Check for overlapping confirmed bookings on this apartment
        conflict = await self.db.execute(
            select(Booking.id).where(
                and_(
                    Booking.apartment_id == data.apartment_id,
                    Booking.is_deleted == False,
                    Booking.status.notin_([BookingStatus.CANCELLED.value]),
                    Booking.check_in_date < data.check_out_date,
                    Booking.check_out_date > data.check_in_date,
                )
            )
        )
        if conflict.scalar_one_or_none():
            raise ValueError("The apartment is already booked for the selected dates")

        nights = max((data.check_out_date - data.check_in_date).days, 1)

        # Pick best price: weekly or monthly rate if applicable, else nightly
        if nights >= 28 and apartment.price_per_month:
            months = nights / 30
            base_price = round(apartment.price_per_month * months, 2)
        elif nights >= 7 and apartment.price_per_week:
            weeks = nights / 7
            base_price = round(apartment.price_per_week * weeks, 2)
        elif apartment.price_per_night:
            base_price = round(apartment.price_per_night * nights, 2)
        else:
            raise ValueError("Apartment has no pricing configured")

        taxes = round(base_price * 0.10, 2)
        address = f"{apartment.address_line1}, {apartment.city}, {apartment.country}"

        booking = Booking(
            patient_id=patient_id,
            booking_type=BookingType.APARTMENT.value,
            reference_number=generate_reference_id("APT"),
            apartment_id=data.apartment_id,
            check_in_date=data.check_in_date,
            check_out_date=data.check_out_date,
            booking_date=datetime.now(timezone.utc),
            guest_count=data.guest_count,
            guest_details=data.guest_details,
            base_price=base_price,
            taxes=taxes,
            discount=0.0,
            total_price=round(base_price + taxes, 2),
            currency=apartment.currency,
            special_requests=data.special_requests,
            notes=data.notes,
            status=BookingStatus.CONFIRMED.value,
            confirmed_at=datetime.now(timezone.utc),
            confirmed_by=created_by,
            created_by=created_by,
        )
        self.db.add(booking)
        await self.db.commit()
        await self.db.refresh(booking)
        logger.info("apartment_booking_created", booking_id=str(booking.id), ref=booking.reference_number)

        if user:
            try:
                html = render_apartment_booking_confirmation_html(
                    guest_name=user.full_name,
                    apartment_name=apartment.name,
                    bedroom_type=apartment.bedroom_type,
                    check_in_date=data.check_in_date.strftime("%B %d, %Y"),
                    check_out_date=data.check_out_date.strftime("%B %d, %Y"),
                    nights=nights,
                    guest_count=data.guest_count,
                    total_price=booking.total_price,
                    currency=booking.currency,
                    reference_number=booking.reference_number,
                    address=address,
                    special_requests=data.special_requests,
                )
                await send_email(
                    db=self.db,
                    to_email=user.email,
                    to_name=user.full_name,
                    subject=f"Apartment Booking Confirmed — {booking.reference_number}",
                    body_html=html,
                    category="booking",
                    user_id=user.id,
                )
            except Exception as exc:
                logger.error("apartment_booking_email_failed", error=str(exc))

        return booking

    # ------------------------------------------------------------------
    # Restaurant booking
    # ------------------------------------------------------------------

    async def create_restaurant_booking(
        self,
        patient_id: UUID,
        data: RestaurantBookingCreate,
        created_by: Optional[UUID] = None,
        user: Optional[User] = None,
    ) -> Booking:
        """Reserve a restaurant table with optional food pre-order."""
        rest_result = await self.db.execute(
            select(Restaurant).where(
                Restaurant.id == data.restaurant_id,
                Restaurant.is_active == True,
            )
        )
        restaurant: Optional[Restaurant] = rest_result.scalar_one_or_none()
        if not restaurant:
            raise ValueError("Restaurant not found")
        if not restaurant.accepts_reservations:
            raise ValueError("This restaurant does not accept reservations")

        booking_dt = datetime.combine(data.booking_date, data.booking_time)
        booking = Booking(
            patient_id=patient_id,
            booking_type=BookingType.RESTAURANT.value,
            reference_number=generate_reference_id("RST"),
            restaurant_id=data.restaurant_id,
            booking_date=datetime.now(timezone.utc),
            scheduled_time=booking_dt,
            guest_count=data.guest_count,
            special_requests=data.special_requests or data.dietary_requirements,
            notes=data.notes,
            status=BookingStatus.CONFIRMED.value,
            confirmed_at=datetime.now(timezone.utc),
            confirmed_by=created_by,
            base_price=0.0,
            taxes=0.0,
            discount=0.0,
            total_price=0.0,
            created_by=created_by,
        )
        self.db.add(booking)
        await self.db.flush()

        # Create detailed MealBooking + calculate cost from ordered items
        estimated_cost: Optional[float] = None
        ordered_items_summary: Optional[str] = None

        selected_items_dict: dict = {}
        if data.ordered_items:
            item_ids = [str(oi.item_id) for oi in data.ordered_items]
            menu_result = await self.db.execute(
                select(MenuItem).where(
                    MenuItem.id.in_([oi.item_id for oi in data.ordered_items]),
                    MenuItem.restaurant_id == data.restaurant_id,
                    MenuItem.is_available == True,
                )
            )
            menu_items_map = {item.id: item for item in menu_result.scalars().all()}

            estimated_cost = 0.0
            summary_parts = []
            for oi in data.ordered_items:
                item = menu_items_map.get(oi.item_id)
                if item:
                    line_total = item.price * oi.quantity
                    estimated_cost += line_total
                    summary_parts.append(f"{oi.quantity}x {item.name}")
                    selected_items_dict[str(oi.item_id)] = {
                        "name": item.name,
                        "quantity": oi.quantity,
                        "price": item.price,
                        "notes": oi.notes,
                    }
            ordered_items_summary = ", ".join(summary_parts) if summary_parts else None

            booking.base_price = round(estimated_cost or 0.0, 2)
            booking.taxes = round((estimated_cost or 0.0) * 0.05, 2)
            booking.total_price = round(booking.base_price + booking.taxes, 2)

        meal_booking = MealBooking(
            restaurant_id=data.restaurant_id,
            patient_id=patient_id,
            booking_id=booking.id,
            meal_type=data.meal_type.value,
            booking_date=data.booking_date,
            booking_time=data.booking_time,
            guest_count=data.guest_count,
            selected_items=selected_items_dict if selected_items_dict else None,
            special_requests=data.special_requests,
            dietary_requirements=data.dietary_requirements,
            estimated_cost=estimated_cost,
            status="confirmed",
            confirmation_code=booking.reference_number,
            contact_name=data.contact_name or (user.full_name if user else "Guest"),
            contact_phone=data.contact_phone or "",
            created_by=created_by,
        )
        self.db.add(meal_booking)

        await self.db.commit()
        await self.db.refresh(booking)
        logger.info("restaurant_booking_created", booking_id=str(booking.id), ref=booking.reference_number)

        if user:
            try:
                html = render_restaurant_booking_confirmation_html(
                    guest_name=user.full_name,
                    restaurant_name=restaurant.name,
                    booking_date=data.booking_date.strftime("%B %d, %Y"),
                    booking_time=data.booking_time.strftime("%I:%M %p"),
                    meal_type=data.meal_type.value,
                    guest_count=data.guest_count,
                    reference_number=booking.reference_number,
                    dietary_requirements=data.dietary_requirements,
                    ordered_items_summary=ordered_items_summary,
                    estimated_cost=estimated_cost,
                    currency=restaurant.currency,
                )
                await send_email(
                    db=self.db,
                    to_email=user.email,
                    to_name=user.full_name,
                    subject=f"Restaurant Booking Confirmed — {booking.reference_number}",
                    body_html=html,
                    category="booking",
                    user_id=user.id,
                )
            except Exception as exc:
                logger.error("restaurant_booking_email_failed", error=str(exc))

        return booking

    # ------------------------------------------------------------------
    # Updates & cancellation
    # ------------------------------------------------------------------

    async def update(
        self,
        booking: Booking,
        data: BookingUpdate,
        updated_by: Optional[UUID] = None,
    ) -> Booking:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(booking, field, value)
        booking.updated_by = updated_by
        await self.db.commit()
        await self.db.refresh(booking)
        return booking

    async def update_status(
        self,
        booking: Booking,
        data: BookingStatusUpdate,
        updated_by: UUID,
    ) -> Booking:
        booking.status = data.status.value
        if data.internal_notes:
            booking.internal_notes = data.internal_notes
        booking.updated_by = updated_by
        if data.status == BookingStatus.CONFIRMED:
            booking.confirmed_at = datetime.now(timezone.utc)
            booking.confirmed_by = updated_by
        await self.db.commit()
        await self.db.refresh(booking)
        logger.info("booking_status_updated", booking_id=str(booking.id), status=data.status.value)

        # Notify patient when booking is confirmed
        if data.status == BookingStatus.CONFIRMED and booking.patient_id:
            try:
                from app.models.patient import Patient
                patient_result = await self.db.execute(
                    select(Patient).where(Patient.id == booking.patient_id)
                )
                patient_rec = patient_result.scalar_one_or_none()
                if patient_rec:
                    await notify(
                        db=self.db,
                        user_id=patient_rec.user_id,
                        title="Booking Confirmed",
                        message=f"Your booking {booking.reference_number} has been confirmed.",
                        notification_type="booking",
                        entity_type="booking",
                        entity_id=booking.id,
                        action_url=f"/bookings/{booking.id}",
                        created_by=updated_by,
                    )
            except Exception as exc:
                logger.error("booking_confirm_notification_failed", error=str(exc))

        return booking

    async def cancel(
        self,
        booking: Booking,
        data: BookingCancelRequest,
        cancelled_by: UUID,
    ) -> Booking:
        if booking.status in {BookingStatus.COMPLETED.value, BookingStatus.CANCELLED.value}:
            raise ValueError(f"Cannot cancel a {booking.status} booking")

        booking.status = BookingStatus.CANCELLED.value
        booking.cancelled_at = datetime.now(timezone.utc)
        booking.cancellation_reason = data.cancellation_reason
        booking.cancelled_by = cancelled_by
        booking.updated_by = cancelled_by

        if booking.is_paid:
            booking.refund_amount = round(booking.total_price * 0.8, 2)  # 80% refund

        await self.db.commit()
        await self.db.refresh(booking)
        logger.info("booking_cancelled", booking_id=str(booking.id))
        return booking

    async def get_stats(self, patient_id: Optional[UUID] = None) -> dict:
        base_query = select(Booking).where(Booking.is_deleted == False)
        if patient_id:
            base_query = base_query.where(Booking.patient_id == patient_id)

        total = (await self.db.execute(
            select(func.count()).select_from(base_query.subquery())
        )).scalar() or 0

        status_rows = (await self.db.execute(
            select(Booking.status, func.count())
            .where(Booking.is_deleted == False)
            .group_by(Booking.status)
        )).all()
        by_status = {s: c for s, c in status_rows}

        type_rows = (await self.db.execute(
            select(Booking.booking_type, func.count())
            .where(Booking.is_deleted == False)
            .group_by(Booking.booking_type)
        )).all()
        by_type = {t: c for t, c in type_rows}

        revenue = (await self.db.execute(
            select(func.sum(Booking.total_price))
            .where(Booking.is_deleted == False, Booking.is_paid == True)
        )).scalar() or 0.0

        return {
            "total_bookings": total,
            "confirmed_bookings": by_status.get(BookingStatus.CONFIRMED.value, 0),
            "cancelled_bookings": by_status.get(BookingStatus.CANCELLED.value, 0),
            "pending_bookings": by_status.get(BookingStatus.PENDING.value, 0),
            "total_revenue": revenue,
            "bookings_by_type": by_type,
            "bookings_by_status": by_status,
        }

    async def get_booking_reports(
        self, 
        start_date: date, 
        end_date: date, 
        property_type: str = "all"
    ) -> BookingReportSummary:
        """Get booking reports for a specific date range and property type for admin dashboard."""
        from app.models.hotel import Hotel, Room
        from app.models.apartment import Apartment
        
        # Filters for bookings
        booking_filters = [
            cast(Booking.created_at, Date) >= start_date,
            cast(Booking.created_at, Date) <= end_date,
            Booking.is_deleted == False
        ]
        
        if property_type == "hotel":
            booking_filters.append(Booking.booking_type == "hotel")
        elif property_type == "apartment":
            booking_filters.append(Booking.booking_type == "apartment")

        # 1. Total Bookings
        total_bookings = await self.db.scalar(
            select(func.count(Booking.id)).where(and_(*booking_filters))
        ) or 0

        # 2. Revenue (confirmed or completed bookings)
        revenue_filters = list(booking_filters)
        revenue_filters.append(Booking.status.in_(["confirmed", "completed"]))
        total_revenue = await self.db.scalar(
            select(func.sum(Booking.total_price)).where(and_(*revenue_filters))
        ) or 0.0

        # 3. Cancellation Rate
        cancelled_bookings = await self.db.scalar(
            select(func.count(Booking.id)).where(
                and_(
                    *booking_filters,
                    Booking.status == "cancelled"
                )
            )
        ) or 0
        cancellation_rate = (cancelled_bookings / total_bookings * 100) if total_bookings > 0 else 0.0

        # 4. Occupancy Rate (Approximate based on nights booked vs capacity)
        # Total rooms across relevant properties
        if property_type == "hotel":
            total_rooms = await self.db.scalar(select(func.sum(Room.total_rooms)).where(Room.is_deleted == False, Room.room_type != "apartment")) or 0
        elif property_type == "apartment":
            total_rooms = await self.db.scalar(select(func.sum(Room.total_rooms)).where(Room.is_deleted == False, Room.room_type == "apartment")) or 0
        else:
            total_rooms = await self.db.scalar(select(func.sum(Room.total_rooms)).where(Room.is_deleted == False)) or 0
            
        num_days = max(1, (end_date - start_date).days + 1)
        total_room_nights = (total_rooms or 0) * num_days
        
        # Booked room nights in this period
        # Simplified: sum of nights for bookings made in this period
        booked_nights = await self.db.scalar(
            select(func.sum(
                func.extract('day', func.age(Booking.check_out_date, Booking.check_in_date))
            )).where(
                and_(
                    *booking_filters,
                    Booking.status.in_(["confirmed", "completed"]),
                    Booking.check_in_date.isnot(None),
                    Booking.check_out_date.isnot(None)
                )
            )
        ) or 0
        
        occupancy_rate = (float(booked_nights) / total_room_nights * 100) if total_room_nights > 0 else 0.0

        # 5. Trends
        # Daily bookings
        bookings_trend_res = await self.db.execute(
            select(
                cast(Booking.created_at, Date).label("date"),
                func.count(Booking.id).label("count")
            )
            .where(and_(*booking_filters))
            .group_by(text("date"))
            .order_by(text("date"))
        )
        bookings_trend = [KPITrend(date=row.date, value=float(row.count)) for row in bookings_trend_res]

        # Daily revenue
        revenue_trend_res = await self.db.execute(
            select(
                cast(Booking.created_at, Date).label("date"),
                func.sum(Booking.total_price).label("revenue")
            )
            .where(and_(*revenue_filters))
            .group_by(text("date"))
            .order_by(text("date"))
        )
        revenue_trend = [KPITrend(date=row.date, value=float(row.revenue)) for row in revenue_trend_res]

        # 6. Bookings by Property Distribution
        prop_bookings = []
        
        # Hotel bookings
        hotel_bookings_sql = select(Hotel.name, func.count(Booking.id).label("count")) \
            .select_from(Booking) \
            .join(Room, Booking.hotel_room_id == Room.id) \
            .join(Hotel, Room.hotel_id == Hotel.id) \
            .where(and_(*booking_filters)) \
            .group_by(Hotel.name)
        
        hotel_bookings_res = await self.db.execute(hotel_bookings_sql)
        for row in hotel_bookings_res:
            prop_bookings.append(PropertyBooking(
                name=row.name, 
                count=row.count, 
                percentage=(row.count / total_bookings * 100) if total_bookings > 0 else 0
            ))
            
        # Apartment bookings
        apt_bookings_sql = select(Apartment.name, func.count(Booking.id).label("count")) \
            .select_from(Booking) \
            .join(Apartment, Booking.apartment_id == Apartment.id) \
            .where(and_(*booking_filters)) \
            .group_by(Apartment.name)
            
        apt_bookings_res = await self.db.execute(apt_bookings_sql)
        for row in apt_bookings_res:
            prop_bookings.append(PropertyBooking(
                name=row.name, 
                count=row.count, 
                percentage=(row.count / total_bookings * 100) if total_bookings > 0 else 0
            ))
            
        prop_bookings.sort(key=lambda x: x.count, reverse=True)

        return BookingReportSummary(
            total_bookings=total_bookings,
            total_revenue=float(total_revenue),
            occupancy_rate=round(occupancy_rate, 2),
            cancellation_rate=round(cancellation_rate, 2),
            bookings_trend=bookings_trend,
            revenue_trend=revenue_trend,
            bookings_by_property=prop_bookings[:5]
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _assert_room_available(
        self, room_id: UUID, check_in: date, check_out: date
    ) -> None:
        """Raise ValueError if the room is blocked for any night in the range."""
        from sqlalchemy import between
        import datetime as _dt

        # Check RoomAvailability rows that overlap [check_in, check_out)
        blocked_result = await self.db.execute(
            select(RoomAvailability).where(
                RoomAvailability.room_id == room_id,
                RoomAvailability.date >= check_in,
                RoomAvailability.date < check_out,
                RoomAvailability.is_blocked == True,
            )
        )
        if blocked_result.scalar_one_or_none():
            raise ValueError("The room is not available for the selected dates")

        # Also check for existing confirmed bookings overlapping these dates
        conflict = await self.db.execute(
            select(Booking.id).where(
                and_(
                    Booking.hotel_room_id == room_id,
                    Booking.is_deleted == False,
                    Booking.status.notin_([BookingStatus.CANCELLED.value]),
                    Booking.check_in_date < check_out,
                    Booking.check_out_date > check_in,
                )
            )
        )
        if conflict.scalar_one_or_none():
            raise ValueError("The room is already booked for the selected dates")
