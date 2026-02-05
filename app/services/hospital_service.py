"""Hospital service."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.hospital import Hospital
from app.schemas.common import PaginationParams
from app.schemas.hospital import HospitalCreate, HospitalUpdate

logger = get_logger(__name__)


class HospitalService:
    """Service for hospital operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_list(
        self,
        pagination: PaginationParams,
        search: Optional[str] = None,
        city: Optional[str] = None,
        country: Optional[str] = None,
    ) -> tuple[List[Hospital], int]:
        """Get paginated list of hospitals."""
        query = select(Hospital).where(Hospital.is_active == True)

        if search:
            query = query.where(
                or_(
                    Hospital.name.ilike(f"%{search}%"),
                    Hospital.city.ilike(f"%{search}%"),
                    Hospital.specialties.any(search),
                )
            )
        
        if city:
            query = query.where(Hospital.city.ilike(f"%{city}%"))
        
        if country:
            query = query.where(Hospital.country.ilike(f"%{country}%"))

        # Get count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        query = query.order_by(Hospital.name).offset(pagination.offset).limit(pagination.page_size)
        
        result = await self.db.execute(query)
        hospitals = result.scalars().all()

        return list(hospitals), total

    async def get_by_id(self, hospital_id: UUID) -> Optional[Hospital]:
        """Get hospital by ID."""
        result = await self.db.execute(select(Hospital).where(Hospital.id == hospital_id))
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Hospital]:
        """Get hospital by slug."""
        result = await self.db.execute(select(Hospital).where(Hospital.slug == slug))
        return result.scalar_one_or_none()

    async def create(self, data: HospitalCreate, created_by: Optional[UUID] = None) -> Hospital:
        """Create new hospital."""
        hospital = Hospital(
            **data.model_dump(),
            # Base model handles IDs, but created_by is specific if added to base
        )
        # Note: BaseModel doesn't strictly enforce created_by if not in schema, 
        # but if needed we can add it. app.models.hospital.Hospital doesn't seem 
        # to inherit from a Mixin with created_by, just BaseModel.
        
        self.db.add(hospital)
        await self.db.commit()
        await self.db.refresh(hospital)
        return hospital

    async def update(self, hospital: Hospital, data: HospitalUpdate) -> Hospital:
        """Update hospital."""
        update_data = data.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(hospital, field, value)

        await self.db.commit()
        await self.db.refresh(hospital)
        return hospital
