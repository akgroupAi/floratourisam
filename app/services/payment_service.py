"""Payment service."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.payment import Payment, PaymentTransaction
from app.schemas.common import PaginationParams
from app.utils.enums import PaymentStatus
from app.utils.helpers import generate_reference_id
from app.utils.notifications import notify

logger = get_logger(__name__)


class PaymentService:
    """Service for payment operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, payment_id: UUID) -> Optional[Payment]:
        result = await self.db.execute(
            select(Payment).where(Payment.id == payment_id, Payment.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_list(
        self, pagination: PaginationParams, user_id: Optional[UUID] = None,
    ) -> tuple[List[dict], int]:
        from app.models.booking import Booking
        from app.models.hotel import Hotel, Room
        from app.models.apartment import Apartment
        from app.models.restaurant import Restaurant

        base_filter = [Payment.is_deleted == False]
        if user_id:
            base_filter.append(Payment.user_id == user_id)

        count_query = select(func.count(Payment.id)).where(*base_filter)
        total = (await self.db.execute(count_query)).scalar() or 0

        stmt = (
            select(
                Payment,
                Booking.booking_type,
                func.coalesce(Hotel.name, Apartment.name, Restaurant.name).label("entity_name"),
            )
            .outerjoin(Booking, Payment.booking_id == Booking.id)
            .outerjoin(Room, Booking.hotel_room_id == Room.id)
            .outerjoin(Hotel, Room.hotel_id == Hotel.id)
            .outerjoin(Apartment, Booking.apartment_id == Apartment.id)
            .outerjoin(Restaurant, Booking.restaurant_id == Restaurant.id)
            .where(*base_filter)
            .order_by(Payment.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )

        rows = (await self.db.execute(stmt)).all()
        result = []
        for payment, booking_type, entity_name in rows:
            d = {c.name: getattr(payment, c.name) for c in payment.__table__.columns}
            d["booking_type"] = booking_type
            d["entity_name"] = entity_name
            result.append(d)

        return result, total

    async def create(self, user_id: UUID, amount: float, method: str, booking_id: Optional[UUID] = None) -> Payment:
        payment = Payment(
            user_id=user_id, booking_id=booking_id,
            reference_number=generate_reference_id("PAY"),
            payment_method=method, status=PaymentStatus.PENDING.value,
            amount=amount, currency="USD",
            processing_fee=amount * 0.029, platform_fee=amount * 0.01,
            net_amount=amount * 0.961,
            initiated_at=datetime.now(timezone.utc),
        )
        self.db.add(payment)
        await self.db.commit()
        await self.db.refresh(payment)
        return payment

    async def complete(self, payment: Payment, txn_id: str) -> Payment:
        payment.status = PaymentStatus.COMPLETED.value
        payment.completed_at = datetime.now(timezone.utc)
        payment.gateway_transaction_id = txn_id
        await self.db.commit()

        # Notify patient about successful payment
        try:
            await notify(
                db=self.db,
                user_id=payment.user_id,
                title="Payment Received",
                message=f"Your payment of {payment.amount} {payment.currency} has been processed successfully.",
                notification_type="payment",
                entity_type="payment",
                entity_id=payment.id,
                action_url=f"/payments/{payment.id}",
            )
        except Exception as exc:
            from app.core.logging import get_logger as _gl
            _gl(__name__).error("payment_notification_failed", error=str(exc))

        return payment

    async def refund(self, payment: Payment, amount: Optional[float] = None) -> Payment:
        payment.is_refunded = True
        payment.refund_amount = amount or payment.amount
        payment.refunded_at = datetime.now(timezone.utc)
        payment.status = PaymentStatus.REFUNDED.value
        await self.db.commit()
        return payment
