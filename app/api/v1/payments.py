"""Payment endpoints."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, Request
from app.api.deps import CurrentUser, DatabaseSession
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.payment import (
    PaymentGatewayResponse,
    PaymentListResponse,
    PaymentRefundRequest,
    PaymentResponse,
)
from app.services.payment_service import PaymentService
from app.services.stripe_service import StripeService
from app.services.razorpay_service import RazorpayService
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter()


# ---------- Stripe request schemas ----------

class StripeCheckoutRequest(BaseModel):
    """Request to create a Stripe Checkout Session."""
    booking_id: UUID
    description: Optional[str] = None
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class StripePaymentIntentRequest(BaseModel):
    """Request to create a Stripe PaymentIntent."""
    booking_id: UUID
    description: Optional[str] = None


# ---------- Razorpay request schemas ----------

class RazorpayOrderRequest(BaseModel):
    """Request to create a Razorpay Order."""
    booking_id: UUID
    description: Optional[str] = None


class RazorpayPaymentVerifyRequest(BaseModel):
    """Request to verify a Razorpay payment."""
    payment_id: str
    order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class RazorpayWebhookRequest(BaseModel):
    """Razorpay webhook payload."""
    event: str
    payload: dict


# ---------- Endpoints ----------

@router.get("", response_model=PaginatedResponse[PaymentListResponse])
async def list_payments(current_user: CurrentUser, db: DatabaseSession, page: int = Query(1), page_size: int = Query(20)):
    """List user's payments."""
    service = PaymentService(db)
    payments, total = await service.get_list(PaginationParams(page=page, page_size=page_size), current_user.id)
    return PaginatedResponse.create(payments, total, page, page_size)


# ========== STRIPE ENDPOINTS (LEGACY) ==========

@router.post("/stripe/checkout")
async def create_stripe_checkout(
    data: StripeCheckoutRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Create a Stripe Checkout Session. Returns a checkout URL to redirect the user to."""
    service = StripeService(db)
    try:
        result = await service.create_checkout_session(
            user_id=current_user.id,
            booking_id=data.booking_id,
            description=data.description,
            success_url=data.success_url,
            cancel_url=data.cancel_url,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/stripe/payment-intent")
async def create_stripe_payment_intent(
    data: StripePaymentIntentRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Create a Stripe PaymentIntent. Returns a client_secret for frontend Stripe.js."""
    service = StripeService(db)
    try:
        result = await service.create_payment_intent(
            user_id=current_user.id,
            booking_id=data.booking_id,
            description=data.description,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: DatabaseSession):
    """Handle Stripe webhook events. Stripe sends payment status updates here."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    service = StripeService(db)
    try:
        result = await service.handle_webhook(payload, sig_header)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== RAZORPAY ENDPOINTS (NEW) ==========

@router.post("/razorpay/order")
async def create_razorpay_order(
    data: RazorpayOrderRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Create a Razorpay Order. Frontend will use this to initiate payment via Razorpay SDK."""
    service = RazorpayService(db)
    try:
        result = await service.create_order(
            user_id=current_user.id,
            booking_id=data.booking_id,
            description=data.description,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/razorpay/verify")
async def verify_razorpay_payment(
    data: RazorpayPaymentVerifyRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Verify a Razorpay payment after successful transaction. Called from frontend after payment."""
    service = RazorpayService(db)
    try:
        result = await service.verify_payment(
            payment_id=data.payment_id,
            order_id=data.order_id,
            razorpay_payment_id=data.razorpay_payment_id,
            razorpay_signature=data.razorpay_signature,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/razorpay/webhook")
async def razorpay_webhook(request: Request, db: DatabaseSession):
    """Handle Razorpay webhook events. Razorpay sends payment status updates here."""
    # Read raw body for signature verification
    payload = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")

    service = RazorpayService(db)
    try:
        # Decode payload for processing
        import json
        payload_str = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        result = await service.handle_webhook(payload_str, signature)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== REFUND ENDPOINT (UNIVERSAL) ==========

@router.post("/{payment_id}/refund")
async def refund_payment(
    payment_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
    reason: Optional[str] = None,
    amount: Optional[float] = None,
):
    """Refund a payment (works for both Stripe and Razorpay)."""
    # First get the payment to determine which gateway was used
    service = PaymentService(db)
    payment = await service.get_by_id(payment_id)
    
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    # Verify user owns this payment
    if str(payment.user_id) != str(current_user.id) and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to refund this payment")
    
    # Route to appropriate service
    if payment.gateway == "stripe":
        service = StripeService(db)
    elif payment.gateway == "razorpay":
        service = RazorpayService(db)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown payment gateway: {payment.gateway}")
    
    try:
        result = await service.refund_payment(
            payment_id=payment_id,
            amount=amount,
            reason=reason,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Get payment by ID."""
    service = PaymentService(db)
    payment = await service.get_by_id(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment

