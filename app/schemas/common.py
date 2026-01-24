"""Common schemas used across the application."""

from datetime import datetime
from typing import Any, Generic, List, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        use_enum_values=True,
        json_encoders={datetime: lambda v: v.isoformat()},
    )


class AuditFieldsMixin(BaseModel):
    """Mixin for audit fields."""

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None


class IDMixin(BaseModel):
    """Mixin for ID field."""

    id: UUID


class TimestampMixin(BaseModel):
    """Mixin for timestamp fields."""

    created_at: datetime
    updated_at: datetime


class PaginationParams(BaseModel):
    """Pagination parameters."""

    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(default=None, description="Field to sort by")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")

    @property
    def offset(self) -> int:
        """Calculate offset for database query."""
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""

    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedResponse[T]":
        """Create a paginated response."""
        pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )


class APIResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""

    success: bool = True
    message: str = "Success"
    data: Optional[T] = None
    errors: Optional[List[dict]] = None
    request_id: Optional[str] = None

    @classmethod
    def ok(
        cls,
        data: Optional[T] = None,
        message: str = "Success",
    ) -> "APIResponse[T]":
        """Create a success response."""
        return cls(success=True, message=message, data=data)

    @classmethod
    def error(
        cls,
        message: str,
        errors: Optional[List[dict]] = None,
    ) -> "APIResponse[T]":
        """Create an error response."""
        return cls(success=False, message=message, errors=errors)


class MessageResponse(BaseModel):
    """Simple message response."""

    success: bool = True
    message: str


class HealthCheck(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str
    environment: str
    timestamp: datetime


class FilterParams(BaseModel):
    """Base filter parameters."""

    search: Optional[str] = Field(default=None, description="Search term")
    is_active: Optional[bool] = Field(default=None, description="Filter by active status")
    created_after: Optional[datetime] = Field(default=None)
    created_before: Optional[datetime] = Field(default=None)


class SortParams(BaseModel):
    """Sort parameters."""

    sort_by: str = Field(default="created_at")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")


class DeleteResponse(BaseModel):
    """Response for delete operations."""

    success: bool = True
    message: str = "Resource deleted successfully"
    id: UUID


class BulkDeleteRequest(BaseModel):
    """Request for bulk delete operations."""

    ids: List[UUID] = Field(..., min_length=1, max_length=100)


class BulkDeleteResponse(BaseModel):
    """Response for bulk delete operations."""

    success: bool = True
    deleted_count: int
    failed_ids: List[UUID] = []
