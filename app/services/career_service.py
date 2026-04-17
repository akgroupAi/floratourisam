"""Career service — job positions and applications."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.career import JobApplication, JobPosition
from app.schemas.career import (
    JobApplicationCreate,
    JobApplicationStatusUpdate,
    JobPositionCreate,
    JobPositionUpdate,
)

logger = get_logger(__name__)


class CareerService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Job Positions ─────────────────────────────────────────

    async def create_position(
        self, data: JobPositionCreate, created_by: UUID
    ) -> JobPosition:
        position = JobPosition(
            **data.model_dump(),
            created_by=created_by,
        )
        self.db.add(position)
        await self.db.commit()
        await self.db.refresh(position)
        logger.info("job_position_created", id=str(position.id), title=data.title)
        return position

    async def update_position(
        self, position_id: UUID, data: JobPositionUpdate, updated_by: UUID
    ) -> JobPosition:
        position = await self._get_position(position_id)
        if not position:
            raise ValueError("Job position not found")
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(position, field, value)
        position.updated_by = updated_by
        await self.db.commit()
        await self.db.refresh(position)
        logger.info("job_position_updated", id=str(position_id))
        return position

    async def delete_position(self, position_id: UUID, deleted_by: UUID) -> None:
        position = await self._get_position(position_id)
        if not position:
            raise ValueError("Job position not found")
        position.soft_delete(deleted_by=deleted_by)
        await self.db.commit()
        logger.info("job_position_deleted", id=str(position_id))

    async def get_position(self, position_id: UUID) -> Optional[JobPosition]:
        return await self._get_position(position_id)

    async def get_position_by_slug(self, slug: str) -> Optional[JobPosition]:
        result = await self.db.execute(
            select(JobPosition).where(
                JobPosition.slug == slug,
                JobPosition.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def list_positions(
        self,
        page: int = 1,
        page_size: int = 20,
        active_only: bool = False,
        department: Optional[str] = None,
        employment_type: Optional[str] = None,
        location: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[List[JobPosition], int]:
        query = select(JobPosition).where(JobPosition.is_deleted == False)

        if active_only:
            query = query.where(JobPosition.is_active == True)
        if department:
            query = query.where(JobPosition.department == department)
        if employment_type:
            query = query.where(JobPosition.employment_type == employment_type)
        if location:
            query = query.where(JobPosition.location.ilike(f"%{location}%"))
        if search:
            query = query.where(
                JobPosition.title.ilike(f"%{search}%")
                | JobPosition.department.ilike(f"%{search}%")
                | JobPosition.location.ilike(f"%{search}%")
            )

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = (
            query.order_by(JobPosition.sort_order.asc(), JobPosition.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = await self.db.execute(query)
        return list(rows.scalars().all()), total

    async def get_departments(self) -> List[str]:
        """Return distinct department names (for filter dropdowns)."""
        result = await self.db.execute(
            select(JobPosition.department)
            .where(JobPosition.is_deleted == False, JobPosition.is_active == True)
            .distinct()
            .order_by(JobPosition.department)
        )
        return [row[0] for row in result.all()]

    async def get_locations(self) -> List[str]:
        """Return distinct locations (for filter dropdowns)."""
        result = await self.db.execute(
            select(JobPosition.location)
            .where(JobPosition.is_deleted == False, JobPosition.is_active == True)
            .distinct()
            .order_by(JobPosition.location)
        )
        return [row[0] for row in result.all()]

    # ── Job Applications ──────────────────────────────────────

    async def submit_application(
        self, data: JobApplicationCreate, user_id: Optional[UUID] = None
    ) -> JobApplication:
        # Verify position exists and is active
        position = await self._get_position(data.position_id)
        if not position:
            raise ValueError("Job position not found")
        if not position.is_active:
            raise ValueError("This position is no longer accepting applications")

        application = JobApplication(
            position_id=data.position_id,
            user_id=user_id,
            full_name=data.full_name,
            email=data.email,
            phone=data.phone,
            resume_url=data.resume_url,
            cover_letter=data.cover_letter,
            linkedin_url=data.linkedin_url,
            portfolio_url=data.portfolio_url,
            experience_years=data.experience_years,
            current_company=data.current_company,
            extra_data=data.extra_data,
            status="submitted",
            created_by=user_id,
        )
        self.db.add(application)
        await self.db.commit()
        await self.db.refresh(application)
        logger.info(
            "job_application_submitted",
            application_id=str(application.id),
            position=str(data.position_id),
            email=data.email,
        )
        return application

    async def update_application_status(
        self,
        application_id: UUID,
        data: JobApplicationStatusUpdate,
        reviewed_by: UUID,
    ) -> JobApplication:
        application = await self._get_application(application_id)
        if not application:
            raise ValueError("Application not found")

        valid_statuses = {
            "submitted", "reviewing", "shortlisted", "interview",
            "offered", "hired", "rejected",
        }
        if data.status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(sorted(valid_statuses))}")

        application.status = data.status
        if data.admin_notes:
            application.admin_notes = data.admin_notes
        application.reviewed_by = reviewed_by
        application.reviewed_at = datetime.now(timezone.utc)
        application.updated_by = reviewed_by
        await self.db.commit()
        await self.db.refresh(application)
        logger.info(
            "job_application_status_updated",
            application_id=str(application_id),
            status=data.status,
        )
        return application

    async def get_application(self, application_id: UUID) -> Optional[JobApplication]:
        return await self._get_application(application_id)

    async def list_applications(
        self,
        page: int = 1,
        page_size: int = 20,
        position_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> tuple[List[JobApplication], int]:
        query = select(JobApplication).where(JobApplication.is_deleted == False)
        if position_id:
            query = query.where(JobApplication.position_id == position_id)
        if status:
            query = query.where(JobApplication.status == status)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = (
            query.order_by(JobApplication.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = await self.db.execute(query)
        return list(rows.scalars().all()), total

    # ── Internals ─────────────────────────────────────────────

    async def _get_position(self, position_id: UUID) -> Optional[JobPosition]:
        result = await self.db.execute(
            select(JobPosition).where(
                JobPosition.id == position_id,
                JobPosition.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def _get_application(self, application_id: UUID) -> Optional[JobApplication]:
        result = await self.db.execute(
            select(JobApplication).where(
                JobApplication.id == application_id,
                JobApplication.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()
