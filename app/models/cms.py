"""CMS models for content management."""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.utils.enums import CMSBlockType, CMSPageStatus


class CMSPage(BaseModel):
    """CMS page for dynamic content."""

    __tablename__ = "cms_pages"

    # Page info
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Template
    template: Mapped[str] = mapped_column(
        String(100),
        default="default",
        nullable=False,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default=CMSPageStatus.DRAFT.value,
        nullable=False,
        index=True,
    )
    is_published: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
    )

    # SEO
    meta_title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    meta_description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    meta_keywords: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    canonical_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Open Graph
    og_title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    og_description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    og_image: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Featured image
    featured_image: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Ordering
    display_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Navigation
    show_in_menu: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    menu_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cms_pages.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Access
    requires_auth: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    allowed_roles: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Custom settings
    settings: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    blocks: Mapped[List["CMSBlock"]] = relationship(
        "CMSBlock",
        back_populates="page",
        lazy="selectin",
        order_by="CMSBlock.position",
    )
    children: Mapped[List["CMSPage"]] = relationship(
        "CMSPage",
        back_populates="parent",
        lazy="dynamic",
    )
    parent: Mapped[Optional["CMSPage"]] = relationship(
        "CMSPage",
        remote_side="CMSPage.id",
        back_populates="children",
    )

    def __repr__(self) -> str:
        return f"CMSPage(id={self.id}, slug={self.slug})"


class CMSBlock(BaseModel):
    """CMS content block for pages."""

    __tablename__ = "cms_blocks"

    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cms_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Block info
    name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    block_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # Position and ordering
    position: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    section: Mapped[str] = mapped_column(
        String(50),
        default="main",
        nullable=False,
    )  # header, main, sidebar, footer

    # Content
    title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    subtitle: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Media
    image_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    video_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Configuration (block-type specific)
    config: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )

    # Items for list-based blocks (FAQ, testimonials, features)
    items: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # CTA (Call to Action)
    cta_text: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    cta_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    cta_style: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    # Styling
    background_color: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    text_color: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    custom_css: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    css_classes: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Visibility
    is_visible: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    visible_from: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
    )
    visible_until: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
    )

    # Responsive
    hide_on_mobile: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    hide_on_desktop: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Animation
    animation: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    # Relationships
    page: Mapped["CMSPage"] = relationship(
        "CMSPage",
        back_populates="blocks",
    )

    def __repr__(self) -> str:
        return f"CMSBlock(id={self.id}, type={self.block_type}, position={self.position})"
