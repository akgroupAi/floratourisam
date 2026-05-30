"""Razorpay payment gateway service."""

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import requests
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.booking import Booking
from app.models.payment import Payment, PaymentTransaction
from app.utils.enums import PaymentStatus
from app.utils.helpers import generate_reference_id

logger = get_logger(__name__)

# Razorpay API endpoints
RAZORPAY_API_BASE = "https://api.razorpay.com/v1"


class RazorpayService:
    """Service for Razorpay payment operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.key_id = settings.RAZORPAY_KEY_ID
        self.key_secret = settings.RAZORPAY_KEY_SECRET

    async def create_order(
        self,
        user_id: UUID,
        booking_id: UUID,
        description: Optional[str] = None,
    ) -> dict:
        """Create a Razorpay Order and a local Payment record."""
        if not self.key_id or not self.key_secret:
            raise ValueError("Razorpay is not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET.")

        # Verify booking exists and read amount from it
        booking = await self._get_booking(booking_id)
        if not booking:
            raise ValueError("Booking not found")

        if booking.is_paid:
            raise ValueError("Booking is already paid")

        # Validate amount
        if not booking.total_price or booking.total_price <= 0:
            raise ValueError(f"Invalid booking amount: {booking.total_price}")

        # Get amount in smallest currency unit (paise for INR, cents for USD, etc.)
        amount = round(booking.total_price, 2)
        currency = (booking.currency or settings.RAZORPAY_CURRENCY).upper()
        
        # Validate currency
        if not currency or len(currency) != 3:
            raise ValueError(f"Invalid currency: {currency}")
        
        # Convert to smallest unit: INR → paise (multiply by 100)
        amount_paise = int(round(amount * 100))
        
        # Validate minimum amount (Razorpay requires at least 1 paise)
        if amount_paise < 1:
            raise ValueError(f"Amount too small: {amount_paise} paise")

        # Log order creation attempt
        logger.info(
            "razorpay_order_creation_attempt",
            booking_id=str(booking_id),
            user_id=str(user_id),
            amount_paise=amount_paise,
            currency=currency,
            razorpay_key_id=self.key_id[:10] + "***" if self.key_id else "MISSING"
        )

        # Create Razorpay Order via API
        try:
            order_response = requests.post(
                f"{RAZORPAY_API_BASE}/orders",
                auth=(self.key_id, self.key_secret),
                json={
                    "amount": amount_paise,
                    "currency": currency,
                    "receipt": f"ord_{str(booking_id)[:34]}",  # Max 40 chars (6+34)
                    "notes": {
                        "booking_id": str(booking_id),
                        "user_id": str(user_id),
                        "description": description or f"Booking {booking_id}",
                    },
                },
            )
            order_response.raise_for_status()
            order_data = order_response.json()
        except requests.RequestException as e:
            error_response = None
            try:
                error_response = e.response.json() if hasattr(e, 'response') and e.response is not None else None
            except:
                pass
            logger.error(
                "razorpay_order_creation_failed",
                amount_paise=amount_paise,
                currency=currency,
                booking_id=str(booking_id),
                error=str(e),
                error_response=error_response,
                status_code=e.response.status_code if hasattr(e, 'response') and e.response is not None else None
            )
            raise ValueError(f"Failed to create Razorpay order: {str(e)}")

        # Create local payment record
        processing_fee = amount * 0.029  # 2.9%
        platform_fee = amount * 0.01  # 1%
        net_amount = amount - processing_fee - platform_fee

        payment = Payment(
            user_id=user_id,
            booking_id=booking_id,
            reference_number=generate_reference_id("PAY"),
            payment_method="card",
            status=PaymentStatus.PENDING.value,
            amount=amount,
            currency=currency,
            processing_fee=processing_fee,
            platform_fee=platform_fee,
            net_amount=net_amount,
            gateway="razorpay",
            gateway_transaction_id=order_data.get("id"),
            gateway_response=order_data,
            initiated_at=datetime.now(timezone.utc),
            description=description,
            created_by=user_id,
        )
        self.db.add(payment)
        await self.db.flush()

        # Log transaction
        txn = PaymentTransaction(
            payment_id=payment.id,
            transaction_type="order_created",
            amount=amount,
            currency=currency,
            status="pending",
            gateway_transaction_id=order_data.get("id"),
            transaction_metadata=order_data,
        )
        self.db.add(txn)
        await self.db.commit()
        await self.db.refresh(payment)

        logger.info(
            "razorpay_order_created",
            payment_id=str(payment.id),
            order_id=order_data.get("id"),
        )

        return {
            "payment_id": str(payment.id),
            "reference_number": payment.reference_number,
            "order_id": order_data.get("id"),
            "amount": amount,
            "amount_paise": amount_paise,
            "currency": currency,
            "key_id": self.key_id,
            "user_name": getattr(payment, "user_name", "User"),
            "user_email": getattr(payment, "user_email", ""),
            "description": description or f"Booking {booking_id}",
        }

    async def verify_payment(
        self,
        payment_id: str,
        order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> dict:
        """Verify Razorpay payment signature and mark payment as completed."""
        # Verify webhook signature
        expected_signature = hmac.new(
            self.key_secret.encode(),
            f"{order_id}|{razorpay_payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected_signature, razorpay_signature):
            logger.error("razorpay_signature_mismatch", payment_id=payment_id)
            raise ValueError("Invalid payment signature")

        # Get payment record by gateway_transaction_id (which is order_id)
        payment = await self._get_payment_by_order_id(order_id)
        if not payment:
            logger.error("razorpay_payment_not_found", order_id=order_id)
            raise ValueError("Payment record not found")

        # Mark as completed
        payment.status = PaymentStatus.COMPLETED.value
        payment.gateway_transaction_id = razorpay_payment_id
        payment.completed_at = datetime.now(timezone.utc)

        # Update payment response with full Razorpay payment details
        if not payment.gateway_response:
            payment.gateway_response = {}
        payment.gateway_response["razorpay_payment_id"] = razorpay_payment_id
        payment.gateway_response["razorpay_signature"] = razorpay_signature

        txn = PaymentTransaction(
            payment_id=payment.id,
            transaction_type="payment_verified",
            amount=payment.amount,
            currency=payment.currency,
            status="completed",
            gateway_transaction_id=razorpay_payment_id,
        )
        self.db.add(txn)
        await self.db.commit()
        await self.db.refresh(payment)

        logger.info(
            "razorpay_payment_verified",
            payment_id=str(payment.id),
            razorpay_payment_id=razorpay_payment_id,
        )

        return {
            "payment_id": str(payment.id),
            "status": payment.status,
            "razorpay_payment_id": razorpay_payment_id,
        }

    async def capture_payment(
        self,
        razorpay_payment_id: str,
        amount_paise: int,
    ) -> dict:
        """Capture a Razorpay payment (if using authorized payments)."""
        try:
            response = requests.post(
                f"{RAZORPAY_API_BASE}/payments/{razorpay_payment_id}/capture",
                auth=(self.key_id, self.key_secret),
                json={"amount": amount_paise},
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            error_response = None
            try:
                error_response = e.response.json() if hasattr(e, 'response') and e.response is not None else None
            except:
                pass
            logger.error(
                "razorpay_capture_failed",
                payment_id=razorpay_payment_id,
                amount_paise=amount_paise,
                error=str(e),
                error_response=error_response,
                status_code=e.response.status_code if hasattr(e, 'response') and e.response is not None else None
            )
            raise ValueError(f"Failed to capture payment: {str(e)}")

    async def refund_payment(
        self,
        payment_id: UUID,
        amount: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> dict:
        """Initiate a refund via Razorpay."""
        payment = await self._get_payment(payment_id)
        if not payment:
            raise ValueError("Payment not found")
        if payment.gateway != "razorpay":
            raise ValueError("Payment was not processed through Razorpay")
        if payment.status != PaymentStatus.COMPLETED.value:
            raise ValueError("Can only refund completed payments")

        # Get the Razorpay Payment ID from gateway response
        razorpay_payment_id = payment.gateway_response.get("razorpay_payment_id")
        if not razorpay_payment_id:
            raise ValueError("No Razorpay payment ID found")

        refund_amount = amount or payment.amount
        refund_amount_paise = int(round(refund_amount * 100))

        try:
            refund_response = requests.post(
                f"{RAZORPAY_API_BASE}/payments/{razorpay_payment_id}/refund",
                auth=(self.key_id, self.key_secret),
                json={
                    "amount": refund_amount_paise,
                    "notes": {
                        "reason": reason or "Refund requested",
                    },
                },
            )
            refund_response.raise_for_status()
            refund_data = refund_response.json()
        except requests.RequestException as e:
            error_response = None
            try:
                error_response = e.response.json() if hasattr(e, 'response') and e.response is not None else None
            except:
                pass
            logger.error(
                "razorpay_refund_failed",
                payment_id=str(payment_id),
                razorpay_payment_id=razorpay_payment_id,
                refund_amount_paise=refund_amount_paise,
                error=str(e),
                error_response=error_response,
                status_code=e.response.status_code if hasattr(e, 'response') and e.response is not None else None
            )
            raise ValueError(f"Failed to refund payment: {str(e)}")

        # Update payment record
        payment.is_refunded = True
        payment.refund_amount = refund_amount
        payment.refunded_at = datetime.now(timezone.utc)
        payment.refund_reason = reason
        payment.status = (
            PaymentStatus.REFUNDED.value
            if refund_amount >= payment.amount
            else PaymentStatus.PARTIALLY_REFUNDED.value
        )

        txn = PaymentTransaction(
            payment_id=payment.id,
            transaction_type="refund",
            amount=refund_amount,
            currency=payment.currency,
            status="completed",
            gateway_transaction_id=refund_data.get("id"),
            transaction_metadata=refund_data,
        )
        self.db.add(txn)
        await self.db.commit()

        logger.info(
            "razorpay_refund_completed",
            payment_id=str(payment_id),
            refund_id=refund_data.get("id"),
        )

        return {
            "refund_id": refund_data.get("id"),
            "payment_id": str(payment.id),
            "amount_refunded": refund_amount,
            "status": payment.status,
        }

    async def handle_webhook(self, payload: str, signature: str) -> dict:
        """Process Razorpay webhook events."""
        # Verify webhook signature
        expected_signature = hmac.new(
            self.key_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected_signature, signature):
            logger.error("razorpay_webhook_signature_mismatch")
            raise ValueError("Invalid webhook signature")

        # Parse payload
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            raise ValueError("Invalid webhook payload")

        event_type = event.get("event")
        data = event.get("payload", {}).get("payment", {})

        logger.info("razorpay_webhook_received", event_type=event_type)

        if event_type == "payment.authorized":
            await self._handle_payment_authorized(data)
        elif event_type == "payment.failed":
            await self._handle_payment_failed(data)
        elif event_type == "refund.created":
            await self._handle_refund_created(data)
        elif event_type == "refund.failed":
            await self._handle_refund_failed(data)

        return {"status": "ok", "event_type": event_type}

    # ---- Internal helpers ----

    async def _get_booking(self, booking_id: UUID) -> Optional[Booking]:
        result = await self.db.execute(
            select(Booking).where(Booking.id == booking_id, Booking.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def _get_payment(self, payment_id: UUID) -> Optional[Payment]:
        result = await self.db.execute(
            select(Payment).where(Payment.id == payment_id, Payment.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def _get_payment_by_order_id(self, order_id: str) -> Optional[Payment]:
        result = await self.db.execute(
            select(Payment).where(
                Payment.gateway_transaction_id == order_id,
                Payment.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def _handle_payment_authorized(self, data: dict) -> None:
        """Handle payment.authorized webhook."""
        order_id = data.get("order_id")
        payment_id = data.get("id")

        payment = await self._get_payment_by_order_id(order_id)
        if payment:
            payment.status = PaymentStatus.COMPLETED.value
            payment.gateway_transaction_id = payment_id
            payment.completed_at = datetime.now(timezone.utc)
            await self.db.commit()
            logger.info("razorpay_payment_authorized", payment_id=str(payment.id))

    async def _handle_payment_failed(self, data: dict) -> None:
        """Handle payment.failed webhook."""
        order_id = data.get("order_id")
        error_description = data.get("error_description", "Unknown error")

        payment = await self._get_payment_by_order_id(order_id)
        if payment:
            payment.status = PaymentStatus.FAILED.value
            payment.failed_at = datetime.now(timezone.utc)
            payment.failure_reason = error_description
            await self.db.commit()
            logger.warning(
                "razorpay_payment_failed",
                payment_id=str(payment.id),
                reason=error_description,
            )

    async def _handle_refund_created(self, data: dict) -> None:
        """Handle refund.created webhook."""
        payment_id = data.get("id")

        payment = await self._get_payment_by_order_id(payment_id)
        if payment:
            logger.info("razorpay_refund_processed", payment_id=str(payment.id))

    async def _handle_refund_failed(self, data: dict) -> None:
        """Handle refund.failed webhook."""
        payment_id = data.get("id")
        error_description = data.get("error_description", "Unknown error")

        payment = await self._get_payment_by_order_id(payment_id)
        if payment:
            logger.error(
                "razorpay_refund_failed_webhook",
                payment_id=str(payment.id),
                reason=error_description,
            )
