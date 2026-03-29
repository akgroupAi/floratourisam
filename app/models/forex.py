"""Forex models."""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Currency(BaseModel):
    """Supported forex currencies."""

    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    exchange_rate: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"Currency(code={self.code}, name={self.name})"


class ForexRequest(BaseModel):
    """Customer forex exchange requests."""

    __tablename__ = "forex_requests"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    from_currency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("currencies.id"), nullable=False)
    to_currency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("currencies.id"), nullable=False)
    
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    calculated_amount: Mapped[float] = mapped_column(Float, nullable=False)
    rate_applied: Mapped[float] = mapped_column(Float, nullable=False)
    
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    additional_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    passport_doc_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    visa_doc_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    medical_doc_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    from_currency = relationship("Currency", foreign_keys=[from_currency_id])
    to_currency = relationship("Currency", foreign_keys=[to_currency_id])

    def __repr__(self):
        return f"ForexRequest(id={self.id}, amount={self.amount})"
