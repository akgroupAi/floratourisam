"""Favorites / wishlist service.

Handles adding, removing, listing, and checking patient favorites.
Entity details (name, image, subtitle) are enriched per entity_type by
querying the relevant source table so the frontend can display rich cards.
"""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.favorite import PatientFavorite
from app.schemas.favorite import FavoriteCreate, FavoriteCountsResponse, FavoriteNotesUpdate, FavoriteResponse
from app.schemas.common import PaginationParams
from app.utils.enums import FavoriteEntityType

logger = get_logger(__name__)


class FavoriteService:
    """Service for patient favorites / wishlist."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Core reads
    # ------------------------------------------------------------------

    async def get_by_id(self, favorite_id: UUID) -> Optional[PatientFavorite]:
        result = await self.db.execute(
            select(PatientFavorite).where(PatientFavorite.id == favorite_id)
        )
        return result.scalar_one_or_none()

    async def find(
        self,
        patient_id: UUID,
        entity_type: FavoriteEntityType,
        entity_id: UUID,
    ) -> Optional[PatientFavorite]:
        """Return the favorite record if it exists, otherwise None."""
        result = await self.db.execute(
            select(PatientFavorite).where(
                PatientFavorite.patient_id == patient_id,
                PatientFavorite.entity_type == entity_type.value,
                PatientFavorite.entity_id == entity_id,
            )
        )
        return result.scalar_one_or_none()

    async def is_favorited(
        self,
        patient_id: UUID,
        entity_type: FavoriteEntityType,
        entity_id: UUID,
    ) -> tuple[bool, Optional[UUID]]:
        """Return (True, favorite_id) if saved, else (False, None)."""
        fav = await self.find(patient_id, entity_type, entity_id)
        if fav:
            return True, fav.id
        return False, None

    async def get_list(
        self,
        patient_id: UUID,
        pagination: PaginationParams,
        entity_type: Optional[FavoriteEntityType] = None,
    ) -> tuple[List[FavoriteResponse], int]:
        """Return paginated, enriched favorites for a patient."""
        query = select(PatientFavorite).where(PatientFavorite.patient_id == patient_id)
        if entity_type:
            query = query.where(PatientFavorite.entity_type == entity_type.value)

        total = (
            await self.db.execute(select(func.count()).select_from(query.subquery()))
        ).scalar() or 0

        query = query.order_by(PatientFavorite.created_at.desc()).offset(pagination.offset).limit(pagination.page_size)
        rows = list((await self.db.execute(query)).scalars().all())

        enriched = await self._enrich(rows)
        return enriched, total

    async def get_counts(self, patient_id: UUID) -> FavoriteCountsResponse:
        """Count favorites per entity type for the patient."""
        result = await self.db.execute(
            select(PatientFavorite.entity_type, func.count().label("cnt"))
            .where(PatientFavorite.patient_id == patient_id)
            .group_by(PatientFavorite.entity_type)
        )
        counts = {row.entity_type: row.cnt for row in result.all()}
        total = sum(counts.values())
        return FavoriteCountsResponse(total=total, counts=counts)

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    async def add(
        self,
        patient_id: UUID,
        data: FavoriteCreate,
    ) -> FavoriteResponse:
        """Save an entity to favorites. Raises ValueError if already saved."""
        existing = await self.find(patient_id, data.entity_type, data.entity_id)
        if existing:
            raise ValueError("Item is already in your favorites")

        fav = PatientFavorite(
            patient_id=patient_id,
            entity_type=data.entity_type.value,
            entity_id=data.entity_id,
            notes=data.notes,
        )
        self.db.add(fav)
        try:
            await self.db.commit()
            await self.db.refresh(fav)
        except IntegrityError:
            await self.db.rollback()
            raise ValueError("Item is already in your favorites")

        logger.info("favorite_added", patient_id=str(patient_id), type=data.entity_type.value, entity=str(data.entity_id))
        enriched = await self._enrich([fav])
        return enriched[0]

    async def update_notes(
        self,
        fav: PatientFavorite,
        data: FavoriteNotesUpdate,
    ) -> FavoriteResponse:
        """Update the personal note on a saved item."""
        fav.notes = data.notes
        await self.db.commit()
        await self.db.refresh(fav)
        enriched = await self._enrich([fav])
        return enriched[0]

    async def remove(self, fav: PatientFavorite) -> None:
        """Remove a favorite (hard delete — no soft delete needed)."""
        await self.db.delete(fav)
        await self.db.commit()
        logger.info("favorite_removed", favorite_id=str(fav.id))

    # ------------------------------------------------------------------
    # Entity enrichment
    # ------------------------------------------------------------------

    async def _enrich(self, favorites: List[PatientFavorite]) -> List[FavoriteResponse]:
        """Batch-enrich a list of favorites with entity name/image/subtitle."""
        if not favorites:
            return []

        # Group IDs by entity_type for efficient batch queries
        by_type: dict[str, list[UUID]] = {}
        for fav in favorites:
            by_type.setdefault(fav.entity_type, []).append(fav.entity_id)

        entity_map: dict[tuple[str, UUID], dict] = {}

        for etype, ids in by_type.items():
            details = await self._fetch_entity_details(etype, ids)
            for d in details:
                entity_map[(etype, d["id"])] = d

        responses = []
        for fav in favorites:
            detail = entity_map.get((fav.entity_type, fav.entity_id), {})
            responses.append(
                FavoriteResponse(
                    id=fav.id,
                    patient_id=fav.patient_id,
                    entity_type=fav.entity_type,
                    entity_id=fav.entity_id,
                    notes=fav.notes,
                    entity_name=detail.get("name"),
                    entity_image_url=detail.get("image_url"),
                    entity_subtitle=detail.get("subtitle"),
                    created_at=fav.created_at,
                )
            )
        return responses

    async def _fetch_entity_details(self, entity_type: str, ids: List[UUID]) -> List[dict]:
        """Fetch minimal display info from the relevant entity table."""
        from sqlalchemy import select

        if entity_type == FavoriteEntityType.DOCTOR.value:
            from app.models.doctor import Doctor
            from app.models.user import User

            rows = await self.db.execute(
                select(Doctor.id, User.full_name, Doctor.profile_image_url, Doctor.specialization)
                .join(User, Doctor.user_id == User.id)
                .where(Doctor.id.in_(ids), Doctor.is_deleted == False)
            )
            return [
                {"id": r.id, "name": r.full_name, "image_url": r.profile_image_url, "subtitle": r.specialization}
                for r in rows.all()
            ]

        if entity_type == FavoriteEntityType.HOSPITAL.value:
            from app.models.hospital import Hospital

            rows = await self.db.execute(
                select(Hospital.id, Hospital.name, Hospital.logo_url, Hospital.city)
                .where(Hospital.id.in_(ids), Hospital.is_deleted == False)
            )
            return [
                {"id": r.id, "name": r.name, "image_url": r.logo_url, "subtitle": r.city}
                for r in rows.all()
            ]

        if entity_type == FavoriteEntityType.PACKAGE.value:
            from app.models.package import MedicalPackage

            rows = await self.db.execute(
                select(MedicalPackage.id, MedicalPackage.name, MedicalPackage.image_url, MedicalPackage.category)
                .where(MedicalPackage.id.in_(ids), MedicalPackage.is_deleted == False)
            )
            return [
                {"id": r.id, "name": r.name, "image_url": r.image_url, "subtitle": r.category}
                for r in rows.all()
            ]

        if entity_type == FavoriteEntityType.HOTEL.value:
            from app.models.hotel import Hotel

            rows = await self.db.execute(
                select(Hotel.id, Hotel.name, Hotel.cover_image_url, Hotel.city)
                .where(Hotel.id.in_(ids), Hotel.is_deleted == False)
            )
            return [
                {"id": r.id, "name": r.name, "image_url": r.cover_image_url, "subtitle": r.city}
                for r in rows.all()
            ]

        if entity_type == FavoriteEntityType.APARTMENT.value:
            from app.models.apartment import Apartment

            rows = await self.db.execute(
                select(Apartment.id, Apartment.name, Apartment.cover_image_url, Apartment.city)
                .where(Apartment.id.in_(ids), Apartment.is_deleted == False)
            )
            return [
                {"id": r.id, "name": r.name, "image_url": r.cover_image_url, "subtitle": r.city}
                for r in rows.all()
            ]

        if entity_type == FavoriteEntityType.RESTAURANT.value:
            from app.models.restaurant import Restaurant

            rows = await self.db.execute(
                select(Restaurant.id, Restaurant.name, Restaurant.cover_image_url, Restaurant.cuisine_types)
                .where(Restaurant.id.in_(ids), Restaurant.is_deleted == False)
            )
            return [
                {
                    "id": r.id,
                    "name": r.name,
                    "image_url": r.cover_image_url,
                    "subtitle": r.cuisine_types[0] if r.cuisine_types else None,
                }
                for r in rows.all()
            ]

        return []
