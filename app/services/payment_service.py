"""Payment service."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select
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
        self,
        pagination: PaginationParams,
        user_id: Optional[UUID] = None,
        status: Optional[str] = None,
        payment_method: Optional[str] = None,
        booking_type: Optional[str] = None,
        from_date=None,
        to_date=None,
    ) -> tuple[List[dict], int]:
        from datetime import timedelta
        from app.models.booking import Booking
        from app.models.hotel import Hotel, Room
        from app.models.apartment import Apartment
        from app.models.restaurant import Restaurant

        conditions = [Payment.is_deleted == False]
        if user_id:
            conditions.append(Payment.user_id == user_id)
        if status:
            if status in ("completed", "confirmed"):
                conditions.append(Payment.status.in_(["completed", "confirmed"]))
            else:
                conditions.append(Payment.status == status)
        if payment_method:
            conditions.append(Payment.payment_method == payment_method)
        if from_date:
            conditions.append(Payment.initiated_at >= datetime(from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc))
        if to_date:
            conditions.append(Payment.initiated_at < datetime(to_date.year, to_date.month, to_date.day, tzinfo=timezone.utc) + timedelta(days=1))

        payment_where = and_(*conditions)

        booking_conditions = [payment_where]
        if booking_type:
            booking_conditions.append(Booking.booking_type == booking_type)
        full_where = and_(*booking_conditions)

        count_base = (
            select(func.count(Payment.id))
            .select_from(Payment)
            .outerjoin(Booking, Payment.booking_id == Booking.id)
            .where(full_where)
        )
        total = (await self.db.execute(count_base)).scalar() or 0

        stmt = (
            select(
                Payment,
                Booking.booking_type,
                func.coalesce(Hotel.name, Apartment.name, Restaurant.name).label("entity_name"),
            )
            .select_from(Payment)
            .outerjoin(Booking, Payment.booking_id == Booking.id)
            .outerjoin(Room, Booking.hotel_room_id == Room.id)
            .outerjoin(Hotel, Room.hotel_id == Hotel.id)
            .outerjoin(Apartment, Booking.apartment_id == Apartment.id)
            .outerjoin(Restaurant, Booking.restaurant_id == Restaurant.id)
            .where(full_where)
            .order_by(Payment.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )

        rows = (await self.db.execute(stmt)).all()
        result = []
        for payment, row_booking_type, entity_name in rows:
            d = {c.name: getattr(payment, c.name) for c in payment.__table__.columns}
            if d.get("status") == "confirmed":
                d["status"] = "completed"
            d["booking_type"] = row_booking_type
            d["entity_name"] = entity_name
            result.append(d)

        return result, total

    # ── Admin-wide views ──────────────────────────────────────
    # The methods above scope to a single user. These deliberately do not, and
    # are only reachable from the admin router.

    async def get_admin_list(
        self,
        pagination: PaginationParams,
        status: Optional[str] = None,
        payment_method: Optional[str] = None,
        gateway: Optional[str] = None,
        booking_type: Optional[str] = None,
        user_id: Optional[UUID] = None,
        search: Optional[str] = None,
        refunded_only: bool = False,
        failed_only: bool = False,
        from_date=None,
        to_date=None,
    ) -> tuple[List[dict], int]:
        """List payments across every user, with the payer attached."""
        from datetime import timedelta

        from app.models.booking import Booking
        from app.models.user import User

        conditions = [Payment.is_deleted == False]
        if status:
            if status in ("completed", "confirmed"):
                conditions.append(Payment.status.in_(["completed", "confirmed"]))
            else:
                conditions.append(Payment.status == status)
        if payment_method:
            conditions.append(Payment.payment_method == payment_method)
        if gateway:
            conditions.append(Payment.gateway == gateway)
        if user_id:
            conditions.append(Payment.user_id == user_id)
        if refunded_only:
            conditions.append(Payment.is_refunded == True)
        if failed_only:
            conditions.append(Payment.status == PaymentStatus.FAILED.value)
        if from_date:
            conditions.append(
                Payment.initiated_at
                >= datetime(from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc)
            )
        if to_date:
            conditions.append(
                Payment.initiated_at
                < datetime(to_date.year, to_date.month, to_date.day, tzinfo=timezone.utc)
                + timedelta(days=1)
            )
        if search:
            like = f"%{search}%"
            conditions.append(
                or_(
                    Payment.reference_number.ilike(like),
                    Payment.gateway_transaction_id.ilike(like),
                    User.email.ilike(like),
                    User.full_name.ilike(like),
                )
            )
        if booking_type:
            conditions.append(Booking.booking_type == booking_type)

        where = and_(*conditions)

        base = (
            select(Payment, User.full_name, User.email, Booking.booking_type)
            .select_from(Payment)
            .outerjoin(User, Payment.user_id == User.id)
            .outerjoin(Booking, Payment.booking_id == Booking.id)
            .where(where)
        )

        total = (
            await self.db.execute(
                select(func.count())
                .select_from(Payment)
                .outerjoin(User, Payment.user_id == User.id)
                .outerjoin(Booking, Payment.booking_id == Booking.id)
                .where(where)
            )
        ).scalar() or 0

        rows = (
            await self.db.execute(
                base.order_by(Payment.created_at.desc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        ).all()

        items = []
        for payment, full_name, email, booking_type_value in rows:
            data = {c.name: getattr(payment, c.name) for c in payment.__table__.columns}
            if data.get("status") == "confirmed":
                data["status"] = "completed"
            data["user_name"] = full_name
            data["user_email"] = email
            data["booking_type"] = booking_type_value
            items.append(data)
        return items, total

    async def get_admin_stats(self, from_date=None, to_date=None) -> dict:
        """Payment totals across the platform, grouped by status, method, and currency."""
        from datetime import timedelta

        conditions = [Payment.is_deleted == False]
        if from_date:
            conditions.append(
                Payment.initiated_at
                >= datetime(from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc)
            )
        if to_date:
            conditions.append(
                Payment.initiated_at
                < datetime(to_date.year, to_date.month, to_date.day, tzinfo=timezone.utc)
                + timedelta(days=1)
            )

        completed = ["completed", "confirmed"]

        by_status_rows = (
            await self.db.execute(
                select(Payment.status, func.count(Payment.id), func.sum(Payment.amount))
                .where(*conditions)
                .group_by(Payment.status)
            )
        ).all()
        by_status = {row[0]: row[1] for row in by_status_rows}
        amount_by_status = {row[0]: float(row[2] or 0) for row in by_status_rows}

        by_method = dict(
            (
                await self.db.execute(
                    select(Payment.payment_method, func.count(Payment.id))
                    .where(*conditions)
                    .group_by(Payment.payment_method)
                )
            ).all()
        )

        revenue_by_currency = {
            currency: float(amount or 0)
            for currency, amount in (
                await self.db.execute(
                    select(Payment.currency, func.sum(Payment.amount))
                    .where(*conditions, Payment.status.in_(completed))
                    .group_by(Payment.currency)
                )
            ).all()
        }

        total_revenue = sum(amount_by_status.get(s, 0.0) for s in completed)
        total_refunded = float(
            (
                await self.db.execute(
                    select(func.sum(Payment.refund_amount)).where(
                        *conditions, Payment.is_refunded == True
                    )
                )
            ).scalar()
            or 0
        )
        successful = sum(by_status.get(s, 0) for s in completed)
        failed = by_status.get(PaymentStatus.FAILED.value, 0)
        total_payments = sum(by_status.values())

        return {
            "total_payments": total_payments,
            "successful_payments": successful,
            "failed_payments": failed,
            "pending_payments": by_status.get(PaymentStatus.PENDING.value, 0),
            "refunded_payments": by_status.get(PaymentStatus.REFUNDED.value, 0),
            "total_revenue": round(total_revenue, 2),
            "total_refunded": round(total_refunded, 2),
            "net_revenue": round(total_revenue - total_refunded, 2),
            "success_rate": round(successful / total_payments * 100, 2) if total_payments else 0.0,
            "failure_rate": round(failed / total_payments * 100, 2) if total_payments else 0.0,
            "payments_by_method": by_method,
            "payments_by_status": by_status,
            "revenue_by_currency": revenue_by_currency,
        }

    async def get_transactions(self, payment_id: UUID) -> List[PaymentTransaction]:
        """Gateway event trail for one payment, oldest first."""
        result = await self.db.execute(
            select(PaymentTransaction)
            .where(PaymentTransaction.payment_id == payment_id)
            .order_by(PaymentTransaction.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_reconciliation(self, limit: int = 100) -> dict:
        """Compare booking totals against completed payments and flag mismatches.

        Three failure modes worth catching: a booking marked paid with no completed
        payment, a booking whose payments do not add up to its total, and a payment
        pointing at a booking that no longer exists.
        """
        from app.models.booking import Booking

        completed = ["completed", "confirmed"]

        paid_per_booking = (
            select(
                Payment.booking_id.label("booking_id"),
                func.sum(Payment.amount).label("paid"),
            )
            .where(
                Payment.is_deleted == False,
                Payment.status.in_(completed),
                Payment.booking_id.isnot(None),
            )
            .group_by(Payment.booking_id)
            .subquery()
        )

        rows = (
            await self.db.execute(
                select(
                    Booking.id,
                    Booking.reference_number,
                    Booking.booking_type,
                    Booking.total_price,
                    Booking.is_paid,
                    Booking.status,
                    func.coalesce(paid_per_booking.c.paid, 0.0).label("paid"),
                )
                .outerjoin(paid_per_booking, Booking.id == paid_per_booking.c.booking_id)
                .where(Booking.is_deleted == False)
                .order_by(Booking.created_at.desc())
                .limit(limit)
            )
        ).all()

        mismatches = []
        for booking_id, reference, booking_type, total_price, is_paid, booking_status, paid in rows:
            total = float(total_price or 0)
            paid = float(paid or 0)
            issue = None
            if is_paid and paid == 0:
                issue = "marked_paid_without_payment"
            elif paid > 0 and abs(paid - total) > 0.01:
                issue = "amount_mismatch"
            elif not is_paid and paid >= total and total > 0:
                issue = "paid_but_not_marked"
            if issue:
                mismatches.append({
                    "booking_id": str(booking_id),
                    "reference_number": reference,
                    "booking_type": booking_type,
                    "booking_status": booking_status,
                    "booking_total": round(total, 2),
                    "amount_paid": round(paid, 2),
                    "difference": round(paid - total, 2),
                    "issue": issue,
                })

        orphaned = (
            await self.db.execute(
                select(func.count(Payment.id))
                .select_from(Payment)
                .outerjoin(Booking, Payment.booking_id == Booking.id)
                .where(
                    Payment.is_deleted == False,
                    Payment.booking_id.isnot(None),
                    Booking.id.is_(None),
                )
            )
        ).scalar() or 0

        return {
            "bookings_checked": len(rows),
            "mismatch_count": len(mismatches),
            "orphaned_payments": orphaned,
            "mismatches": mismatches,
        }

    async def admin_refund(
        self,
        payment: Payment,
        amount: Optional[float],
        reason: str,
        actioned_by: UUID,
    ) -> Payment:
        """Record an admin-initiated refund, full or partial.

        This marks the refund in our records; it does not call the gateway. Issue the
        money back in the Razorpay dashboard, then record it here.
        """
        refund_amount = amount or payment.amount
        already = payment.refund_amount or 0
        if refund_amount + already > payment.amount + 0.01:
            raise ValueError(
                f"Refund of {refund_amount} exceeds refundable balance "
                f"({payment.amount - already} remaining)"
            )

        payment.refund_amount = already + refund_amount
        payment.is_refunded = True
        payment.refunded_at = datetime.now(timezone.utc)
        payment.refund_reason = reason
        payment.status = (
            PaymentStatus.REFUNDED.value
            if payment.refund_amount >= payment.amount - 0.01
            else PaymentStatus.PARTIALLY_REFUNDED.value
        )
        payment.updated_by = actioned_by

        self.db.add(
            PaymentTransaction(
                payment_id=payment.id,
                transaction_type="refund",
                amount=refund_amount,
                currency=payment.currency,
                status="success",
                transaction_metadata={"reason": reason, "actioned_by": str(actioned_by), "source": "admin"},
            )
        )

        await self.db.commit()
        await self.db.refresh(payment)
        logger.info(
            "admin_refund_recorded",
            payment_id=str(payment.id),
            amount=refund_amount,
            actioned_by=str(actioned_by),
        )
        return payment

    async def create(self, user_id: UUID, amount: float, method: str, booking_id: Optional[UUID] = None) -> Payment:
        # The platform fee is already inside `amount` (added at booking time), so read
        # it off the booking rather than re-deriving it and double-counting.
        platform_fee = 0.0
        if booking_id:
            from app.models.booking import Booking

            booking = (
                await self.db.execute(select(Booking).where(Booking.id == booking_id))
            ).scalar_one_or_none()
            platform_fee = round((booking.platform_fee if booking else 0.0) or 0.0, 2)

        processing_fee = round(amount * 0.029, 2)
        payment = Payment(
            user_id=user_id, booking_id=booking_id,
            reference_number=generate_reference_id("PAY"),
            payment_method=method, status=PaymentStatus.PENDING.value,
            amount=amount, currency="USD",
            processing_fee=processing_fee, platform_fee=platform_fee,
            net_amount=round(amount - processing_fee - platform_fee, 2),
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
