"""Knowledge Document schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeDocumentCreate(BaseModel):
    title: str = Field(..., max_length=300)
    category: str = Field(default="general", max_length=50)
    content: str = Field(..., min_length=10)
    summary: Optional[str] = None
    tags: Optional[list[str]] = None
    source_url: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0
    metadata_extra: Optional[dict] = None


class KnowledgeDocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=300)
    category: Optional[str] = Field(None, max_length=50)
    content: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[list[str]] = None
    source_url: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None
    metadata_extra: Optional[dict] = None


class KnowledgeDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    category: str
    content: str
    summary: Optional[str] = None
    tags: Optional[list] = None
    source_url: Optional[str] = None
    is_active: bool
    sort_order: int
    metadata_extra: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[UUID] = None


class KnowledgeDocumentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    category: str
    summary: Optional[str] = None
    tags: Optional[list] = None
    is_active: bool
    sort_order: int
    created_at: Optional[datetime] = None
