"""Quote request service ('Get a Free Medical Plan Quote' form)."""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.site import LeadSubmission
from app.schemas.quote import QuoteStatusUpdate
from app.utils.email_sender import render_quote_lead_email_html, send_email
from app.utils.enums import QuoteStatus

logger = get_logger(__name__)

QUOTE_FORM_SOURCE = "quote_form"


def _status_label(status: str) -> str:
    labels = {
        QuoteStatus.NEW.value: "New",
        QuoteStatus.CONTACTED.value: "Contacted",
        QuoteStatus.QUALIFIED.value: "Qualified",
        QuoteStatus.CONVERTED.value: "Converted",
    }
    return labels.get(status, status.replace("_", " ").title())


def _serialize_quote(lead: LeadSubmission) -> dict:
    status = lead.status or QuoteStatus.NEW.value
    documents = lead.documents or []
    return {
        "id": lead.id,
        "full_name": lead.name,
        "email": lead.email,
        "phone": lead.phone,
        "country": lead.country,
        "medical_condition": lead.medical_condition,
        "treatment_of_interest": lead.treatment_interest,
        "preferred_destination": lead.preferred_destination,
        "message": lead.message,
        "documents": documents,
        "document_count": len(documents),
        "status": status,
        "status_label": _status_label(status),
        "is_new": status == QuoteStatus.NEW.value,
        "notes": lead.notes,
        "assigned_to": lead.assigned_to,
        "utm_source": lead.utm_source,
        "utm_medium": lead.utm_medium,
        "utm_campaign": lead.utm_campaign,
        "created_at": lead.created_at,
        "updated_at": lead.updated_at,
    }


class QuoteService:
    """Service for medical plan quote requests."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def notify_admin(self, lead: LeadSubmission) -> None:
        """Email the admin about a new quote request. Never raises — best effort."""
        try:
            await send_email(
                db=self.db,
                to_email=settings.FIRST_SUPERUSER_EMAIL,
                to_name="Admin",
                subject=f"New Quote Request: {lead.medical_condition or 'Medical Plan'} ({lead.country or 'Unknown'})",
                body_html=render_quote_lead_email_html(
                    name=lead.name,
                    email=lead.email,
                    phone=lead.phone,
                    country=lead.country,
                    medical_condition=lead.medical_condition,
                    treatment=lead.treatment_interest,
                    message=lead.message,
                    document_count=len(lead.documents or []),
                ),
                category="quote_notification",
            )
        except Exception as exc:
            logger.error("quote_admin_email_failed", error=str(exc))

    def _quote_filters(self):
        # Legacy quote rows predate form_source tagging, so NULL counts as a quote.
        return [
            LeadSubmission.is_deleted == False,
            or_(
                LeadSubmission.form_source == QUOTE_FORM_SOURCE,
                LeadSubmission.form_source.is_(None),
            ),
        ]

    async def list_quotes(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        country: Optional[str] = None,
        medical_condition: Optional[str] = None,
        search: Optional[str] = None,
        new_only: bool = False,
        has_documents: Optional[bool] = None,
        sort_by: str = "created_at",
    ) -> Tuple[List[dict], int]:
        """List quote submissions for admin."""
        filters = self._quote_filters()
        if status:
            filters.append(LeadSubmission.status == status)
        if new_only:
            filters.append(LeadSubmission.status == QuoteStatus.NEW.value)
        if country:
            filters.append(LeadSubmission.country.ilike(f"%{country}%"))
        if medical_condition:
            filters.append(LeadSubmission.medical_condition.ilike(f"%{medical_condition}%"))
        if search:
            filters.append(
                or_(
                    LeadSubmission.name.ilike(f"%{search}%"),
                    LeadSubmission.email.ilike(f"%{search}%"),
                    LeadSubmission.phone.ilike(f"%{search}%"),
                )
            )
        if has_documents is True:
            filters.append(LeadSubmission.documents.isnot(None))
        elif has_documents is False:
            filters.append(LeadSubmission.documents.is_(None))

        base = select(LeadSubmission).where(*filters)
        total = (await self.db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

        sort_columns = {
            "name": LeadSubmission.name,
            "email": LeadSubmission.email,
            "country": LeadSubmission.country,
        }
        order_by = sort_columns.get(sort_by, LeadSubmission.created_at.desc())

        result = await self.db.execute(
            base.order_by(order_by)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [_serialize_quote(row) for row in result.scalars().all()]
        return items, total

    async def get_stats(self) -> dict:
        """Return quote counts grouped by status, plus conversion rate."""
        rows = (
            await self.db.execute(
                select(LeadSubmission.status, func.count(LeadSubmission.id))
                .where(*self._quote_filters())
                .group_by(LeadSubmission.status)
            )
        ).all()

        counts = {status: count for status, count in rows}
        new = counts.get(QuoteStatus.NEW.value, 0)
        contacted = counts.get(QuoteStatus.CONTACTED.value, 0)
        qualified = counts.get(QuoteStatus.QUALIFIED.value, 0)
        converted = counts.get(QuoteStatus.CONVERTED.value, 0)
        total = sum(counts.values())

        return {
            "total": total,
            "new": new,
            "contacted": contacted,
            "qualified": qualified,
            "converted": converted,
            "new_count": new,
            "conversion_rate": round(converted / total * 100, 1) if total else 0.0,
        }

    async def _get_quote(self, quote_id: UUID) -> Optional[LeadSubmission]:
        result = await self.db.execute(
            select(LeadSubmission).where(
                LeadSubmission.id == quote_id,
                *self._quote_filters(),
            )
        )
        return result.scalar_one_or_none()

    async def get_quote(self, quote_id: UUID) -> Optional[dict]:
        """Get quote detail including attached documents."""
        lead = await self._get_quote(quote_id)
        return _serialize_quote(lead) if lead else None

    async def update_status(
        self,
        quote_id: UUID,
        data: QuoteStatusUpdate,
        updated_by: UUID,
    ) -> dict:
        """Move a quote along the funnel (new → contacted → qualified → converted)."""
        lead = await self._get_quote(quote_id)
        if not lead:
            raise ValueError("Quote submission not found")

        lead.status = data.status.value
        if data.notes is not None:
            lead.notes = data.notes
        # A quote that reaches a real funnel stage belongs to whoever moved it.
        if data.status != QuoteStatus.NEW and lead.assigned_to is None:
            lead.assigned_to = updated_by
        lead.updated_by = updated_by
        lead.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(lead)
        logger.info("quote_status_updated", quote_id=str(quote_id), status=data.status.value)
        return _serialize_quote(lead)

    async def assign(self, quote_id: UUID, assigned_to: UUID, updated_by: UUID) -> dict:
        """Assign a quote to a team member."""
        lead = await self._get_quote(quote_id)
        if not lead:
            raise ValueError("Quote submission not found")

        lead.assigned_to = assigned_to
        lead.updated_by = updated_by
        lead.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(lead)
        logger.info("quote_assigned", quote_id=str(quote_id), assigned_to=str(assigned_to))
        return _serialize_quote(lead)

    async def delete(self, quote_id: UUID, deleted_by: UUID) -> bool:
        """Soft-delete a quote submission."""
        lead = await self._get_quote(quote_id)
        if not lead:
            return False

        lead.soft_delete(deleted_by)
        await self.db.commit()
        logger.info("quote_deleted", quote_id=str(quote_id))
        return True
