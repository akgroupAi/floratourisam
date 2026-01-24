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
    ) -> tuple[List[Payment], int]:
        query = select(Payment).where(Payment.is_deleted == False)
        if user_id:
            query = query.where(Payment.user_id == user_id)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(Payment.created_at.desc())
        query = query.offset(pagination.offset).limit(pagination.page_size)
        payments = (await self.db.execute(query)).scalars().all()

        return list(payments), total

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
        return payment

    async def refund(self, payment: Payment, amount: Optional[float] = None) -> Payment:
        payment.is_refunded = True
        payment.refund_amount = amount or payment.amount
        payment.refunded_at = datetime.now(timezone.utc)
        payment.status = PaymentStatus.REFUNDED.value
        await self.db.commit()
        return payment
