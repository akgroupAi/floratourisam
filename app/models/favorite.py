"""Patient favorites / wishlist model."""

import uuid
from typing import Optional

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import SimpleBaseModel


class PatientFavorite(SimpleBaseModel):
    """Persists a patient's saved (bookmarked) entities.

    Supported entity types: doctor, hospital, package, hotel, apartment, restaurant.
    The (patient_id, entity_type, entity_id) triple is unique — toggling the same
    item twice will raise an integrity error caught at the service layer.
    """

    __tablename__ = "patient_favorites"

    __table_args__ = (
        UniqueConstraint("patient_id", "entity_type", "entity_id", name="uq_patient_favorite"),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    entity_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    notes: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"PatientFavorite(patient={self.patient_id}, {self.entity_type}={self.entity_id})"
