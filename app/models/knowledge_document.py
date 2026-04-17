"""Knowledge document model — admin-managed RAG content."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class KnowledgeDocument(BaseModel):
    """Admin-uploaded knowledge document for the RAG chatbot."""

    __tablename__ = "knowledge_documents"

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, default="general", index=True
    )  # general, treatment, policy, faq, procedure, pricing, travel, aftercare
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # short summary for display
    tags: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)  # ["cardiology", "visa", ...]
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    metadata_extra: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
