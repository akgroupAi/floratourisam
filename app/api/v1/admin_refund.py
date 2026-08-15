"""Admin refund queue.

Cancelling a booking computes what is owed and parks it here. Money leaves only when an
admin releases it — a Razorpay refund cannot be reversed through the API, so an
automatic payout on a policy bug is unrecoverable, while an unapproved refund is merely
visible and waiting.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.refund import (
    CancellationPolicyResponse,
    PendingRefundItem,
    RefundApproveRequest,
    RefundApproveResponse,
    RefundRejectRequest,
    RefundStatsResponse,
)
from app.services.refund_service import RefundService
from app.utils.cancellation import policy_summary

router = APIRouter()


@router.get(
    "/stats",
    response_model=RefundStatsResponse,
    dependencies=[RequireAdmin],
    summary="Refund queue statistics",
)
async def get_refund_stats(db: DatabaseSession):
    """
    How much is owed and how long anyone has been waiting.

    `pending_value` is money the platform owes but has not paid. `oldest_waiting_hours`
    is the number to watch — a customer waiting three days for a refund will chase you,
    or charge back.
    """
    return await RefundService(db).stats()


@router.get(
    "/policy",
    response_model=CancellationPolicyResponse,
    summary="The active cancellation policy",
)
async def get_cancellation_policy():
    """
    The rules currently in force. Public — show this on the booking page and in your
    terms, so a customer knows the position before they book rather than after they
    cancel.
    """
    return policy_summary()


@router.get(
    "",
    response_model=PaginatedResponse[PendingRefundItem],
    dependencies=[RequireAdmin],
    summary="Refunds awaiting action",
)
async def list_refunds(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(
        None, description="pending | failed | processed | rejected. Omit for the working queue."
    ),
    search: Optional[str] = Query(None, description="Booking reference"),
):
    """
    The work queue, **longest-waiting customer first**.

    With no `status`, returns what needs action: `pending` plus `failed` — a refund the
    gateway rejected stays in the queue so it can be retried rather than being lost.
    """
    items, total = await RefundService(db).list_pending(
        PaginationParams(page=page, page_size=page_size),
        status=status,
        search=search,
    )
    return PaginatedResponse.create(items, total, page, page_size)


@router.post(
    "/{booking_id}/approve",
    response_model=RefundApproveResponse,
    dependencies=[RequireAdmin],
    summary="Release a refund to Razorpay",
)
async def approve_refund(
    booking_id: UUID,
    data: RefundApproveRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """
    **This moves real money.** It calls Razorpay for the amount and marks the booking
    refunded.

    Send an empty body to pay exactly what the policy calculated. Pass `amount` only to
    override — a goodwill exception, or a partial settlement.

    If the gateway rejects it, the booking is marked `failed` with the error and **stays
    in the queue** so it can be retried. Nothing is silently dropped.
    """
    try:
        return await RefundService(db).approve(
            booking_id, approved_by=current_user.id, amount=data.amount
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/{booking_id}/reject",
    response_model=PendingRefundItem,
    dependencies=[RequireAdmin],
    summary="Decline a refund",
)
async def reject_refund(
    booking_id: UUID,
    data: RefundRejectRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """
    Decline a queued refund — a no-show, a policy dispute settled against the customer.

    The reason is stored and shown on the booking. A refund already paid cannot be
    rejected.
    """
    service = RefundService(db)
    try:
        booking = await service.reject(booking_id, rejected_by=current_user.id, reason=data.reason)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return PendingRefundItem(
        booking_id=booking.id,
        reference_number=booking.reference_number,
        booking_type=booking.booking_type,
        total_price=booking.total_price,
        platform_fee=booking.platform_fee,
        cancellation_charge=booking.cancellation_charge,
        refund_amount=booking.refund_amount,
        currency=booking.currency,
        refund_status=booking.refund_status,
        refund_requested_at=booking.refund_requested_at,
        cancelled_at=booking.cancelled_at,
        cancellation_reason=booking.cancellation_reason,
        refund_note=booking.refund_note,
        payment_id=booking.payment_id,
    )
