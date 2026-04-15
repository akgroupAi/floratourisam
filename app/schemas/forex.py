"""Forex schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BaseSchema


# ============== CURRENCY SCHEMAS ==============


class CurrencyCreate(BaseModel):
    """Schema for creating a currency."""
    code: str = Field(..., min_length=2, max_length=10)
    name: str = Field(..., min_length=2, max_length=100)
    symbol: Optional[str] = Field(None, max_length=10)
    buy_rate: float = Field(0.0, ge=0.0)
    sell_rate: float = Field(0.0, ge=0.0)
    is_active: bool = True


class CurrencyUpdate(BaseModel):
    """Schema for updating a currency."""
    code: Optional[str] = Field(None, min_length=2, max_length=10)
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    symbol: Optional[str] = Field(None, max_length=10)
    buy_rate: Optional[float] = Field(None, ge=0.0)
    sell_rate: Optional[float] = Field(None, ge=0.0)
    is_active: Optional[bool] = None


class CurrencyResponse(BaseSchema):
    """Schema for returning a currency."""
    id: UUID
    code: str
    name: str
    symbol: Optional[str] = None
    buy_rate: float
    sell_rate: float
    is_active: bool
    updated_at: datetime

    class Config:
        from_attributes = True


# ============== FOREX REQUEST SCHEMAS ==============


class ForexRequestCreate(BaseModel):
    """Schema for creating a forex request."""
    from_currency_id: UUID
    to_currency_id: UUID
    amount: float = Field(..., gt=0.0)
    purpose: str = Field(..., min_length=2, max_length=255)
    additional_notes: Optional[str] = None


class ForexRequestResponse(BaseSchema):
    """Schema for returning a forex request."""
    id: UUID
    user_id: UUID
    
    from_currency_id: UUID
    to_currency_id: UUID
    from_currency: Optional[CurrencyResponse] = None
    to_currency: Optional[CurrencyResponse] = None

    amount: float
    calculated_amount: float
    rate_applied: float

    purpose: str
    additional_notes: Optional[str] = None

    passport_doc_url: Optional[str] = None
    visa_doc_url: Optional[str] = None
    medical_doc_url: Optional[str] = None

    status: str
    admin_remarks: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ForexRequestStatusUpdate(BaseModel):
    """Schema for updating a forex request status."""
    status: str = Field(..., pattern="^(pending|under_review|approved|rejected|completed)$")
    admin_remarks: Optional[str] = Field(None, max_length=1000)
