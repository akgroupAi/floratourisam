"""CMS schemas."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BaseSchema
from app.utils.enums import CMSBlockType, CMSPageStatus


class CMSBlockCreate(BaseModel):
    """CMS block creation."""

    block_type: CMSBlockType
    position: int = Field(default=0, ge=0)
    section: str = Field(default="main", max_length=50)
    name: Optional[str] = Field(default=None, max_length=255)
    title: Optional[str] = Field(default=None, max_length=255)
    subtitle: Optional[str] = Field(default=None, max_length=500)
    content: Optional[str] = None
    image_url: Optional[str] = Field(default=None, max_length=500)
    video_url: Optional[str] = Field(default=None, max_length=500)
    config: Optional[dict] = None
    items: Optional[List[dict]] = None
    cta_text: Optional[str] = Field(default=None, max_length=100)
    cta_url: Optional[str] = Field(default=None, max_length=500)
    cta_style: Optional[str] = Field(default=None, max_length=50)
    background_color: Optional[str] = Field(default=None, max_length=20)
    text_color: Optional[str] = Field(default=None, max_length=20)
    custom_css: Optional[str] = None
    css_classes: Optional[str] = Field(default=None, max_length=255)
    is_visible: bool = True
    visible_from: Optional[datetime] = None
    visible_until: Optional[datetime] = None
    hide_on_mobile: bool = False
    hide_on_desktop: bool = False
    animation: Optional[str] = Field(default=None, max_length=50)


class CMSBlockUpdate(CMSBlockCreate):
    """CMS block update."""

    block_type: Optional[CMSBlockType] = None
    position: Optional[int] = Field(default=None, ge=0)


class CMSBlockResponse(BaseSchema):
    """CMS block response."""

    id: UUID
    page_id: UUID
    block_type: str
    position: int
    section: str
    name: Optional[str] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    content: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    config: Optional[dict] = None
    items: Optional[List[dict]] = None
    cta_text: Optional[str] = None
    cta_url: Optional[str] = None
    cta_style: Optional[str] = None
    background_color: Optional[str] = None
    text_color: Optional[str] = None
    css_classes: Optional[str] = None
    is_visible: bool
    visible_from: Optional[datetime] = None
    visible_until: Optional[datetime] = None
    hide_on_mobile: bool
    hide_on_desktop: bool
    animation: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CMSBlockReorderRequest(BaseModel):
    """Block reorder request."""

    block_id: UUID
    new_position: int = Field(..., ge=0)


class CMSPageCreate(BaseModel):
    """CMS page creation."""

    title: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=255, pattern="^[a-z0-9-]+$")
    description: Optional[str] = None
    template: str = Field(default="default", max_length=100)
    status: CMSPageStatus = CMSPageStatus.DRAFT

    # SEO
    meta_title: Optional[str] = Field(default=None, max_length=255)
    meta_description: Optional[str] = Field(default=None, max_length=500)
    meta_keywords: Optional[str] = Field(default=None, max_length=500)
    canonical_url: Optional[str] = Field(default=None, max_length=500)

    # Open Graph
    og_title: Optional[str] = Field(default=None, max_length=255)
    og_description: Optional[str] = Field(default=None, max_length=500)
    og_image: Optional[str] = Field(default=None, max_length=500)

    # Media
    featured_image: Optional[str] = Field(default=None, max_length=500)

    # Navigation
    show_in_menu: bool = False
    menu_order: int = Field(default=0)
    parent_id: Optional[UUID] = None

    # Access
    requires_auth: bool = False
    allowed_roles: Optional[List[str]] = None

    # Settings
    settings: Optional[dict] = None

    # Blocks
    blocks: Optional[List[CMSBlockCreate]] = None


class CMSPageUpdate(BaseModel):
    """CMS page update."""

    title: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    template: Optional[str] = Field(default=None, max_length=100)
    status: Optional[CMSPageStatus] = None

    # SEO
    meta_title: Optional[str] = Field(default=None, max_length=255)
    meta_description: Optional[str] = Field(default=None, max_length=500)
    meta_keywords: Optional[str] = Field(default=None, max_length=500)
    canonical_url: Optional[str] = Field(default=None, max_length=500)

    # Open Graph
    og_title: Optional[str] = Field(default=None, max_length=255)
    og_description: Optional[str] = Field(default=None, max_length=500)
    og_image: Optional[str] = Field(default=None, max_length=500)

    # Media
    featured_image: Optional[str] = Field(default=None, max_length=500)

    # Navigation
    show_in_menu: Optional[bool] = None
    menu_order: Optional[int] = None
    parent_id: Optional[UUID] = None

    # Access
    requires_auth: Optional[bool] = None
    allowed_roles: Optional[List[str]] = None

    # Settings
    settings: Optional[dict] = None


class CMSPageListResponse(BaseSchema):
    """CMS page list response."""

    id: UUID
    title: str
    slug: str
    status: str
    is_published: bool
    template: str
    show_in_menu: bool
    menu_order: int
    parent_id: Optional[UUID] = None
    block_count: int = 0
    created_at: datetime
    updated_at: datetime


class CMSPageResponse(BaseSchema):
    """CMS page response."""

    id: UUID
    title: str
    slug: str
    description: Optional[str] = None
    template: str
    status: str
    is_published: bool
    published_at: Optional[datetime] = None

    # SEO
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: Optional[str] = None
    canonical_url: Optional[str] = None

    # Open Graph
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None

    # Media
    featured_image: Optional[str] = None

    # Navigation
    display_order: int
    show_in_menu: bool
    menu_order: int
    parent_id: Optional[UUID] = None

    # Access
    requires_auth: bool
    allowed_roles: Optional[dict] = None

    # Settings
    settings: Optional[dict] = None

    # Blocks
    blocks: List[CMSBlockResponse] = []

    # Timestamps
    created_at: datetime
    updated_at: datetime


class CMSPagePublicResponse(BaseModel):
    """Public CMS page response (for frontend)."""

    title: str
    slug: str
    description: Optional[str] = None
    template: str

    # SEO
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: Optional[str] = None
    canonical_url: Optional[str] = None

    # Open Graph
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None

    # Media
    featured_image: Optional[str] = None

    # Blocks (ordered by position)
    blocks: List[CMSBlockResponse] = []


class CMSMenuResponse(BaseModel):
    """CMS menu response."""

    items: List["CMSMenuItemResponse"]


class CMSMenuItemResponse(BaseModel):
    """CMS menu item response."""

    id: UUID
    title: str
    slug: str
    url: str
    order: int
    children: List["CMSMenuItemResponse"] = []


# Forward reference update
CMSMenuItemResponse.model_rebuild()
