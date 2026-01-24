"""Payment model for transaction management."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.utils.enums import PaymentMethod, PaymentStatus


class Payment(BaseModel):
    """Payment model for handling transactions."""

    __tablename__ = "payments"

    # User and booking
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    booking_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )  # Generic reference

    # Payment details
    reference_number: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    payment_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=PaymentStatus.PENDING.value,
        nullable=False,
        index=True,
    )

    # Amount
    amount: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        nullable=False,
    )
    exchange_rate: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    amount_in_base_currency: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    # Fees
    processing_fee: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    platform_fee: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    net_amount: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # Gateway details
    gateway: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )  # stripe, paypal, etc.
    gateway_transaction_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    gateway_response: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Timestamps
    initiated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    failed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Error handling
    failure_reason: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    failure_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    # Refund
    is_refunded: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    refund_amount: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    refunded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    refund_reason: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Card details (masked)
    card_last_four: Mapped[Optional[str]] = mapped_column(
        String(4),
        nullable=True,
    )
    card_brand: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    # Billing address
    billing_address: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Description
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Invoice
    invoice_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    invoice_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Relationships
    transactions: Mapped[list["PaymentTransaction"]] = relationship(
        "PaymentTransaction",
        back_populates="payment",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"Payment(id={self.id}, ref={self.reference_number}, status={self.status})"


class PaymentTransaction(BaseModel):
    """Transaction log for payment events."""

    __tablename__ = "payment_transactions"

    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Transaction details
    transaction_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # authorization, capture, refund, void
    amount: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # Gateway
    gateway_transaction_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    gateway_response: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Error details
    error_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Metadata
    transaction_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # IP tracking
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
    )

    # Relationships
    payment: Mapped["Payment"] = relationship(
        "Payment",
        back_populates="transactions",
    )
