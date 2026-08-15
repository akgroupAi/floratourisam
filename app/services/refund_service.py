"""The refund queue — computed on cancellation, released by an admin.

Cancelling a booking works out what is owed and parks it here. Money leaves only when
someone approves it, because a Razorpay refund cannot be reversed through the API: an
automatic payout on a policy bug is unrecoverable, whereas an unapproved refund is
merely visible and waiting.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.logging import get_logger
from app.models.booking import Booking
from app.models.patient import Patient
from app.models.payment import Payment
from app.schemas.common import PaginationParams
from app.utils.cancellation import compute_refund

logger = get_logger(__name__)

PENDING = "pending"
PROCESSED = "processed"
REJECTED = "rejected"
FAILED = "failed"


class RefundService:
    """Queue, approve, and reject refunds on cancelled bookings."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_pending(
        self,
        pagination: PaginationParams,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[dict], int]:
        """Refunds awaiting action, oldest request first — longest-waiting customer first."""
        filters = [Booking.is_deleted == False]
        if status:
            filters.append(Booking.refund_status == status)
        else:
            # The working queue: awaiting approval, plus anything the gateway rejected.
            filters.append(Booking.refund_status.in_([PENDING, FAILED]))
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
                .options(joinedload(Booking.patient).joinedload(Patient.user))
                .where(*filters)
                .order_by(Booking.refund_requested_at.asc().nulls_last())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        ).unique().scalars().all()

        now = datetime.now(timezone.utc)
        items = []
        for booking in rows:
            user = booking.patient.user if booking.patient else None
            waiting_hours = None
            if booking.refund_requested_at:
                requested = booking.refund_requested_at
                if requested.tzinfo is None:
                    requested = requested.replace(tzinfo=timezone.utc)
                waiting_hours = round((now - requested).total_seconds() / 3600, 1)

            items.append({
                "booking_id": booking.id,
                "reference_number": booking.reference_number,
                "booking_type": booking.booking_type,
                "patient_name": user.full_name if user else None,
                "patient_email": user.email if user else None,
                "total_price": booking.total_price,
                "platform_fee": booking.platform_fee,
                "cancellation_charge": booking.cancellation_charge,
                "refund_amount": booking.refund_amount,
                "currency": booking.currency,
                "refund_status": booking.refund_status,
                "refund_requested_at": booking.refund_requested_at,
                "waiting_hours": waiting_hours,
                "cancelled_at": booking.cancelled_at,
                "cancellation_reason": booking.cancellation_reason,
                "refund_note": booking.refund_note,
                "payment_id": booking.payment_id,
            })
        return items, total

    async def get_booking(self, booking_id: UUID) -> Optional[Booking]:
        return (
            await self.db.execute(
                select(Booking).where(Booking.id == booking_id, Booking.is_deleted == False)
            )
        ).scalar_one_or_none()

    async def approve(
        self, booking_id: UUID, approved_by: UUID, amount: Optional[float] = None
    ) -> dict:
        """Release a queued refund to Razorpay.

        `amount` overrides the computed figure for the rare case an admin agrees
        something different — a goodwill exception, or a partial settlement.
        """
        booking = await self.get_booking(booking_id)
        if not booking:
            raise ValueError("Booking not found")
        if booking.refund_status == PROCESSED:
            raise ValueError("This refund has already been processed")
        if booking.refund_status == REJECTED:
            raise ValueError("This refund was rejected — reopen it before approving")
        if booking.refund_status not in (PENDING, FAILED):
            raise ValueError("This booking has no refund awaiting approval")
        if not booking.payment_id:
            raise ValueError("No payment is linked to this booking — refund it manually")

        refund_amount = round(amount if amount is not None else (booking.refund_amount or 0.0), 2)
        if refund_amount <= 0:
            raise ValueError("Refund amount must be greater than zero")
        if refund_amount > (booking.total_price or 0) + 0.01:
            raise ValueError("Refund cannot exceed what the customer paid")

        from app.services.razorpay_service import RazorpayService

        try:
            result = await RazorpayService(self.db).refund_payment(
                payment_id=booking.payment_id,
                amount=refund_amount,
                reason=f"Booking {booking.reference_number} cancelled",
            )
        except Exception as exc:  # noqa: BLE001
            # Keep it in the queue rather than losing it — the admin can retry.
            booking.refund_status = FAILED
            booking.refund_note = str(exc)[:500]
            booking.updated_by = approved_by
            await self.db.commit()
            logger.error(
                "refund_gateway_failed",
                booking_id=str(booking_id),
                amount=refund_amount,
                error=str(exc),
            )
            raise ValueError(f"Refund failed at the gateway: {exc}")

        booking.refund_status = PROCESSED
        booking.refund_amount = refund_amount
        booking.refund_processed_at = datetime.now(timezone.utc)
        booking.refund_processed_by = approved_by
        booking.refund_reference = str(result.get("refund_id") or "") or None
        booking.refund_note = None
        booking.updated_by = approved_by
        await self.db.commit()

        logger.info(
            "refund_processed",
            booking_id=str(booking_id),
            amount=refund_amount,
            approved_by=str(approved_by),
            refund_reference=booking.refund_reference,
        )
        return {
            "booking_id": str(booking_id),
            "refund_amount": refund_amount,
            "refund_reference": booking.refund_reference,
            "status": PROCESSED,
        }

    async def reject(self, booking_id: UUID, rejected_by: UUID, reason: str) -> Booking:
        """Decline a queued refund. The reason is kept — the customer will ask."""
        booking = await self.get_booking(booking_id)
        if not booking:
            raise ValueError("Booking not found")
        if booking.refund_status == PROCESSED:
            raise ValueError("This refund has already been paid and cannot be rejected")

        booking.refund_status = REJECTED
        booking.refund_note = reason
        booking.refund_processed_at = datetime.now(timezone.utc)
        booking.refund_processed_by = rejected_by
        booking.updated_by = rejected_by
        await self.db.commit()
        await self.db.refresh(booking)

        logger.info(
            "refund_rejected",
            booking_id=str(booking_id),
            rejected_by=str(rejected_by),
            reason=reason,
        )
        return booking

    async def stats(self) -> dict:
        """Queue health — what is owed, and how long people have been waiting."""
        base = [Booking.is_deleted == False]

        by_status = dict(
            (
                await self.db.execute(
                    select(Booking.refund_status, func.count(Booking.id))
                    .where(*base)
                    .group_by(Booking.refund_status)
                )
            ).all()
        )

        async def total_for(status: str) -> float:
            return float(
                (
                    await self.db.execute(
                        select(func.coalesce(func.sum(Booking.refund_amount), 0.0)).where(
                            *base, Booking.refund_status == status
                        )
                    )
                ).scalar()
                or 0
            )

        pending_value = await total_for(PENDING)
        processed_value = await total_for(PROCESSED)

        oldest = (
            await self.db.execute(
                select(func.min(Booking.refund_requested_at)).where(
                    *base, Booking.refund_status.in_([PENDING, FAILED])
                )
            )
        ).scalar()

        oldest_hours = None
        if oldest:
            if oldest.tzinfo is None:
                oldest = oldest.replace(tzinfo=timezone.utc)
            oldest_hours = round(
                (datetime.now(timezone.utc) - oldest).total_seconds() / 3600, 1
            )

        return {
            "pending": by_status.get(PENDING, 0),
            "failed": by_status.get(FAILED, 0),
            "processed": by_status.get(PROCESSED, 0),
            "rejected": by_status.get(REJECTED, 0),
            "pending_value": round(pending_value, 2),
            "processed_value": round(processed_value, 2),
            "oldest_waiting_hours": oldest_hours,
        }

    async def preview(self, booking: Booking) -> dict:
        """What cancelling this booking right now would refund. Changes nothing."""
        breakdown = compute_refund(booking)
        return {
            "booking_id": str(booking.id),
            "reference_number": booking.reference_number,
            "total_price": booking.total_price,
            "currency": booking.currency,
            **breakdown.as_dict(),
        }
