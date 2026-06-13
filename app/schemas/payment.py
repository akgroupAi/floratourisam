"""Payment schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BaseSchema
from app.utils.enums import PaymentMethod, PaymentStatus


class PaymentCreate(BaseModel):
    """Payment creation schema."""

    booking_id: Optional[UUID] = None
    amount: float = Field(..., gt=0)
    currency: str = Field(default="USD", max_length=3)
    payment_method: PaymentMethod
    description: Optional[str] = Field(default=None, max_length=500)
    billing_address: Optional[dict] = None


class PaymentInitiateRequest(BaseModel):
    """Payment initiation request."""

    booking_id: UUID
    payment_method: PaymentMethod
    return_url: Optional[str] = None
    billing_address: Optional[dict] = None


class PaymentConfirmRequest(BaseModel):
    """Payment confirmation request."""

    payment_id: UUID
    gateway_transaction_id: str


class PaymentRefundRequest(BaseModel):
    """Payment refund request."""

    payment_id: UUID
    amount: Optional[float] = Field(default=None, gt=0)  # None = full refund
    reason: str = Field(..., max_length=500)


class PaymentListResponse(BaseSchema):
    """Payment list response."""

    id: UUID
    reference_number: str
    booking_id: Optional[UUID] = None
    amount: float
    currency: str
    payment_method: str
    status: str
    initiated_at: datetime
    completed_at: Optional[datetime] = None
    is_refunded: bool
    booking_type: Optional[str] = None
    entity_name: Optional[str] = None


class PaymentResponse(BaseSchema):
    """Payment detail response."""

    id: UUID
    user_id: UUID
    booking_id: Optional[UUID] = None
    reference_number: str
    payment_method: str
    status: str

    # Amount
    amount: float
    currency: str
    exchange_rate: Optional[float] = None
    amount_in_base_currency: Optional[float] = None

    # Fees
    processing_fee: float
    platform_fee: float
    net_amount: float

    # Gateway
    gateway: Optional[str] = None
    gateway_transaction_id: Optional[str] = None

    # Timestamps
    initiated_at: datetime
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None

    # Error
    failure_reason: Optional[str] = None
    failure_code: Optional[str] = None

    # Refund
    is_refunded: bool
    refund_amount: Optional[float] = None
    refunded_at: Optional[datetime] = None
    refund_reason: Optional[str] = None

    # Card (masked)
    card_last_four: Optional[str] = None
    card_brand: Optional[str] = None

    # Invoice
    invoice_id: Optional[str] = None
    invoice_url: Optional[str] = None

    # Description
    description: Optional[str] = None

    # Timestamps
    created_at: datetime


class PaymentGatewayResponse(BaseModel):
    """Payment gateway response for frontend."""

    payment_id: UUID
    gateway: str
    client_secret: Optional[str] = None
    checkout_url: Optional[str] = None
    expires_at: Optional[datetime] = None


class PaymentTransactionResponse(BaseSchema):
    """Payment transaction log response."""

    id: UUID
    payment_id: UUID
    transaction_type: str
    amount: float
    currency: str
    status: str
    gateway_transaction_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime


class PaymentStatsResponse(BaseModel):
    """Payment statistics."""

    total_payments: int
    successful_payments: int
    failed_payments: int
    total_revenue: float
    total_refunded: float
    net_revenue: float
    payments_by_method: dict[str, int]
    payments_by_status: dict[str, int]
    revenue_by_currency: dict[str, float]
