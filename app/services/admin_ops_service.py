"""Admin operations: notification broadcasts, platform calendar, demand signals."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.apartment import Apartment
from app.models.doctor import Doctor
from app.models.favorite import PatientFavorite
from app.models.hospital import Hospital
from app.models.hotel import Hotel
from app.models.package import MedicalPackage
from app.models.patient import Patient
from app.models.restaurant import Restaurant
from app.models.system import Event, Notification
from app.models.treatment_proposal import TreatmentProposal
from app.models.user import User
from app.schemas.common import PaginationParams
from app.utils.notifications import notify

logger = get_logger(__name__)

# Favorite entity type → (model, display-name column). Mirrors FavoriteEntityType.
FAVORITE_SOURCES = {
    "doctor": (Doctor, None),
    "hospital": (Hospital, Hospital.name),
    "package": (MedicalPackage, MedicalPackage.name),
    "hotel": (Hotel, Hotel.name),
    "apartment": (Apartment, Apartment.name),
    "restaurant": (Restaurant, Restaurant.name),
}


class AdminOpsService:
    """Cross-cutting admin operations that do not warrant a service of their own."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Notifications ─────────────────────────────────────────

    async def broadcast(
        self,
        title: str,
        message: str,
        sent_by: UUID,
        roles: Optional[List[str]] = None,
        user_ids: Optional[List[UUID]] = None,
        notification_type: str = "system",
        action_url: Optional[str] = None,
        action_text: Optional[str] = None,
    ) -> dict:
        """Send a notification to explicit users, or to everyone holding given roles.

        Exactly one of `roles` or `user_ids` should be supplied. With neither, this
        deliberately refuses rather than messaging every user by accident.
        """
        if not roles and not user_ids:
            raise ValueError(
                "Specify roles or user_ids. Refusing to broadcast to every user implicitly."
            )

        filters = [User.is_deleted == False, User.is_active == True]
        if user_ids:
            filters.append(User.id.in_(user_ids))
        elif roles:
            filters.append(User.role.in_(roles))

        recipients = list(
            (await self.db.execute(select(User.id).where(*filters))).scalars().all()
        )

        # notify() flushes but does not commit, and re-raises on failure. Build them
        # all, then commit once — a broadcast either lands or it does not.
        for user_id in recipients:
            await notify(
                db=self.db,
                user_id=user_id,
                title=title,
                message=message,
                notification_type=notification_type,
                action_url=action_url,
                action_text=action_text,
                created_by=sent_by,
            )
        await self.db.commit()

        logger.info(
            "admin_broadcast_sent",
            sent_by=str(sent_by),
            recipients=len(recipients),
        )
        return {
            "recipients_targeted": len(recipients),
            "notifications_created": len(recipients),
        }

    async def list_notifications(
        self,
        pagination: PaginationParams,
        user_id: Optional[UUID] = None,
        notification_type: Optional[str] = None,
        is_read: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[dict], int]:
        """Notifications across all users."""
        filters = [Notification.is_deleted == False]
        if user_id:
            filters.append(Notification.user_id == user_id)
        if notification_type:
            filters.append(Notification.notification_type == notification_type)
        if is_read is not None:
            filters.append(Notification.is_read == is_read)
        if search:
            like = f"%{search}%"
            filters.append(
                or_(Notification.title.ilike(like), Notification.message.ilike(like))
            )

        total = (
            await self.db.execute(
                select(func.count()).select_from(
                    select(Notification.id).where(*filters).subquery()
                )
            )
        ).scalar() or 0

        rows = (
            await self.db.execute(
                select(Notification, User.full_name, User.email)
                .outerjoin(User, Notification.user_id == User.id)
                .where(*filters)
                .order_by(Notification.created_at.desc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        ).all()

        return [
            {
                "id": n.id,
                "user_id": n.user_id,
                "user_name": name,
                "user_email": email,
                "title": n.title,
                "message": n.message,
                "notification_type": n.notification_type,
                "entity_type": n.entity_type,
                "entity_id": n.entity_id,
                "action_url": n.action_url,
                "is_read": n.is_read,
                "read_at": n.read_at,
                "sent_push": n.sent_push,
                "sent_email": n.sent_email,
                "created_at": n.created_at,
            }
            for n, name, email in rows
        ], total

    async def notification_stats(self) -> dict:
        """Volume and read-through rate."""
        base = [Notification.is_deleted == False]
        total = (
            await self.db.execute(select(func.count(Notification.id)).where(*base))
        ).scalar() or 0
        read = (
            await self.db.execute(
                select(func.count(Notification.id)).where(*base, Notification.is_read == True)
            )
        ).scalar() or 0
        by_type = dict(
            (
                await self.db.execute(
                    select(Notification.notification_type, func.count(Notification.id))
                    .where(*base)
                    .group_by(Notification.notification_type)
                )
            ).all()
        )
        last_24h = (
            await self.db.execute(
                select(func.count(Notification.id)).where(
                    *base,
                    Notification.created_at >= datetime.now(timezone.utc) - timedelta(days=1),
                )
            )
        ).scalar() or 0

        return {
            "total": total,
            "read": read,
            "unread": total - read,
            "read_rate": round(read / total * 100, 2) if total else 0.0,
            "sent_last_24h": last_24h,
            "by_type": by_type,
        }

    # ── Platform calendar ─────────────────────────────────────

    async def list_events(
        self,
        pagination: PaginationParams,
        user_id: Optional[UUID] = None,
        event_type: Optional[str] = None,
        status: Optional[str] = None,
        upcoming_only: bool = False,
        from_date=None,
        to_date=None,
    ) -> Tuple[List[dict], int]:
        """Every user's events — the platform-wide calendar."""
        filters = [Event.is_deleted == False]
        if user_id:
            filters.append(Event.user_id == user_id)
        if event_type:
            filters.append(Event.event_type == event_type)
        if status:
            filters.append(Event.status == status)
        if upcoming_only:
            filters.append(Event.start_time >= datetime.now(timezone.utc))
        if from_date:
            filters.append(
                Event.start_time
                >= datetime(from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc)
            )
        if to_date:
            filters.append(
                Event.start_time
                < datetime(to_date.year, to_date.month, to_date.day, tzinfo=timezone.utc)
                + timedelta(days=1)
            )

        total = (
            await self.db.execute(
                select(func.count()).select_from(select(Event.id).where(*filters).subquery())
            )
        ).scalar() or 0

        rows = (
            await self.db.execute(
                select(Event, User.full_name, User.email)
                .outerjoin(User, Event.user_id == User.id)
                .where(*filters)
                .order_by(Event.start_time.asc() if upcoming_only else Event.start_time.desc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        ).all()

        return [
            {
                "id": e.id,
                "user_id": e.user_id,
                "user_name": name,
                "user_email": email,
                "title": e.title,
                "description": e.description,
                "event_type": e.event_type,
                "start_time": e.start_time,
                "end_time": e.end_time,
                "all_day": e.all_day,
                "location": e.location,
                "location_type": e.location_type,
                "meeting_url": e.meeting_url,
                "status": e.status,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "created_at": e.created_at,
            }
            for e, name, email in rows
        ], total

    # ── Demand signals ────────────────────────────────────────

    async def favorite_stats(self, limit: int = 10) -> dict:
        """What patients are saving — a demand signal for catalogue decisions."""
        by_type = dict(
            (
                await self.db.execute(
                    select(PatientFavorite.entity_type, func.count(PatientFavorite.id))
                    .group_by(PatientFavorite.entity_type)
                )
            ).all()
        )
        total = sum(by_type.values())
        patients_with_favorites = (
            await self.db.execute(
                select(func.count(func.distinct(PatientFavorite.patient_id)))
            )
        ).scalar() or 0

        top: dict[str, list] = {}
        for entity_type, (model, name_column) in FAVORITE_SOURCES.items():
            counts = (
                await self.db.execute(
                    select(PatientFavorite.entity_id, func.count(PatientFavorite.id).label("c"))
                    .where(PatientFavorite.entity_type == entity_type)
                    .group_by(PatientFavorite.entity_id)
                    .order_by(func.count(PatientFavorite.id).desc())
                    .limit(limit)
                )
            ).all()
            if not counts:
                continue

            ids = [row[0] for row in counts]
            names: dict = {}
            if name_column is not None:
                names = dict(
                    (
                        await self.db.execute(
                            select(model.id, name_column).where(model.id.in_(ids))
                        )
                    ).all()
                )
            else:
                # Doctors get their name from the linked user row.
                names = dict(
                    (
                        await self.db.execute(
                            select(Doctor.id, User.full_name)
                            .join(User, Doctor.user_id == User.id)
                            .where(Doctor.id.in_(ids))
                        )
                    ).all()
                )

            top[entity_type] = [
                {
                    "entity_id": str(entity_id),
                    "name": names.get(entity_id),
                    "saved_count": count,
                }
                for entity_id, count in counts
            ]

        return {
            "total_favorites": total,
            "patients_with_favorites": patients_with_favorites,
            "by_entity_type": by_type,
            "most_saved": top,
        }

    async def proposal_stats(self) -> dict:
        """Treatment proposal funnel — created, approved, accepted, and their value."""
        base = [TreatmentProposal.is_deleted == False]

        by_status = dict(
            (
                await self.db.execute(
                    select(TreatmentProposal.status, func.count(TreatmentProposal.id))
                    .where(*base)
                    .group_by(TreatmentProposal.status)
                )
            ).all()
        )
        total = sum(by_status.values())

        pending_admin = (
            await self.db.execute(
                select(func.count(TreatmentProposal.id)).where(
                    *base, TreatmentProposal.admin_approved.is_(None)
                )
            )
        ).scalar() or 0
        admin_approved = (
            await self.db.execute(
                select(func.count(TreatmentProposal.id)).where(
                    *base, TreatmentProposal.admin_approved == True
                )
            )
        ).scalar() or 0

        total_value = float(
            (
                await self.db.execute(
                    select(func.sum(TreatmentProposal.total_amount)).where(*base)
                )
            ).scalar()
            or 0
        )
        average_value = float(
            (
                await self.db.execute(
                    select(func.avg(TreatmentProposal.total_amount)).where(*base)
                )
            ).scalar()
            or 0
        )
        accepted = by_status.get("accepted", 0)
        accepted_value = float(
            (
                await self.db.execute(
                    select(func.sum(TreatmentProposal.total_amount)).where(
                        *base, TreatmentProposal.status == "accepted"
                    )
                )
            ).scalar()
            or 0
        )

        return {
            "total": total,
            "by_status": by_status,
            "pending_admin_review": pending_admin,
            "admin_approved": admin_approved,
            "accepted": accepted,
            "acceptance_rate": round(accepted / total * 100, 2) if total else 0.0,
            "total_proposed_value": round(total_value, 2),
            "accepted_value": round(accepted_value, 2),
            "average_proposal_value": round(average_value, 2),
        }
