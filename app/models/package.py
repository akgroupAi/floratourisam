"""Medical package and package item models."""

import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.utils.enums import PackageCategory

if TYPE_CHECKING:
    from app.models.hospital import Department, Hospital


class MedicalPackage(BaseModel):
    """A pre-defined bundle of medical services offered at a fixed price."""

    __tablename__ = "medical_packages"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    short_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    category: Mapped[str] = mapped_column(
        String(50),
        default=PackageCategory.GENERAL.value,
        nullable=False,
        index=True,
    )

    # Pricing
    price: Mapped[float] = mapped_column(Float, nullable=False)
    discounted_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)

    # Duration / validity
    duration_days: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Optional hospital / department link
    hospital_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Media
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    gallery: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)

    # Visibility
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # Max persons covered per booking
    max_persons: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Textual inclusions / exclusions (JSONB list of strings)
    inclusions: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    exclusions: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    terms_and_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # SEO
    meta_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    meta_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    items: Mapped[List["PackageItem"]] = relationship(
        "PackageItem",
        back_populates="package",
        cascade="all, delete-orphan",
        order_by="PackageItem.display_order",
        lazy="selectin",
    )
    hospital: Mapped[Optional["Hospital"]] = relationship("Hospital", lazy="select")
    department: Mapped[Optional["Department"]] = relationship("Department", lazy="select")

    def __repr__(self) -> str:
        return f"MedicalPackage(id={self.id}, name={self.name!r})"

    @property
    def effective_price(self) -> float:
        """Return discounted price if available, else base price."""
        return self.discounted_price if self.discounted_price is not None else self.price

    @property
    def discount_percentage(self) -> Optional[float]:
        """Percentage saved versus base price, or None if no discount."""
        if self.discounted_price is not None and self.price > 0:
            return round((self.price - self.discounted_price) / self.price * 100, 1)
        return None


class PackageItem(BaseModel):
    """An individual service or component bundled within a MedicalPackage."""

    __tablename__ = "package_items"

    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("medical_packages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    item_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # sessions, nights, times

    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationship back to package
    package: Mapped["MedicalPackage"] = relationship("MedicalPackage", back_populates="items")

    def __repr__(self) -> str:
        return f"PackageItem(id={self.id}, name={self.name!r}, type={self.item_type})"
