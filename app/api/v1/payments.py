"""Payment endpoints."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from app.api.deps import CurrentUser, DatabaseSession
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.payment import (
    PaymentGatewayResponse,
    PaymentListResponse,
    PaymentRefundRequest,
    PaymentResponse,
)
from app.services.payment_service import PaymentService

from app.services.razorpay_service import RazorpayService
from pydantic import BaseModel, Field
from typing import Optional
import io

router = APIRouter()


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


# ---------- Razorpay response schemas ----------

class RazorpayOrderResponse(BaseModel):
    """Response from creating a Razorpay order - contains all data needed for frontend checkout."""
    payment_id: str = Field(..., description="Payment record ID for tracking")
    reference_number: str = Field(..., description="Booking reference (e.g., APT-20260530-XXXXX)")
    order_id: str = Field(..., description="Razorpay Order ID - pass to SDK")
    amount: float = Field(..., description="Amount in rupees/currency")
    amount_paise: int = Field(..., description="Amount in smallest unit (paise for INR)")
    currency: str = Field(..., description="Currency code (INR, USD, EUR, etc.)")
    key_id: str = Field(..., description="Razorpay Key ID - pass to SDK for authentication")
    user_name: str = Field(..., description="User name for Razorpay form prefill")
    user_email: str = Field(..., description="User email for Razorpay form prefill")
    description: str = Field(..., description="Payment description for user clarity")
    checkout_method: str = Field(default="razorpay_sdk", description="Integration method: razorpay_sdk uses Razorpay.js modal")
    integration_hint: str = Field(..., description="Frontend integration instructions")
    
    class Config:
        json_schema_extra = {
            "example": {
                "payment_id": "f7c3b8d1-9c5a-4b21-a1d2-3e4f5g6h7i8j",
                "reference_number": "APT-20260530-ABC123",
                "order_id": "order_SvZLidgPYGFjD9",
                "amount": 33.00,
                "amount_paise": 3300,
                "currency": "USD",
                "key_id": "rzp_test_SvYnusY18eShJP",
                "user_name": "John Doe",
                "user_email": "john@example.com",
                "description": "Apartment booking",
                "checkout_method": "razorpay_sdk",
                "integration_hint": "Use order_id and key_id with Razorpay.js SDK to open payment modal"
            }
        }


# ---------- Endpoints ----------

@router.get("", response_model=PaginatedResponse[PaymentListResponse])
async def list_payments(current_user: CurrentUser, db: DatabaseSession, page: int = Query(1), page_size: int = Query(20)):
    """List user's payments."""
    service = PaymentService(db)
    payments, total = await service.get_list(PaginationParams(page=page, page_size=page_size), current_user.id)
    return PaginatedResponse.create(payments, total, page, page_size)


# ========== RAZORPAY ENDPOINTS ==========

@router.post("/razorpay/order", response_model=RazorpayOrderResponse)
async def create_razorpay_order(
    data: RazorpayOrderRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Create a Razorpay Order for payment checkout.
    
    Response includes all data needed for Razorpay SDK integration on frontend:
    - order_id: Pass to Razorpay SDK
    - key_id: Razorpay API key for authentication
    - amount_paise: Amount in smallest currency unit
    
    Frontend Integration:
    1. Include Razorpay SDK: <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
    2. Use response data with Razorpay.js to open payment modal
    3. After user pays, call /razorpay/verify endpoint with payment details
    """
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
    """Refund a payment (Razorpay)."""
    # First get the payment to determine which gateway was used
    service = PaymentService(db)
    payment = await service.get_by_id(payment_id)
    
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    # Verify user owns this payment
    if str(payment.user_id) != str(current_user.id) and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to refund this payment")
    
    # Only support Razorpay
    if payment.gateway != "razorpay":
        raise HTTPException(status_code=400, detail=f"Payment gateway '{payment.gateway}' is not supported or deprecated")
    
    service = RazorpayService(db)
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


@router.get("/{payment_id}/invoice")
async def download_invoice(payment_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Download a PDF invoice for a completed Razorpay payment."""
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    from app.models.payment import Payment
    from app.models.booking import Booking
    from app.models.user import User
    from app.models.hotel import Room
    from app.models.apartment import Apartment
    from app.models.restaurant import Restaurant
    from app.utils.invoice_generator import generate_invoice_pdf

    # Load payment
    pay_result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = pay_result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if str(payment.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    if payment.status not in ("completed", "partially_refunded", "refunded"):
        raise HTTPException(status_code=400, detail="Invoice is only available for completed payments")

    # Load user
    user_result = await db.execute(select(User).where(User.id == payment.user_id))
    user = user_result.scalar_one_or_none()

    # Load booking linked to this payment
    booking = None
    if payment.booking_id:
        bk_result = await db.execute(select(Booking).where(Booking.id == payment.booking_id))
        booking = bk_result.scalar_one_or_none()
    if not booking:
        # Fall back: find booking where payment_id == this payment
        bk_result = await db.execute(select(Booking).where(Booking.payment_id == payment.id))
        booking = bk_result.scalar_one_or_none()

    # Resolve entity name from booking
    entity_name = None
    if booking:
        if booking.hotel_room_id:
            room_res = await db.execute(
                select(Room).options(joinedload(Room.hotel)).where(Room.id == booking.hotel_room_id)
            )
            room = room_res.scalar_one_or_none()
            if room:
                entity_name = room.hotel.name if room.hotel else "Hotel"
        elif booking.apartment_id:
            apt_res = await db.execute(select(Apartment).where(Apartment.id == booking.apartment_id))
            apt = apt_res.scalar_one_or_none()
            entity_name = apt.name if apt else "Apartment"
        elif booking.restaurant_id:
            rest_res = await db.execute(select(Restaurant).where(Restaurant.id == booking.restaurant_id))
            rest = rest_res.scalar_one_or_none()
            entity_name = rest.name if rest else "Restaurant"

    pdf_bytes = generate_invoice_pdf(
        payment_reference=payment.reference_number,
        razorpay_payment_id=payment.gateway_transaction_id,
        payment_status=payment.status,
        payment_method=payment.payment_method,
        paid_at=payment.completed_at,
        booking_reference=booking.reference_number if booking else payment.reference_number,
        booking_type=booking.booking_type if booking else "booking",
        entity_name=entity_name,
        check_in_date=booking.check_in_date if booking else None,
        check_out_date=booking.check_out_date if booking else None,
        guest_count=booking.guest_count if booking else 1,
        base_price=booking.base_price if booking else payment.amount,
        taxes=booking.taxes if booking else 0.0,
        discount=booking.discount if booking else 0.0,
        total_price=booking.total_price if booking else payment.amount,
        currency=payment.currency,
        user_name=user.full_name if user else "Guest",
        user_email=user.email if user else "",
        user_phone=user.phone if user else None,
    )

    filename = f"invoice-{payment.reference_number}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

