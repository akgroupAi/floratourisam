"""Unified audit trail built from the AuditMixin columns every table already carries.

`AuditMixin` stamps created_by / updated_by / deleted_by and their timestamps on every
row, but nothing queried them across entities. This service turns those columns into a
single chronological feed.

What this can and cannot tell you:
  - CAN: who created, last updated, or deleted a record, and when.
  - CANNOT: field-level before/after values, or the full history of repeated edits —
    `updated_by` only holds the *most recent* editor. Real diffs would need a dedicated
    audit table populated by a SQLAlchemy event listener.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import String, cast, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.apartment import Apartment
from app.models.booking import Booking
from app.models.consultation import Consultation
from app.models.doctor import Doctor
from app.models.hospital import Department, Hospital
from app.models.hotel import Hotel
from app.models.package import MedicalPackage
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.restaurant import Restaurant
from app.models.site import LeadSubmission, Treatment
from app.models.user import User
from app.schemas.common import PaginationParams

logger = get_logger(__name__)

# Entity types the feed covers, with the column used as a human-readable label.
AUDITED_ENTITIES = {
    "hospital": (Hospital, Hospital.name),
    "department": (Department, Department.name),
    "doctor": (Doctor, None),
    "patient": (Patient, None),
    "hotel": (Hotel, Hotel.name),
    "apartment": (Apartment, Apartment.name),
    "restaurant": (Restaurant, Restaurant.name),
    "package": (MedicalPackage, MedicalPackage.name),
    "treatment": (Treatment, Treatment.name),
    "booking": (Booking, Booking.reference_number),
    "payment": (Payment, Payment.reference_number),
    "consultation": (Consultation, Consultation.reference_number),
    "lead": (LeadSubmission, LeadSubmission.email),
    "user": (User, User.full_name),
}


class AuditService:
    """Chronological feed of who changed what, across every audited entity."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def entity_types() -> List[str]:
        return sorted(AUDITED_ENTITIES)

    def _events_for(self, entity_type: str, model, label_column):
        """Three SELECTs per entity — created, updated, deleted — as a UNION ALL.

        `updated_at` equal to `created_at` is not a real edit, so those are excluded to
        stop every insert producing a duplicate 'updated' row.
        """
        label = (
            cast(label_column, String) if label_column is not None else literal(None, String)
        )

        created = select(
            literal(entity_type).label("entity_type"),
            cast(model.id, String).label("entity_id"),
            label.label("entity_label"),
            literal("created").label("action"),
            model.created_by.label("actor_id"),
            model.created_at.label("occurred_at"),
        ).where(model.created_by.isnot(None))

        updated = select(
            literal(entity_type),
            cast(model.id, String),
            label,
            literal("updated"),
            model.updated_by,
            model.updated_at,
        ).where(
            model.updated_by.isnot(None),
            model.updated_at.isnot(None),
            or_(model.created_at.is_(None), model.updated_at > model.created_at),
        )

        deleted = select(
            literal(entity_type),
            cast(model.id, String),
            label,
            literal("deleted"),
            model.deleted_by,
            model.deleted_at,
        ).where(model.deleted_by.isnot(None), model.deleted_at.isnot(None))

        return [created, updated, deleted]

    def _feed_query(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        actor_id: Optional[UUID] = None,
        action: Optional[str] = None,
        from_date=None,
        to_date=None,
    ):
        wanted = (
            {entity_type: AUDITED_ENTITIES[entity_type]}
            if entity_type and entity_type in AUDITED_ENTITIES
            else AUDITED_ENTITIES
        )

        selects = []
        for name, (model, label_column) in wanted.items():
            for stmt in self._events_for(name, model, label_column):
                if entity_id is not None:
                    stmt = stmt.where(model.id == entity_id)
                selects.append(stmt)

        if not selects:
            return None

        feed = union_all(*selects).subquery("audit_feed")

        conditions = []
        if actor_id is not None:
            conditions.append(feed.c.actor_id == actor_id)
        if action:
            conditions.append(feed.c.action == action)
        if from_date:
            conditions.append(
                feed.c.occurred_at
                >= datetime(from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc)
            )
        if to_date:
            conditions.append(
                feed.c.occurred_at
                < datetime(to_date.year, to_date.month, to_date.day, tzinfo=timezone.utc)
                + timedelta(days=1)
            )
        return feed, conditions

    async def get_feed(
        self,
        pagination: PaginationParams,
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        actor_id: Optional[UUID] = None,
        action: Optional[str] = None,
        from_date=None,
        to_date=None,
    ) -> Tuple[List[dict], int]:
        """Newest-first feed of create/update/delete events, with the actor resolved."""
        built = self._feed_query(
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            action=action,
            from_date=from_date,
            to_date=to_date,
        )
        if built is None:
            return [], 0
        feed, conditions = built

        total = (
            await self.db.execute(
                select(func.count()).select_from(feed).where(*conditions)
            )
        ).scalar() or 0

        rows = (
            await self.db.execute(
                select(
                    feed.c.entity_type,
                    feed.c.entity_id,
                    feed.c.entity_label,
                    feed.c.action,
                    feed.c.actor_id,
                    feed.c.occurred_at,
                    User.full_name,
                    User.email,
                    User.role,
                )
                .select_from(feed)
                .outerjoin(User, feed.c.actor_id == User.id)
                .where(*conditions)
                .order_by(feed.c.occurred_at.desc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        ).all()

        return [
            {
                "entity_type": e_type,
                "entity_id": e_id,
                "entity_label": e_label,
                "action": act,
                "actor_id": act_id,
                "actor_name": name,
                "actor_email": email,
                "actor_role": role,
                "occurred_at": occurred,
            }
            for e_type, e_id, e_label, act, act_id, occurred, name, email, role in rows
        ], total

    async def get_entity_history(
        self, entity_type: str, entity_id: UUID, pagination: PaginationParams
    ) -> Tuple[List[dict], int]:
        """Everything recorded for one record, newest first."""
        if entity_type not in AUDITED_ENTITIES:
            raise ValueError(
                f"Unknown entity type '{entity_type}'. Known: {', '.join(self.entity_types())}"
            )
        return await self.get_feed(pagination, entity_type=entity_type, entity_id=entity_id)

    async def get_actor_summary(self, actor_id: UUID, days: int = 30) -> dict:
        """What one user changed recently, counted by entity type and action."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        built = self._feed_query(actor_id=actor_id)
        if built is None:
            return {"actor_id": str(actor_id), "days": days, "total_actions": 0}
        feed, conditions = built
        conditions = conditions + [feed.c.occurred_at >= since]

        rows = (
            await self.db.execute(
                select(feed.c.entity_type, feed.c.action, func.count())
                .select_from(feed)
                .where(*conditions)
                .group_by(feed.c.entity_type, feed.c.action)
            )
        ).all()

        by_entity: dict[str, dict[str, int]] = {}
        by_action: dict[str, int] = {}
        total = 0
        for entity_type, action, count in rows:
            by_entity.setdefault(entity_type, {})[action] = count
            by_action[action] = by_action.get(action, 0) + count
            total += count

        return {
            "actor_id": str(actor_id),
            "days": days,
            "total_actions": total,
            "by_entity_type": by_entity,
            "by_action": by_action,
        }
