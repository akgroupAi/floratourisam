"""Contact form service."""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.site import LeadSubmission
from app.schemas.contact import ContactCreate, ContactStatusUpdate
from app.utils.email_sender import render_contact_lead_email_html, send_email
from app.utils.enums import ContactStatus

logger = get_logger(__name__)

CONTACT_FORM_SOURCE = "contact_page"
LEGACY_PENDING_STATUSES = {ContactStatus.PENDING.value, "new"}


def _status_label(status: str) -> str:
    labels = {
        ContactStatus.PENDING.value: "Pending",
        ContactStatus.IN_PROCESS.value: "In Process",
        ContactStatus.COMPLETED.value: "Completed",
        "new": "Pending",
    }
    return labels.get(status, status.replace("_", " ").title())


def _serialize_contact(lead: LeadSubmission) -> dict:
    status = lead.status or ContactStatus.PENDING.value
    if status == "new":
        status = ContactStatus.PENDING.value
    return {
        "id": lead.id,
        "full_name": lead.name,
        "email": lead.email,
        "phone": lead.phone,
        "country": lead.country,
        "treatment_of_interest": lead.treatment_interest,
        "message": lead.message,
        "status": status,
        "status_label": _status_label(status),
        "is_new": status == ContactStatus.PENDING.value,
        "notes": lead.notes,
        "assigned_to": lead.assigned_to,
        "created_at": lead.created_at,
        "updated_at": lead.updated_at,
    }


class ContactService:
    """Service for contact form submissions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def submit(self, data: ContactCreate) -> LeadSubmission:
        """Save a contact submission and notify admin by email."""
        lead = LeadSubmission(
            name=data.full_name,
            email=data.email,
            phone=data.phone,
            country=data.country,
            treatment_interest=data.treatment_of_interest,
            message=data.message,
            form_source=CONTACT_FORM_SOURCE,
            status=ContactStatus.PENDING.value,
        )
        self.db.add(lead)
        await self.db.flush()

        try:
            await send_email(
                db=self.db,
                to_email=settings.FIRST_SUPERUSER_EMAIL,
                to_name="Admin",
                subject=f"New Contact Inquiry: {data.full_name}",
                body_html=render_contact_lead_email_html(
                    name=data.full_name,
                    email=data.email,
                    phone=data.phone,
                    country=data.country,
                    treatment=data.treatment_of_interest,
                    message=data.message,
                ),
                category="contact_notification",
            )
        except Exception as exc:
            logger.error("contact_admin_email_failed", error=str(exc))

        await self.db.commit()
        await self.db.refresh(lead)
        logger.info("contact_submission_created", contact_id=str(lead.id))
        return lead

    def _contact_filters(self):
        return [
            LeadSubmission.is_deleted == False,
            LeadSubmission.form_source == CONTACT_FORM_SOURCE,
        ]

    async def list_contacts(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        country: Optional[str] = None,
        search: Optional[str] = None,
        new_only: bool = False,
    ) -> Tuple[List[dict], int]:
        """List contact submissions for admin."""
        filters = self._contact_filters()
        if status:
            if status == ContactStatus.PENDING.value:
                filters.append(LeadSubmission.status.in_(list(LEGACY_PENDING_STATUSES)))
            else:
                filters.append(LeadSubmission.status == status)
        if new_only:
            filters.append(LeadSubmission.status.in_(list(LEGACY_PENDING_STATUSES)))
        if country:
            filters.append(LeadSubmission.country.ilike(f"%{country}%"))
        if search:
            filters.append(
                or_(
                    LeadSubmission.name.ilike(f"%{search}%"),
                    LeadSubmission.email.ilike(f"%{search}%"),
                    LeadSubmission.phone.ilike(f"%{search}%"),
                )
            )

        base = select(LeadSubmission).where(*filters)
        total = (await self.db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

        result = await self.db.execute(
            base.order_by(LeadSubmission.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [_serialize_contact(row) for row in result.scalars().all()]
        return items, total

    async def get_stats(self) -> dict:
        """Return contact counts grouped by status."""
        filters = self._contact_filters()
        rows = (
            await self.db.execute(
                select(LeadSubmission.status, func.count(LeadSubmission.id))
                .where(*filters)
                .group_by(LeadSubmission.status)
            )
        ).all()

        counts = {status: count for status, count in rows}
        pending = counts.get(ContactStatus.PENDING.value, 0) + counts.get("new", 0)
        in_process = counts.get(ContactStatus.IN_PROCESS.value, 0)
        completed = counts.get(ContactStatus.COMPLETED.value, 0)
        total = pending + in_process + completed + sum(
            c for s, c in counts.items()
            if s not in {ContactStatus.PENDING.value, "new", ContactStatus.IN_PROCESS.value, ContactStatus.COMPLETED.value}
        )

        return {
            "total": total,
            "pending": pending,
            "in_process": in_process,
            "completed": completed,
            "new_count": pending,
        }

    async def _get_contact(self, contact_id: UUID) -> Optional[LeadSubmission]:
        result = await self.db.execute(
            select(LeadSubmission).where(
                LeadSubmission.id == contact_id,
                *self._contact_filters(),
            )
        )
        return result.scalar_one_or_none()

    async def get_contact(self, contact_id: UUID, viewed_by: Optional[UUID] = None) -> Optional[dict]:
        """Get contact detail; moves pending submissions to in_process when opened."""
        lead = await self._get_contact(contact_id)
        if not lead:
            return None

        current_status = lead.status or ContactStatus.PENDING.value
        if current_status in LEGACY_PENDING_STATUSES:
            lead.status = ContactStatus.IN_PROCESS.value
            lead.updated_at = datetime.now(timezone.utc)
            if viewed_by:
                lead.updated_by = viewed_by
                lead.assigned_to = lead.assigned_to or viewed_by
            await self.db.commit()
            await self.db.refresh(lead)
            logger.info("contact_marked_in_process", contact_id=str(contact_id))

        return _serialize_contact(lead)

    async def update_status(
        self,
        contact_id: UUID,
        data: ContactStatusUpdate,
        updated_by: UUID,
    ) -> dict:
        """Update contact status (typically to completed)."""
        lead = await self._get_contact(contact_id)
        if not lead:
            raise ValueError("Contact submission not found")

        lead.status = data.status.value
        if data.notes is not None:
            lead.notes = data.notes
        lead.updated_by = updated_by
        lead.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(lead)
        logger.info(
            "contact_status_updated",
            contact_id=str(contact_id),
            status=data.status.value,
        )
        return _serialize_contact(lead)
