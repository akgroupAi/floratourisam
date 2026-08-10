"""Admin payment monitoring — platform-wide transaction visibility.

The public `/payments` router is deliberately scoped to the calling user. Everything
here spans all users and is admin-gated.
"""

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.payment import (
    AdminPaymentListResponse,
    AdminPaymentStatsResponse,
    AdminRefundRequest,
    PaymentResponse,
    PaymentTransactionResponse,
    ReconciliationResponse,
)
from app.services.payment_service import PaymentService

router = APIRouter()


@router.get(
    "/stats",
    response_model=AdminPaymentStatsResponse,
    dependencies=[RequireAdmin],
    summary="Payment statistics",
)
async def get_payment_stats(
    db: DatabaseSession,
    from_date: Optional[date] = Query(None, description="Filter from this date (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="Filter to this date, inclusive"),
):
    """Totals, success/failure rates, and revenue split by method, status, and currency."""
    service = PaymentService(db)
    return await service.get_admin_stats(from_date=from_date, to_date=to_date)


@router.get(
    "/reconciliation",
    response_model=ReconciliationResponse,
    dependencies=[RequireAdmin],
    summary="Reconcile bookings against payments",
)
async def get_reconciliation(
    db: DatabaseSession,
    limit: int = Query(100, ge=1, le=1000, description="Most recent bookings to check"),
):
    """
    Flag bookings whose money does not add up.

    Catches three cases: a booking marked paid with no completed payment, a booking
    whose payments do not match its total, and payments pointing at a deleted booking.
    """
    service = PaymentService(db)
    return await service.get_reconciliation(limit=limit)


@router.get(
    "",
    response_model=PaginatedResponse[AdminPaymentListResponse],
    dependencies=[RequireAdmin],
    summary="List all payments",
)
async def list_payments(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="pending, processing, completed, failed, refunded, partially_refunded"),
    payment_method: Optional[str] = Query(None),
    gateway: Optional[str] = Query(None, description="e.g. razorpay"),
    booking_type: Optional[str] = Query(None, description="hotel, apartment, restaurant"),
    user_id: Optional[UUID] = Query(None, description="Payments from one user"),
    search: Optional[str] = Query(None, description="Reference number, gateway txn id, payer name or email"),
    refunded_only: bool = Query(False),
    failed_only: bool = Query(False, description="Shortcut for triaging failures"),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
):
    """List payments across every user, newest first."""
    service = PaymentService(db)
    items, total = await service.get_admin_list(
        PaginationParams(page=page, page_size=page_size),
        status=status,
        payment_method=payment_method,
        gateway=gateway,
        booking_type=booking_type,
        user_id=user_id,
        search=search,
        refunded_only=refunded_only,
        failed_only=failed_only,
        from_date=from_date,
        to_date=to_date,
    )
    return PaginatedResponse.create(items, total, page, page_size)


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    dependencies=[RequireAdmin],
    summary="Get payment detail",
)
async def get_payment(payment_id: UUID, db: DatabaseSession):
    """Full payment record for any user."""
    service = PaymentService(db)
    payment = await service.get_by_id(payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return payment


@router.get(
    "/{payment_id}/transactions",
    response_model=list[PaymentTransactionResponse],
    dependencies=[RequireAdmin],
    summary="Gateway transaction trail",
)
async def get_payment_transactions(payment_id: UUID, db: DatabaseSession):
    """
    Every gateway event recorded for this payment — authorization, capture, refund, void —
    oldest first. This is what explains a failed or disputed payment.
    """
    service = PaymentService(db)
    payment = await service.get_by_id(payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return await service.get_transactions(payment_id)


@router.post(
    "/{payment_id}/refund",
    response_model=PaymentResponse,
    dependencies=[RequireAdmin],
    summary="Record a refund",
)
async def refund_payment(
    payment_id: UUID,
    data: AdminRefundRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """
    Record a full or partial refund against a payment.

    **This records the refund in our system; it does not move money.** Issue the refund
    in the payment gateway first, then record it here so our totals stay correct.
    Partial refunds accumulate and set status to `partially_refunded` until the full
    amount is reached.
    """
    service = PaymentService(db)
    payment = await service.get_by_id(payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    try:
        return await service.admin_refund(
            payment, data.amount, data.reason, actioned_by=current_user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
