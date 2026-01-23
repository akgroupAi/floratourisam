"""Payment endpoints."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from app.api.deps import CurrentUser, DatabaseSession
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.payment import PaymentListResponse, PaymentResponse
from app.services.payment_service import PaymentService

router = APIRouter()


@router.get("", response_model=PaginatedResponse[PaymentListResponse])
async def list_payments(current_user: CurrentUser, db: DatabaseSession, page: int = Query(1), page_size: int = Query(20)):
    """List user's payments."""
    service = PaymentService(db)
    payments, total = await service.get_list(PaginationParams(page=page, page_size=page_size), current_user.id)
    return PaginatedResponse.create(payments, total, page, page_size)


@router.post("/initiate")
async def initiate_payment(booking_id: UUID, amount: float, method: str, current_user: CurrentUser, db: DatabaseSession):
    """Initiate a payment."""
    service = PaymentService(db)
    payment = await service.create(current_user.id, amount, method, booking_id)
    return {"payment_id": payment.id, "reference": payment.reference_number}


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Get payment by ID."""
    service = PaymentService(db)
    payment = await service.get_by_id(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


@router.post("/{payment_id}/confirm")
async def confirm_payment(payment_id: UUID, transaction_id: str, db: DatabaseSession):
    """Confirm payment completion."""
    service = PaymentService(db)
    payment = await service.get_by_id(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return await service.complete(payment, transaction_id)
