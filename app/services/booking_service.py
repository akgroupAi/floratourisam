"""Booking service.

Handles hotel, apartment, and restaurant bookings:
- Room/apartment availability checking against RoomAvailability calendar
- MealBooking record creation for restaurant pre-orders
- Confirmation emails for all booking types
"""

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, select, cast, Date, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.booking import Booking
from app.models.hotel import Room, RoomAvailability
from app.models.apartment import Apartment, ApartmentAvailability
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
from app.utils.admin_notify import notify_admin_cancellation, notify_admin_new_booking
from app.utils.cancellation import compute_refund
from app.utils.pricing import price_with_platform_fee
from app.utils.email_sender import (
    render_apartment_booking_confirmation_html,
    render_hotel_booking_confirmation_html,
    render_restaurant_booking_confirmation_html,
    send_email,
)
from app.utils.enums import BookingStatus, BookingType
from app.utils.helpers import generate_reference_id
from app.utils.notifications import notify
from app.utils.booking_helpers import OCCUPIED_BOOKING_STATUSES, booking_status_label
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
                status_label=booking_status_label(b.status, b.is_paid, b.booking_type),
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

    def _manager_scope_clause(self, user: Optional[User]):
        """Return a filter restricting bookings to a manager's assigned entities.

        - Super admin / admin: returns None (no restriction — all bookings).
        - Hotel/apartment/restaurant manager: only bookings for the hotels,
          apartments or restaurants assigned to them via ``manager_id``.
        - Any other role (or no user): returns a clause matching nothing.
        """
        from app.models.hotel import Hotel
        from app.utils.enums import UserRole

        if user is None:
            return Booking.id.is_(None)

        role = user.role
        if role in (UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value):
            return None
        if role == UserRole.HOTEL_MANAGER.value:
            room_ids = (
                select(Room.id)
                .join(Hotel, Room.hotel_id == Hotel.id)
                .where(Hotel.manager_id == user.id)
            )
            return Booking.hotel_room_id.in_(room_ids)
        if role == UserRole.APARTMENT_MANAGER.value:
            apt_ids = select(Apartment.id).where(Apartment.manager_id == user.id)
            return Booking.apartment_id.in_(apt_ids)
        if role == UserRole.RESTAURANT_MANAGER.value:
            rest_ids = select(Restaurant.id).where(Restaurant.manager_id == user.id)
            return Booking.restaurant_id.in_(rest_ids)
        return Booking.id.is_(None)

    async def get_admin_dashboard_stats(self, user: Optional[User] = None) -> AdminBookingKPIs:
        """Calculate admin dashboard KPIs (scoped to the manager's entities)."""
        scope = self._manager_scope_clause(user)
        scope_filters = [scope] if scope is not None else []

        total = await self.db.scalar(
            select(func.count(Booking.id)).where(Booking.is_deleted == False, *scope_filters)
        ) or 0
        active_confirmed = await self.db.scalar(
            select(func.count(Booking.id)).where(
                Booking.is_deleted == False,
                Booking.status.in_([BookingStatus.CONFIRMED.value, "checked_in"]),
                *scope_filters,
            )
        ) or 0
        pending = await self.db.scalar(
            select(func.count(Booking.id)).where(
                Booking.is_deleted == False,
                Booking.status == BookingStatus.PENDING.value,
                *scope_filters,
            )
        ) or 0
        revenue = await self.db.scalar(
            select(func.sum(Booking.total_price)).where(
                Booking.is_deleted == False,
                Booking.is_paid == True,
                *scope_filters,
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
        user: Optional[User] = None,
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

        scope = self._manager_scope_clause(user)
        if scope is not None:
            query = query.where(scope)

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
        taxes = 0.0
        _, platform_fee, total_price = price_with_platform_fee(base_price, taxes)

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
            platform_fee=platform_fee,
            total_price=total_price,
            currency=hotel.currency if hotel else "USD",
            special_requests=data.special_requests,
            notes=data.notes,
            status=BookingStatus.PENDING.value,
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
        await self._attach_guests(booking, getattr(data, "guests", None), created_by)

        logger.info("hotel_booking_created_pending_payment", booking_id=str(booking.id), ref=booking.reference_number)

        await notify_admin_new_booking(self.db, booking)
        await self.db.commit()

        return booking

    async def _attach_guests(self, booking, guests, created_by) -> None:
        """Save travellers supplied inline with a booking.

        Best-effort by design: a malformed traveller list must not lose a booking the
        customer has already paid attention to. The error is logged and the guests can
        be added afterwards via POST /bookings/{id}/guests.
        """
        if not guests:
            return
        from app.services.booking_guest_service import BookingGuestService

        try:
            await BookingGuestService(self.db).add_guests(
                booking.id, guests, created_by=created_by
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "booking_guests_attach_failed",
                booking_id=str(booking.id),
                error=str(exc),
            )

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
        """Whether the apartment can be booked for the whole range.

        The single source of truth for apartment availability — the public endpoints
        all delegate here. Previously three implementations disagreed about whether an
        unpaid `pending` booking holds the unit; they do not, matching what the booking
        path actually enforces and how hotel rooms behave.
        """
        try:
            await self._assert_apartment_available(apartment_id, check_in, check_out)
            return True
        except ValueError:
            return False

    async def _assert_apartment_available(
        self,
        apartment_id: UUID,
        check_in: date,
        check_out: date,
        exclude_booking_id: Optional[UUID] = None,
    ) -> None:
        """Raise ValueError with a reason if the apartment cannot take this stay."""
        if check_out <= check_in:
            raise ValueError("check_out must be after check_in")

        apartment = (
            await self.db.execute(
                select(Apartment).where(Apartment.id == apartment_id)
            )
        ).scalar_one_or_none()
        if not apartment:
            raise ValueError("Apartment not found")

        nights = [
            check_in + timedelta(days=offset)
            for offset in range((check_out - check_in).days)
        ]

        overrides = {
            row.date: row
            for row in (
                await self.db.execute(
                    select(ApartmentAvailability).where(
                        ApartmentAvailability.apartment_id == apartment_id,
                        ApartmentAvailability.date >= check_in,
                        ApartmentAvailability.date < check_out,
                        ApartmentAvailability.is_deleted == False,
                    )
                )
            )
            .scalars()
            .all()
        }

        for night in nights:
            override = overrides.get(night)
            if override and override.is_blocked:
                raise ValueError(
                    f"The apartment is not available on {night.isoformat()}"
                )

        # Minimum stay is taken from the first night of the stay — that is the rule the
        # guest is quoted when they pick their arrival date.
        first_override = overrides.get(check_in)
        required_nights = (
            first_override.minimum_nights
            if first_override is not None and first_override.minimum_nights is not None
            else (apartment.minimum_nights or 1)
        )
        if len(nights) < required_nights:
            raise ValueError(
                f"This apartment requires a minimum stay of {required_nights} night(s)"
            )

        conflict_query = select(Booking.id).where(
            and_(
                Booking.apartment_id == apartment_id,
                Booking.is_deleted == False,
                Booking.status.in_(OCCUPIED_BOOKING_STATUSES),
                Booking.check_in_date < check_out,
                Booking.check_out_date > check_in,
            )
        )
        if exclude_booking_id:
            conflict_query = conflict_query.where(Booking.id != exclude_booking_id)
        if (await self.db.execute(conflict_query)).scalar_one_or_none():
            raise ValueError("The apartment is already booked for the selected dates")

    async def _apartment_base_price(
        self, apartment: Apartment, check_in: date, nights: int
    ) -> float:
        """Price a stay, preferring per-date calendar rates over the tiered defaults.

        If every night of the stay has a calendar price, those are summed. Otherwise the
        existing monthly/weekly/nightly tiers apply — a long stay should still get the
        monthly rate rather than 30 nightly overrides.
        """
        check_out = check_in + timedelta(days=nights)
        overrides = {
            row.date: row
            for row in (
                await self.db.execute(
                    select(ApartmentAvailability).where(
                        ApartmentAvailability.apartment_id == apartment.id,
                        ApartmentAvailability.date >= check_in,
                        ApartmentAvailability.date < check_out,
                        ApartmentAvailability.is_deleted == False,
                        ApartmentAvailability.price.isnot(None),
                    )
                )
            )
            .scalars()
            .all()
        }

        stay_nights = [check_in + timedelta(days=offset) for offset in range(nights)]
        if overrides and all(night in overrides for night in stay_nights):
            return round(sum(overrides[night].price for night in stay_nights), 2)

        if nights >= 28 and apartment.price_per_month:
            return round(apartment.price_per_month * (nights / 30), 2)
        if nights >= 7 and apartment.price_per_week:
            return round(apartment.price_per_week * (nights / 7), 2)
        if apartment.price_per_night:
            return round(apartment.price_per_night * nights, 2)
        raise ValueError("Apartment has no pricing configured")

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

        # Blocked dates, minimum stay, and overlapping bookings — one shared check so
        # the availability endpoints and this path can never disagree.
        await self._assert_apartment_available(
            data.apartment_id, data.check_in_date, data.check_out_date
        )

        nights = max((data.check_out_date - data.check_in_date).days, 1)
        base_price = await self._apartment_base_price(apartment, data.check_in_date, nights)

        taxes = 0.0
        _, platform_fee, total_price = price_with_platform_fee(base_price, taxes)
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
            platform_fee=platform_fee,
            total_price=total_price,
            currency=apartment.currency,
            special_requests=data.special_requests,
            notes=data.notes,
            status=BookingStatus.PENDING.value,
            created_by=created_by,
        )
        self.db.add(booking)
        await self.db.commit()
        await self.db.refresh(booking)
        await self._attach_guests(booking, getattr(data, "guests", None), created_by)

        logger.info("apartment_booking_created_pending_payment", booking_id=str(booking.id), ref=booking.reference_number)

        await notify_admin_new_booking(self.db, booking)
        await self.db.commit()

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
            booking.taxes = 0.0
            # A table reservation with no pre-order costs nothing, so no fee applies.
            _, booking.platform_fee, booking.total_price = price_with_platform_fee(
                booking.base_price, booking.taxes
            )

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

        await notify_admin_new_booking(self.db, booking)
        await self.db.commit()

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

    @staticmethod
    def queue_refund(booking: Booking):
        """Work out the refund for a cancelled booking and queue it.

        Does not commit and does not call the gateway — money moves only when an admin
        releases it from /admin/refunds. Shared by every cancellation path (booking,
        consultation, appointment) so they cannot compute different amounts.

        Returns the breakdown for callers that want to log or display it.
        """
        breakdown = compute_refund(booking)
        booking.refund_amount = breakdown.refund_amount
        booking.cancellation_charge = breakdown.cancellation_charge
        if breakdown.refund_amount > 0:
            booking.refund_status = "pending"
            booking.refund_requested_at = datetime.now(timezone.utc)
        else:
            booking.refund_status = "none"
            booking.refund_note = breakdown.reason
        return breakdown

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

        self.queue_refund(booking)

        await self.db.commit()
        await self.db.refresh(booking)

        # Best-effort: a failed notification must not undo the cancellation.
        from app.utils.manager_notify import notify_manager_cancellation

        await notify_manager_cancellation(self.db, booking)
        # The admin needs to know too - a queued refund will not pay itself.
        await notify_admin_cancellation(self.db, booking)
        await self.db.commit()

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
        start_date: Optional[date],
        end_date: Optional[date],
        property_type: str = "all",
        user: Optional[User] = None,
    ) -> BookingReportSummary:
        """Get booking reports for a specific date range and property type for admin dashboard."""
        from app.models.hotel import Hotel, Room
        from app.models.apartment import Apartment

        # Filters for bookings
        booking_filters = [Booking.is_deleted == False]

        # Restrict to the manager's assigned entities (None for admins)
        scope = self._manager_scope_clause(user)
        if scope is not None:
            booking_filters.append(scope)

        if start_date:
            booking_filters.append(cast(Booking.created_at, Date) >= start_date)
        if end_date:
            booking_filters.append(cast(Booking.created_at, Date) <= end_date)
        
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
        from app.utils.enums import UserRole as _UserRole
        room_filters = [Room.is_deleted == False]
        # Hotel managers' occupancy is measured against only their own rooms
        if user is not None and user.role == _UserRole.HOTEL_MANAGER.value:
            room_filters.append(
                Room.hotel_id.in_(
                    select(Hotel.id).where(Hotel.manager_id == user.id)
                )
            )

        if property_type == "hotel":
            total_rooms = await self.db.scalar(select(func.sum(Room.total_rooms)).where(*room_filters, Room.room_type != "apartment")) or 0
        elif property_type == "apartment":
            total_rooms = await self.db.scalar(select(func.sum(Room.total_rooms)).where(*room_filters, Room.room_type == "apartment")) or 0
        else:
            total_rooms = await self.db.scalar(select(func.sum(Room.total_rooms)).where(*room_filters)) or 0
            
        num_days = max(1, (end_date - start_date).days + 1) if start_date and end_date else 1
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

    async def _room_night_capacity(
        self, room_id: UUID, check_in: date, check_out: date
    ) -> Tuple[List[date], dict, dict]:
        """Per-night capacity and existing occupancy for a room type.

        A Room row is a room *type* ("Deluxe Double", total_rooms=10), not a single
        unit, so availability is a count per night rather than a yes/no. Capacity for a
        night is the calendar override where one exists, otherwise the room's
        total_rooms.

        Returns ``(nights, capacity_by_night, blocked_nights)``.
        """
        room = (
            await self.db.execute(select(Room).where(Room.id == room_id))
        ).scalar_one_or_none()
        if not room:
            raise ValueError("Room not found")

        default_capacity = room.total_rooms if room.total_rooms is not None else 1

        overrides = {
            row.date: row
            for row in (
                await self.db.execute(
                    select(RoomAvailability).where(
                        RoomAvailability.room_id == room_id,
                        RoomAvailability.date >= check_in,
                        RoomAvailability.date < check_out,
                        RoomAvailability.is_deleted == False,
                    )
                )
            )
            .scalars()
            .all()
        }

        nights = [
            check_in + timedelta(days=offset)
            for offset in range((check_out - check_in).days)
        ]
        capacity: dict[date, int] = {}
        blocked: dict[date, bool] = {}
        for night in nights:
            override = overrides.get(night)
            blocked[night] = bool(override and override.is_blocked)
            capacity[night] = (
                override.available_rooms if override is not None else default_capacity
            )
        return nights, capacity, blocked

    async def _room_night_occupancy(
        self,
        room_id: UUID,
        nights: List[date],
        exclude_booking_id: Optional[UUID] = None,
    ) -> dict:
        """How many units of this room type are already taken on each night."""
        if not nights:
            return {}

        query = select(Booking.check_in_date, Booking.check_out_date).where(
            and_(
                Booking.hotel_room_id == room_id,
                Booking.is_deleted == False,
                Booking.status.in_(OCCUPIED_BOOKING_STATUSES),
                Booking.check_in_date.isnot(None),
                Booking.check_out_date.isnot(None),
                Booking.check_in_date <= max(nights),
                Booking.check_out_date > min(nights),
            )
        )
        if exclude_booking_id:
            query = query.where(Booking.id != exclude_booking_id)

        booked = {night: 0 for night in nights}
        for existing_in, existing_out in (await self.db.execute(query)).all():
            for night in nights:
                if existing_in <= night < existing_out:
                    booked[night] += 1
        return booked

    async def _assert_room_available(
        self,
        room_id: UUID,
        check_in: date,
        check_out: date,
        exclude_booking_id: Optional[UUID] = None,
        quantity: int = 1,
    ) -> None:
        """Raise ValueError unless `quantity` units are free for every night.

        Previously any overlapping booking rejected the request, which meant a hotel
        with ten rooms of a type could only ever sell one per night.
        """
        nights, capacity, blocked = await self._room_night_capacity(
            room_id, check_in, check_out
        )
        if not nights:
            raise ValueError("check_out must be after check_in")

        for night in nights:
            if blocked[night]:
                raise ValueError(
                    f"The room is not available on {night.isoformat()}"
                )

        booked = await self._room_night_occupancy(room_id, nights, exclude_booking_id)
        for night in nights:
            remaining = capacity[night] - booked.get(night, 0)
            if remaining < quantity:
                raise ValueError(
                    f"Only {max(remaining, 0)} room(s) left on {night.isoformat()}"
                )

    # ------------------------------------------------------------------
    # Rate & availability calendar
    # ------------------------------------------------------------------

    async def get_room_calendar(
        self, room_id: UUID, start: date, end: date
    ) -> List[dict]:
        """One row per night: price, capacity, how many are sold, what is left."""
        nights, capacity, blocked = await self._room_night_capacity(room_id, start, end)
        booked = await self._room_night_occupancy(room_id, nights)

        room = (
            await self.db.execute(select(Room).where(Room.id == room_id))
        ).scalar_one_or_none()
        default_price = room.price_per_night if room else 0.0

        overrides = {
            row.date: row
            for row in (
                await self.db.execute(
                    select(RoomAvailability).where(
                        RoomAvailability.room_id == room_id,
                        RoomAvailability.date >= start,
                        RoomAvailability.date < end,
                        RoomAvailability.is_deleted == False,
                    )
                )
            )
            .scalars()
            .all()
        }

        calendar = []
        for night in nights:
            override = overrides.get(night)
            sold = booked.get(night, 0)
            total = capacity[night]
            calendar.append({
                "date": night,
                "price": override.price if override and override.price else default_price,
                "available_rooms": total,
                "booked_rooms": sold,
                "remaining_rooms": max(total - sold, 0),
                "is_blocked": blocked[night],
                "notes": override.notes if override else None,
                "has_override": override is not None,
            })
        return calendar

    async def set_room_calendar(
        self,
        room_id: UUID,
        start: date,
        end: date,
        updated_by: UUID,
        price: Optional[float] = None,
        available_rooms: Optional[int] = None,
        is_blocked: Optional[bool] = None,
        notes: Optional[str] = None,
        weekdays: Optional[List[int]] = None,
    ) -> int:
        """Upsert calendar rows across a date range. Returns rows written.

        `weekdays` restricts the change to given days (0=Monday), so a weekend rate is
        one call rather than one per Saturday.

        Only the fields supplied are changed; the rest keep their current value, or fall
        back to the room's defaults when the row is new. That matters because
        `available_rooms` defaults to 0 at the database level — creating a row just to
        set a price would otherwise silently take the room off sale.
        """
        room = (
            await self.db.execute(select(Room).where(Room.id == room_id))
        ).scalar_one_or_none()
        if not room:
            raise ValueError("Room not found")
        if end <= start:
            raise ValueError("end date must be after start date")
        if available_rooms is not None and available_rooms < 0:
            raise ValueError("available_rooms cannot be negative")
        if price is not None and price < 0:
            raise ValueError("price cannot be negative")

        existing = {
            row.date: row
            for row in (
                await self.db.execute(
                    select(RoomAvailability).where(
                        RoomAvailability.room_id == room_id,
                        RoomAvailability.date >= start,
                        RoomAvailability.date < end,
                        RoomAvailability.is_deleted == False,
                    )
                )
            )
            .scalars()
            .all()
        }

        written = 0
        for offset in range((end - start).days):
            night = start + timedelta(days=offset)
            if weekdays is not None and night.weekday() not in weekdays:
                continue

            row = existing.get(night)
            if row is None:
                row = RoomAvailability(
                    room_id=room_id,
                    date=night,
                    price=price if price is not None else room.price_per_night,
                    available_rooms=(
                        available_rooms
                        if available_rooms is not None
                        else (room.total_rooms if room.total_rooms is not None else 1)
                    ),
                    is_blocked=bool(is_blocked),
                    notes=notes,
                    created_by=updated_by,
                )
                self.db.add(row)
            else:
                if price is not None:
                    row.price = price
                if available_rooms is not None:
                    row.available_rooms = available_rooms
                if is_blocked is not None:
                    row.is_blocked = is_blocked
                if notes is not None:
                    row.notes = notes
                row.updated_by = updated_by
            written += 1

        await self.db.commit()
        logger.info(
            "room_calendar_updated",
            room_id=str(room_id),
            start=start.isoformat(),
            end=end.isoformat(),
            rows=written,
            updated_by=str(updated_by),
        )
        return written

    async def get_apartment_calendar(
        self, apartment_id: UUID, start: date, end: date
    ) -> List[dict]:
        """One row per night: price, minimum stay, blocked, and whether it is taken."""
        apartment = (
            await self.db.execute(select(Apartment).where(Apartment.id == apartment_id))
        ).scalar_one_or_none()
        if not apartment:
            raise ValueError("Apartment not found")

        overrides = {
            row.date: row
            for row in (
                await self.db.execute(
                    select(ApartmentAvailability).where(
                        ApartmentAvailability.apartment_id == apartment_id,
                        ApartmentAvailability.date >= start,
                        ApartmentAvailability.date < end,
                        ApartmentAvailability.is_deleted == False,
                    )
                )
            )
            .scalars()
            .all()
        }

        booked_ranges = (
            await self.db.execute(
                select(Booking.check_in_date, Booking.check_out_date).where(
                    and_(
                        Booking.apartment_id == apartment_id,
                        Booking.is_deleted == False,
                        Booking.status.in_(OCCUPIED_BOOKING_STATUSES),
                        Booking.check_in_date.isnot(None),
                        Booking.check_out_date.isnot(None),
                        Booking.check_in_date < end,
                        Booking.check_out_date > start,
                    )
                )
            )
        ).all()

        calendar = []
        for offset in range((end - start).days):
            night = start + timedelta(days=offset)
            override = overrides.get(night)
            is_booked = any(ci <= night < co for ci, co in booked_ranges)
            calendar.append({
                "date": night,
                "price": (
                    override.price
                    if override is not None and override.price is not None
                    else apartment.price_per_night
                ),
                "minimum_nights": (
                    override.minimum_nights
                    if override is not None and override.minimum_nights is not None
                    else (apartment.minimum_nights or 1)
                ),
                "is_blocked": bool(override and override.is_blocked),
                "is_booked": is_booked,
                "notes": override.notes if override else None,
                "has_override": override is not None,
            })
        return calendar

    async def set_apartment_calendar(
        self,
        apartment_id: UUID,
        start: date,
        end: date,
        updated_by: UUID,
        price: Optional[float] = None,
        is_blocked: Optional[bool] = None,
        minimum_nights: Optional[int] = None,
        notes: Optional[str] = None,
        weekdays: Optional[List[int]] = None,
    ) -> int:
        """Upsert apartment calendar rows across a range. Returns rows written."""
        apartment = (
            await self.db.execute(select(Apartment).where(Apartment.id == apartment_id))
        ).scalar_one_or_none()
        if not apartment:
            raise ValueError("Apartment not found")
        if end <= start:
            raise ValueError("end date must be after start date")
        if price is not None and price < 0:
            raise ValueError("price cannot be negative")
        if minimum_nights is not None and minimum_nights < 1:
            raise ValueError("minimum_nights must be at least 1")

        existing = {
            row.date: row
            for row in (
                await self.db.execute(
                    select(ApartmentAvailability).where(
                        ApartmentAvailability.apartment_id == apartment_id,
                        ApartmentAvailability.date >= start,
                        ApartmentAvailability.date < end,
                        ApartmentAvailability.is_deleted == False,
                    )
                )
            )
            .scalars()
            .all()
        }

        written = 0
        for offset in range((end - start).days):
            night = start + timedelta(days=offset)
            if weekdays is not None and night.weekday() not in weekdays:
                continue

            row = existing.get(night)
            if row is None:
                row = ApartmentAvailability(
                    apartment_id=apartment_id,
                    date=night,
                    price=price,
                    is_blocked=bool(is_blocked),
                    minimum_nights=minimum_nights,
                    notes=notes,
                    created_by=updated_by,
                )
                self.db.add(row)
            else:
                if price is not None:
                    row.price = price
                if is_blocked is not None:
                    row.is_blocked = is_blocked
                if minimum_nights is not None:
                    row.minimum_nights = minimum_nights
                if notes is not None:
                    row.notes = notes
                row.updated_by = updated_by
            written += 1

        await self.db.commit()
        logger.info(
            "apartment_calendar_updated",
            apartment_id=str(apartment_id),
            start=start.isoformat(),
            end=end.isoformat(),
            rows=written,
            updated_by=str(updated_by),
        )
        return written

    async def clear_apartment_calendar(
        self, apartment_id: UUID, start: date, end: date, deleted_by: UUID
    ) -> int:
        """Remove overrides so the range falls back to the apartment's defaults."""
        rows = (
            await self.db.execute(
                select(ApartmentAvailability).where(
                    ApartmentAvailability.apartment_id == apartment_id,
                    ApartmentAvailability.date >= start,
                    ApartmentAvailability.date < end,
                    ApartmentAvailability.is_deleted == False,
                )
            )
        ).scalars().all()

        for row in rows:
            row.soft_delete(deleted_by)
        await self.db.commit()
        logger.info(
            "apartment_calendar_cleared",
            apartment_id=str(apartment_id),
            rows=len(rows),
            deleted_by=str(deleted_by),
        )
        return len(rows)

    async def clear_room_calendar(
        self, room_id: UUID, start: date, end: date, deleted_by: UUID
    ) -> int:
        """Remove calendar overrides so the range falls back to the room's defaults."""
        rows = (
            await self.db.execute(
                select(RoomAvailability).where(
                    RoomAvailability.room_id == room_id,
                    RoomAvailability.date >= start,
                    RoomAvailability.date < end,
                    RoomAvailability.is_deleted == False,
                )
            )
        ).scalars().all()

        for row in rows:
            row.soft_delete(deleted_by)
        await self.db.commit()
        logger.info(
            "room_calendar_cleared",
            room_id=str(room_id),
            rows=len(rows),
            deleted_by=str(deleted_by),
        )
        return len(rows)

    async def confirm_after_payment(
        self,
        booking: Booking,
        payment_id: UUID,
    ) -> Booking:
        """Confirm a hotel/apartment booking after successful payment verification."""
        if booking.is_paid and booking.status == BookingStatus.CONFIRMED.value:
            return booking

        if booking.booking_type == BookingType.HOTEL.value:
            if not booking.hotel_room_id or not booking.check_in_date or not booking.check_out_date:
                raise ValueError("Invalid hotel booking details")
            await self._assert_room_available(
                booking.hotel_room_id,
                booking.check_in_date,
                booking.check_out_date,
                exclude_booking_id=booking.id,
            )
        elif booking.booking_type == BookingType.APARTMENT.value:
            if not booking.apartment_id or not booking.check_in_date or not booking.check_out_date:
                raise ValueError("Invalid apartment booking details")
            conflict = await self.db.execute(
                select(Booking.id).where(
                    and_(
                        Booking.apartment_id == booking.apartment_id,
                        Booking.id != booking.id,
                        Booking.is_deleted == False,
                        Booking.status.in_(OCCUPIED_BOOKING_STATUSES),
                        Booking.check_in_date < booking.check_out_date,
                        Booking.check_out_date > booking.check_in_date,
                    )
                )
            )
            if conflict.scalar_one_or_none():
                raise ValueError("The apartment is no longer available for the selected dates")

        booking.is_paid = True
        booking.paid_at = datetime.now(timezone.utc)
        booking.payment_id = payment_id
        booking.status = BookingStatus.CONFIRMED.value
        booking.confirmed_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(booking)
        logger.info(
            "booking_confirmed_after_payment",
            booking_id=str(booking.id),
            payment_id=str(payment_id),
        )

        await self._send_booking_confirmation_email(booking)

        # Tell the property manager a paid booking has landed.
        from app.utils.manager_notify import notify_manager_new_booking

        await notify_manager_new_booking(self.db, booking)
        await self.db.commit()

        return booking

    async def _send_booking_confirmation_email(self, booking: Booking) -> None:
        """Send confirmation email after payment is verified."""
        from app.models.patient import Patient

        patient_result = await self.db.execute(
            select(Patient).options(joinedload(Patient.user)).where(Patient.id == booking.patient_id)
        )
        patient = patient_result.scalar_one_or_none()
        user = patient.user if patient else None
        if not user:
            return

        try:
            if booking.booking_type == BookingType.HOTEL.value and booking.hotel_room_id:
                room_res = await self.db.execute(
                    select(Room).options(joinedload(Room.hotel)).where(Room.id == booking.hotel_room_id)
                )
                room = room_res.scalar_one_or_none()
                if not room:
                    return
                hotel = room.hotel
                nights = max((booking.check_out_date - booking.check_in_date).days, 1) if booking.check_out_date and booking.check_in_date else 1
                html = render_hotel_booking_confirmation_html(
                    guest_name=user.full_name,
                    hotel_name=hotel.name if hotel else "Hotel",
                    room_name=room.name,
                    room_type=room.room_type,
                    check_in_date=booking.check_in_date.strftime("%B %d, %Y") if booking.check_in_date else "",
                    check_out_date=booking.check_out_date.strftime("%B %d, %Y") if booking.check_out_date else "",
                    nights=nights,
                    guest_count=booking.guest_count,
                    total_price=booking.total_price,
                    currency=booking.currency,
                    reference_number=booking.reference_number,
                    special_requests=booking.special_requests,
                )
                subject = f"Hotel Booking Confirmed — {booking.reference_number}"
            elif booking.booking_type == BookingType.APARTMENT.value and booking.apartment_id:
                apt_res = await self.db.execute(
                    select(Apartment).where(Apartment.id == booking.apartment_id)
                )
                apartment = apt_res.scalar_one_or_none()
                if not apartment:
                    return
                nights = max((booking.check_out_date - booking.check_in_date).days, 1) if booking.check_out_date and booking.check_in_date else 1
                address = f"{apartment.address_line1}, {apartment.city}, {apartment.country}"
                html = render_apartment_booking_confirmation_html(
                    guest_name=user.full_name,
                    apartment_name=apartment.name,
                    bedroom_type=apartment.bedroom_type,
                    check_in_date=booking.check_in_date.strftime("%B %d, %Y") if booking.check_in_date else "",
                    check_out_date=booking.check_out_date.strftime("%B %d, %Y") if booking.check_out_date else "",
                    nights=nights,
                    guest_count=booking.guest_count,
                    total_price=booking.total_price,
                    currency=booking.currency,
                    reference_number=booking.reference_number,
                    address=address,
                    special_requests=booking.special_requests,
                )
                subject = f"Apartment Booking Confirmed — {booking.reference_number}"
            else:
                return

            await send_email(
                db=self.db,
                to_email=user.email,
                to_name=user.full_name,
                subject=subject,
                body_html=html,
                category="booking",
                user_id=user.id,
            )
        except Exception as exc:
            logger.error("booking_confirmation_email_failed", booking_id=str(booking.id), error=str(exc))
