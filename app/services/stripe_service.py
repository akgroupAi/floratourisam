"""Stripe payment gateway service."""

import stripe
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.booking import Booking
from app.models.payment import Payment, PaymentTransaction
from app.utils.enums import PaymentStatus
from app.utils.helpers import generate_reference_id

logger = get_logger(__name__)

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:
    """Service for Stripe payment operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_checkout_session(
        self,
        user_id: UUID,
        booking_id: UUID,
        description: Optional[str] = None,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
    ) -> dict:
        """Create a Stripe Checkout Session and a local Payment record."""
        if not settings.STRIPE_SECRET_KEY:
            raise ValueError("Stripe is not configured. Set STRIPE_SECRET_KEY.")

        # Verify booking exists and read amount from it
        booking = await self._get_booking(booking_id)
        if not booking:
            raise ValueError("Booking not found")

        if booking.is_paid:
            raise ValueError("Booking is already paid")

        amount = round(booking.total_price, 2)
        currency_lower = (booking.currency or settings.STRIPE_CURRENCY).lower()
        amount_cents = int(round(amount * 100))

        default_success = f"{settings.FRONTEND_URL}/payments/success?session_id={{CHECKOUT_SESSION_ID}}"
        default_cancel = f"{settings.FRONTEND_URL}/payments/cancel"

        final_success = success_url or default_success
        final_cancel = cancel_url or default_cancel

        # Ensure URLs have a scheme — Stripe requires absolute URLs
        for url in (final_success, final_cancel):
            if url and not url.startswith(("http://", "https://")):
                raise ValueError(
                    f"Invalid URL '{url}': must start with http:// or https://"
                )

        # Create Stripe Checkout Session
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": currency_lower,
                    "unit_amount": amount_cents,
                    "product_data": {
                        "name": description or f"Booking {booking_id}",
                    },
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=final_success,
            cancel_url=final_cancel,
            metadata={
                "booking_id": str(booking_id),
                "user_id": str(user_id),
            },
        )

        # Create local payment record
        processing_fee = amount * 0.029
        platform_fee = amount * 0.01
        net_amount = amount - processing_fee - platform_fee

        payment = Payment(
            user_id=user_id,
            booking_id=booking_id,
            reference_number=generate_reference_id("PAY"),
            payment_method="credit_card",
            status=PaymentStatus.PENDING.value,
            amount=amount,
            currency=currency_lower,
            processing_fee=processing_fee,
            platform_fee=platform_fee,
            net_amount=net_amount,
            gateway="stripe",
            gateway_transaction_id=session.id,
            gateway_response={"checkout_session_id": session.id},
            initiated_at=datetime.now(timezone.utc),
            description=description,
            created_by=user_id,
        )
        self.db.add(payment)
        await self.db.flush()  # Get payment.id before creating transaction

        # Log transaction
        txn = PaymentTransaction(
            payment_id=payment.id,
            transaction_type="checkout_session_created",
            amount=amount,
            currency=currency_lower,
            status="pending",
            gateway_transaction_id=session.id,
            transaction_metadata={"checkout_url": session.url},
        )
        self.db.add(txn)
        await self.db.commit()
        await self.db.refresh(payment)

        logger.info("stripe_checkout_created", payment_id=str(payment.id), session_id=session.id)

        return {
            "payment_id": payment.id,
            "reference_number": payment.reference_number,
            "checkout_url": session.url,
            "session_id": session.id,
            "amount": amount,
            "currency": currency_lower,
        }

    async def create_payment_intent(
        self,
        user_id: UUID,
        booking_id: UUID,
        description: Optional[str] = None,
    ) -> dict:
        """Create a Stripe PaymentIntent for frontend-controlled payments."""
        if not settings.STRIPE_SECRET_KEY:
            raise ValueError("Stripe is not configured. Set STRIPE_SECRET_KEY.")

        booking = await self._get_booking(booking_id)
        if not booking:
            raise ValueError("Booking not found")

        if booking.is_paid:
            raise ValueError("Booking is already paid")

        amount = round(booking.total_price, 2)
        currency_lower = (booking.currency or settings.STRIPE_CURRENCY).lower()
        amount_cents = int(round(amount * 100))

        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency_lower,
            metadata={
                "booking_id": str(booking_id),
                "user_id": str(user_id),
            },
            description=description or f"Booking {booking_id}",
        )

        processing_fee = amount * 0.029
        platform_fee = amount * 0.01
        net_amount = amount - processing_fee - platform_fee

        payment = Payment(
            user_id=user_id,
            booking_id=booking_id,
            reference_number=generate_reference_id("PAY"),
            payment_method="credit_card",
            status=PaymentStatus.PENDING.value,
            amount=amount,
            currency=currency_lower,
            processing_fee=processing_fee,
            platform_fee=platform_fee,
            net_amount=net_amount,
            gateway="stripe",
            gateway_transaction_id=intent.id,
            gateway_response={"payment_intent_id": intent.id},
            initiated_at=datetime.now(timezone.utc),
            description=description,
            created_by=user_id,
        )
        self.db.add(payment)
        await self.db.flush()  # Get payment.id before creating transaction

        txn = PaymentTransaction(
            payment_id=payment.id,
            transaction_type="payment_intent_created",
            amount=amount,
            currency=currency_lower,
            status="pending",
            gateway_transaction_id=intent.id,
        )
        self.db.add(txn)
        await self.db.commit()
        await self.db.refresh(payment)

        logger.info("stripe_intent_created", payment_id=str(payment.id), intent_id=intent.id)

        return {
            "payment_id": payment.id,
            "reference_number": payment.reference_number,
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id,
            "amount": amount,
            "currency": currency_lower,
        }

    async def handle_webhook(self, payload: bytes, sig_header: str) -> dict:
        """Process Stripe webhook events."""
        if not settings.WjaSTRIPE_WEBHOOK_SECRET:
            raise ValueError("Stripe webhook secret not configured")

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except stripe.SignatureVerificationError:
            raise ValueError("Invalid webhook signature")

        event_type = event["type"]
        data_object = event["data"]["object"]

        logger.info("stripe_webhook_received", event_type=event_type)

        if event_type == "checkout.session.completed":
            await self._handle_checkout_completed(data_object)
        elif event_type == "payment_intent.succeeded":
            await self._handle_payment_succeeded(data_object)
        elif event_type == "payment_intent.payment_failed":
            await self._handle_payment_failed(data_object)
        elif event_type == "charge.refunded":
            await self._handle_refund(data_object)

        return {"status": "ok", "event_type": event_type}

    async def refund_payment(
        self,
        payment_id: UUID,
        amount: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> dict:
        """Initiate a refund via Stripe."""
        payment = await self._get_payment(payment_id)
        if not payment:
            raise ValueError("Payment not found")
        if payment.gateway != "stripe":
            raise ValueError("Payment was not processed through Stripe")
        if payment.status != PaymentStatus.COMPLETED.value:
            raise ValueError("Can only refund completed payments")

        # Get the PaymentIntent ID from gateway response
        intent_id = payment.gateway_transaction_id
        if not intent_id:
            raise ValueError("No Stripe transaction ID found")

        refund_params = {"payment_intent": intent_id}
        if amount:
            refund_params["amount"] = int(round(amount * 100))
        if reason:
            refund_params["reason"] = "requested_by_customer"

        refund = stripe.Refund.create(**refund_params)

        refund_amount = amount or payment.amount
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
            gateway_transaction_id=refund.id,
        )
        self.db.add(txn)
        await self.db.commit()

        logger.info("stripe_refund_completed", payment_id=str(payment_id), refund_id=refund.id)

        return {
            "refund_id": refund.id,
            "payment_id": payment.id,
            "amount_refunded": refund_amount,
            "status": payment.status,
        }

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

    async def _get_payment_by_gateway_id(self, gateway_id: str) -> Optional[Payment]:
        result = await self.db.execute(
            select(Payment).where(
                Payment.gateway_transaction_id == gateway_id,
                Payment.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def _handle_checkout_completed(self, session_data: dict):
        """Mark payment as completed after checkout session completes."""
        payment = await self._get_payment_by_gateway_id(session_data["id"])
        if not payment:
            logger.warning("stripe_webhook_payment_not_found", session_id=session_data["id"])
            return

        payment.status = PaymentStatus.COMPLETED.value
        payment.completed_at = datetime.now(timezone.utc)
        payment.gateway_response = dict(session_data)

        # Extract card info if available
        if session_data.get("payment_intent"):
            try:
                intent = stripe.PaymentIntent.retrieve(session_data["payment_intent"])
                if intent.get("charges", {}).get("data"):
                    charge = intent["charges"]["data"][0]
                    card = charge.get("payment_method_details", {}).get("card", {})
                    payment.card_last_four = card.get("last4")
                    payment.card_brand = card.get("brand")
            except Exception as e:
                logger.warning("stripe_card_info_fetch_failed", error=str(e))

        # Update booking
        await self._mark_booking_paid(payment)

        txn = PaymentTransaction(
            payment_id=payment.id,
            transaction_type="checkout_completed",
            amount=payment.amount,
            currency=payment.currency,
            status="completed",
            gateway_transaction_id=session_data.get("payment_intent"),
        )
        self.db.add(txn)
        await self.db.commit()

        logger.info("stripe_checkout_completed", payment_id=str(payment.id))

    async def _handle_payment_succeeded(self, intent_data: dict):
        """Mark payment as completed after PaymentIntent succeeds."""
        payment = await self._get_payment_by_gateway_id(intent_data["id"])
        if not payment:
            logger.warning("stripe_webhook_payment_not_found", intent_id=intent_data["id"])
            return

        payment.status = PaymentStatus.COMPLETED.value
        payment.completed_at = datetime.now(timezone.utc)
        payment.gateway_response = dict(intent_data)

        # Extract card info
        if intent_data.get("charges", {}).get("data"):
            charge = intent_data["charges"]["data"][0]
            card = charge.get("payment_method_details", {}).get("card", {})
            payment.card_last_four = card.get("last4")
            payment.card_brand = card.get("brand")

        await self._mark_booking_paid(payment)

        txn = PaymentTransaction(
            payment_id=payment.id,
            transaction_type="payment_succeeded",
            amount=payment.amount,
            currency=payment.currency,
            status="completed",
            gateway_transaction_id=intent_data["id"],
        )
        self.db.add(txn)
        await self.db.commit()

        logger.info("stripe_payment_succeeded", payment_id=str(payment.id))

    async def _handle_payment_failed(self, intent_data: dict):
        """Mark payment as failed."""
        payment = await self._get_payment_by_gateway_id(intent_data["id"])
        if not payment:
            return

        payment.status = PaymentStatus.FAILED.value
        payment.failed_at = datetime.now(timezone.utc)
        payment.failure_reason = intent_data.get("last_payment_error", {}).get("message")
        payment.failure_code = intent_data.get("last_payment_error", {}).get("code")

        txn = PaymentTransaction(
            payment_id=payment.id,
            transaction_type="payment_failed",
            amount=payment.amount,
            currency=payment.currency,
            status="failed",
            gateway_transaction_id=intent_data["id"],
            error_code=payment.failure_code,
            error_message=payment.failure_reason,
        )
        self.db.add(txn)
        await self.db.commit()

        logger.info("stripe_payment_failed", payment_id=str(payment.id))

    async def _handle_refund(self, charge_data: dict):
        """Handle refund webhook."""
        intent_id = charge_data.get("payment_intent")
        if not intent_id:
            return

        payment = await self._get_payment_by_gateway_id(intent_id)
        if not payment:
            return

        refund_amount = charge_data.get("amount_refunded", 0) / 100
        payment.is_refunded = True
        payment.refund_amount = refund_amount
        payment.refunded_at = datetime.now(timezone.utc)
        payment.status = (
            PaymentStatus.REFUNDED.value
            if refund_amount >= payment.amount
            else PaymentStatus.PARTIALLY_REFUNDED.value
        )
        await self.db.commit()

        logger.info("stripe_refund_webhook", payment_id=str(payment.id), amount=refund_amount)

    async def _mark_booking_paid(self, payment: Payment):
        """Update the linked booking as paid and activate dining pass if applicable."""
        if not payment.booking_id:
            return
        booking = await self._get_booking(payment.booking_id)
        if booking:
            booking.is_paid = True
            booking.paid_at = datetime.now(timezone.utc)
            booking.payment_id = payment.id
            booking.status = "confirmed"

            # Activate dining pass if this booking is for a dining pass purchase
            metadata = booking.booking_metadata or {}
            if metadata.get("type") == "dining_pass" and metadata.get("dining_pass_purchase_id"):
                await self._activate_dining_pass(metadata["dining_pass_purchase_id"])

    async def _activate_dining_pass(self, purchase_id_str: str):
        """Activate a dining pass purchase after successful payment."""
        from uuid import UUID as PyUUID
        from app.models.restaurant import DiningPassPurchase

        try:
            purchase_id = PyUUID(purchase_id_str)
        except ValueError:
            logger.error("invalid_dining_pass_purchase_id", purchase_id=purchase_id_str)
            return

        result = await self.db.execute(
            select(DiningPassPurchase).where(
                DiningPassPurchase.id == purchase_id,
                DiningPassPurchase.is_deleted == False,
            )
        )
        purchase = result.scalar_one_or_none()
        if purchase and purchase.status == "pending":
            purchase.status = "active"
            logger.info("dining_pass_activated", purchase_id=purchase_id_str, ref=purchase.reference_code)
