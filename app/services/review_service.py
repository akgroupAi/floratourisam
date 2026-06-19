"""Reviews & Ratings service.

Responsibilities:
  1. Verify the patient has actually used the entity before allowing a review
     (doctor → completed consultation, others → completed booking)
  2. Persist the review and mark is_verified accordingly
  3. Recalculate the entity's aggregate `rating` + `total_reviews` after any write
  4. Enforce the one-review-per-patient-per-entity rule with a friendly error
  5. Admin moderation: approve, reject, respond
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import Numeric as sa_numeric
from sqlalchemy import and_, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.apartment import Apartment
from app.models.booking import Booking
from app.models.consultation import Consultation
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.hotel import Hotel
from app.models.patient import Patient
from app.models.restaurant import Restaurant
from app.models.review import Review
from app.models.user import User
from app.schemas.review import AdminReviewApprove, ReviewCreate, ReviewUpdate
from app.utils.enums import BookingStatus, ConsultationStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ENTITY_MODELS = {
    "doctor": Doctor,
    "hospital": Hospital,
    "hotel": Hotel,
    "apartment": Apartment,
    "restaurant": Restaurant,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ReviewService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    async def _get_patient(self, user_id: UUID) -> Optional[Patient]:
        result = await self.db.execute(
            select(Patient).where(Patient.user_id == user_id, Patient.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def _entity_exists(self, entity_type: str, entity_id: UUID) -> bool:
        model = _ENTITY_MODELS.get(entity_type)
        if not model:
            return False
        result = await self.db.execute(
            select(model.id).where(model.id == entity_id, model.is_deleted == False)
        )
        return result.scalar_one_or_none() is not None

    async def _verify_usage(
        self,
        patient_id: UUID,
        entity_type: str,
        entity_id: UUID,
        booking_id: Optional[UUID],
        consultation_id: Optional[UUID],
    ) -> Tuple[bool, Optional[UUID], Optional[UUID]]:
        """
        Returns (is_verified, resolved_booking_id, resolved_consultation_id).
        Checks whether the patient has a completed booking/consultation for the entity.
        """
        if entity_type == "doctor":
            q = select(Consultation.id).where(
                Consultation.patient_id == patient_id,
                Consultation.doctor_id == entity_id,
                Consultation.status == ConsultationStatus.COMPLETED.value,
                Consultation.is_deleted == False,
            )
            if consultation_id:
                q = q.where(Consultation.id == consultation_id)
            row = (await self.db.execute(q.limit(1))).scalar_one_or_none()
            return (row is not None, None, row)

        # hotel, apartment, restaurant — check bookings
        q = select(Booking.id).where(
            Booking.patient_id == patient_id,
            Booking.status == BookingStatus.COMPLETED.value,
            Booking.is_deleted == False,
        )
        if entity_type == "hotel":
            from app.models.hotel import Room
            # join through room → hotel
            q = (
                select(Booking.id)
                .join(Room, Booking.hotel_room_id == Room.id)
                .where(
                    Booking.patient_id == patient_id,
                    Booking.status == BookingStatus.COMPLETED.value,
                    Booking.is_deleted == False,
                    Room.hotel_id == entity_id,
                )
            )
        elif entity_type == "apartment":
            q = q.where(Booking.apartment_id == entity_id)
        elif entity_type == "restaurant":
            q = q.where(Booking.restaurant_id == entity_id)

        if booking_id:
            q = q.where(Booking.id == booking_id)
        row = (await self.db.execute(q.limit(1))).scalar_one_or_none()
        return (row is not None, row, None)

    async def _recalculate_entity_rating(self, entity_type: str, entity_id: UUID) -> None:
        """Recompute avg rating and review count; write back to the entity row."""
        agg = (
            await self.db.execute(
                select(
                    func.round(func.avg(Review.rating).cast(sa_numeric()), 2),
                    func.count(Review.id),
                ).where(
                    Review.entity_type == entity_type,
                    Review.entity_id == entity_id,
                    Review.is_approved == True,
                    Review.is_deleted == False,
                )
            )
        ).first()
        avg_rating, total = (agg[0] or 0.0), (agg[1] or 0)

        model = _ENTITY_MODELS.get(entity_type)
        if model and hasattr(model, "rating"):
            await self.db.execute(
                update(model)
                .where(model.id == entity_id)
                .values(rating=float(avg_rating), total_reviews=total)
            )

    async def _enrich(self, reviews: List[Review]) -> List[dict]:
        """Attach reviewer display name + avatar to each review dict."""
        if not reviews:
            return []
        patient_ids = list({r.patient_id for r in reviews})
        rows = (
            await self.db.execute(
                select(Patient.id, User.full_name, User.avatar_url)
                .join(User, Patient.user_id == User.id)
                .where(Patient.id.in_(patient_ids))
            )
        ).all()
        info = {pid: (name, avatar) for pid, name, avatar in rows}

        result = []
        for r in reviews:
            name, avatar = info.get(r.patient_id, (None, None))
            d = {c.key: getattr(r, c.key) for c in r.__table__.columns}
            d["reviewer_name"] = name
            d["reviewer_avatar"] = avatar
            result.append(d)
        return result

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    async def submit_review(
        self,
        user_id: UUID,
        data: ReviewCreate,
        created_by: UUID,
    ) -> Review:
        """
        Submit a new review. Raises ValueError on:
        - Unknown entity type
        - Entity not found
        - Patient profile not found
        - Duplicate review (already submitted)
        """
        if data.entity_type not in _ENTITY_MODELS:
            raise ValueError(f"Unknown entity_type '{data.entity_type}'")

        if not await self._entity_exists(data.entity_type, data.entity_id):
            raise ValueError(f"{data.entity_type.capitalize()} with id {data.entity_id} not found")

        patient = await self._get_patient(user_id)
        if not patient:
            raise ValueError("Patient profile not found. Please complete your profile first.")

        is_verified, booking_id, consultation_id = await self._verify_usage(
            patient_id=patient.id,
            entity_type=data.entity_type,
            entity_id=data.entity_id,
            booking_id=data.booking_id,
            consultation_id=data.consultation_id,
        )

        # Prefer supplied IDs if verification passed
        resolved_booking = data.booking_id or booking_id
        resolved_consultation = data.consultation_id or consultation_id

        review = Review(
            id=uuid.uuid4(),
            entity_type=data.entity_type,
            entity_id=data.entity_id,
            patient_id=patient.id,
            rating=data.rating,
            title=data.title,
            body=data.body,
            is_verified=is_verified,
            is_approved=False,  # always requires admin approval first
            booking_id=resolved_booking,
            consultation_id=resolved_consultation,
            created_by=created_by,
            updated_by=created_by,
        )

        self.db.add(review)
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise ValueError(
                f"You have already submitted a review for this {data.entity_type}. "
                "You can edit your existing review instead."
            )
        await self.db.refresh(review)
        return review

    async def get_review(self, review_id: UUID) -> Optional[Review]:
        result = await self.db.execute(
            select(Review).where(Review.id == review_id, Review.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def list_for_entity(
        self,
        entity_type: str,
        entity_id: UUID,
        page: int = 1,
        page_size: int = 20,
        verified_only: bool = False,
        min_rating: Optional[int] = None,
        sort_by: str = "created_at",  # created_at | rating | helpful_count
    ) -> Tuple[List[dict], int]:
        """Return approved, non-deleted reviews for a public entity page."""
        base = select(Review).where(
            Review.entity_type == entity_type,
            Review.entity_id == entity_id,
            Review.is_approved == True,
            Review.is_deleted == False,
        )
        if verified_only:
            base = base.where(Review.is_verified == True)
        if min_rating is not None:
            base = base.where(Review.rating >= min_rating)

        total = (await self.db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

        order_col = {
            "rating": Review.rating.desc(),
            "helpful_count": Review.helpful_count.desc(),
        }.get(sort_by, Review.created_at.desc())

        rows_q = base.order_by(Review.is_featured.desc(), order_col).offset((page - 1) * page_size).limit(page_size)
        reviews = list((await self.db.execute(rows_q)).scalars().all())

        # Average rating for the entity (all approved reviews, ignoring filters)
        avg_result = await self.db.execute(
            select(func.avg(Review.rating)).where(
                Review.entity_type == entity_type,
                Review.entity_id == entity_id,
                Review.is_approved == True,
                Review.is_deleted == False,
            )
        )
        average_rating = round(float(avg_result.scalar() or 0), 2)

        return await self._enrich(reviews), total, average_rating

    async def _attach_entity_names(self, reviews: List[dict]) -> List[dict]:
        """Attach the reviewed entity's display name to each enriched review dict."""
        if not reviews:
            return reviews

        # Group entity ids by type so we run one query per table.
        ids_by_type: dict[str, set] = {}
        for r in reviews:
            ids_by_type.setdefault(r["entity_type"], set()).add(r["entity_id"])

        names: dict[tuple, str] = {}
        for entity_type, ids in ids_by_type.items():
            if entity_type == "doctor":
                # Doctor display name comes from the linked user.
                rows = (
                    await self.db.execute(
                        select(Doctor.id, Doctor.title, User.full_name)
                        .join(User, Doctor.user_id == User.id)
                        .where(Doctor.id.in_(ids))
                    )
                ).all()
                for eid, title, full_name in rows:
                    label = f"{title} {full_name}".strip() if title else full_name
                    names[(entity_type, eid)] = label
                continue

            model = _ENTITY_MODELS.get(entity_type)
            if not model or not hasattr(model, "name"):
                continue
            rows = (
                await self.db.execute(
                    select(model.id, model.name).where(model.id.in_(ids))
                )
            ).all()
            for eid, name in rows:
                names[(entity_type, eid)] = name

        for r in reviews:
            r["entity_name"] = names.get((r["entity_type"], r["entity_id"]))
        return reviews

    async def list_all_admin(
        self,
        page: int = 1,
        page_size: int = 20,
        entity_type: Optional[str] = None,
        min_rating: Optional[int] = None,
        is_approved: Optional[bool] = None,
        is_verified: Optional[bool] = None,
        sort_by: str = "created_at",  # created_at | rating | helpful_count
    ) -> Tuple[List[dict], int, float]:
        """Return non-deleted reviews across all (or one) entity type(s) for admins.

        Powers a global admin "all reviews" feed for hotels, apartments,
        restaurants, doctors and hospitals. Each item carries the reviewed
        entity's name. By default every moderation status is included; pass
        ``is_approved`` to narrow to approved (True) or pending/rejected (False).
        """
        filters = [Review.is_deleted == False]
        if entity_type:
            filters.append(Review.entity_type == entity_type)
        if min_rating is not None:
            filters.append(Review.rating >= min_rating)
        if is_approved is not None:
            filters.append(Review.is_approved == is_approved)
        if is_verified is not None:
            filters.append(Review.is_verified == is_verified)

        base = select(Review).where(*filters)
        total = (await self.db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

        order_col = {
            "rating": Review.rating.desc(),
            "helpful_count": Review.helpful_count.desc(),
        }.get(sort_by, Review.created_at.desc())

        rows_q = (
            base.order_by(Review.is_featured.desc(), order_col)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        reviews = list((await self.db.execute(rows_q)).scalars().all())

        # Overall average across the same filter scope (ignoring pagination).
        average_rating = round(
            float((await self.db.execute(select(func.avg(Review.rating)).where(*filters))).scalar() or 0),
            2,
        )

        enriched = await self._enrich(reviews)
        enriched = await self._attach_entity_names(enriched)
        return enriched, total, average_rating

    async def get_entity_summary(self, entity_type: str, entity_id: UUID) -> dict:
        """Aggregate stats for the entity."""
        breakdown: dict = {i: 0 for i in range(1, 6)}
        rows = (
            await self.db.execute(
                select(Review.rating, func.count(Review.id))
                .where(
                    Review.entity_type == entity_type,
                    Review.entity_id == entity_id,
                    Review.is_approved == True,
                    Review.is_deleted == False,
                )
                .group_by(Review.rating)
            )
        ).all()
        total = 0
        total_rating = 0.0
        for rating_val, count in rows:
            breakdown[rating_val] = count
            total += count
            total_rating += rating_val * count

        avg = round(total_rating / total, 2) if total else 0.0

        verified = (
            await self.db.execute(
                select(func.count()).where(
                    Review.entity_type == entity_type,
                    Review.entity_id == entity_id,
                    Review.is_approved == True,
                    Review.is_verified == True,
                    Review.is_deleted == False,
                )
            )
        ).scalar() or 0

        has_response = (
            await self.db.execute(
                select(func.count()).where(
                    Review.entity_type == entity_type,
                    Review.entity_id == entity_id,
                    Review.is_approved == True,
                    Review.response_text.isnot(None),
                    Review.is_deleted == False,
                )
            )
        ).scalar() or 0

        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "average_rating": avg,
            "total_reviews": total,
            "rating_breakdown": breakdown,
            "verified_count": verified,
            "has_response_count": has_response,
        }

    async def list_mine(
        self,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[dict], int]:
        """List all reviews the patient has submitted."""
        patient = await self._get_patient(user_id)
        if not patient:
            return [], 0

        base = select(Review).where(Review.patient_id == patient.id, Review.is_deleted == False)
        total = (await self.db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
        rows = list(
            (await self.db.execute(base.order_by(Review.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
        )
        return await self._enrich(rows), total

    async def update_review(
        self,
        review_id: UUID,
        user_id: UUID,
        data: ReviewUpdate,
        updated_by: UUID,
    ) -> Review:
        """Patient updates their own review. Forbidden after admin approval."""
        patient = await self._get_patient(user_id)
        if not patient:
            raise ValueError("Patient profile not found")

        review = await self.get_review(review_id)
        if not review:
            raise ValueError("Review not found")
        if review.patient_id != patient.id:
            raise PermissionError("You can only edit your own reviews")
        if review.is_approved:
            raise ValueError(
                "This review has already been approved and published. "
                "Contact support to request changes."
            )

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(review, field, value)
        review.updated_by = updated_by
        review.updated_at = _utcnow()
        await self.db.commit()
        await self.db.refresh(review)
        return review

    async def delete_review(self, review_id: UUID, user_id: UUID, deleted_by: UUID) -> None:
        """Patient soft-deletes their own review. Recalculates entity rating."""
        patient = await self._get_patient(user_id)
        if not patient:
            raise ValueError("Patient profile not found")

        review = await self.get_review(review_id)
        if not review:
            raise ValueError("Review not found")
        if review.patient_id != patient.id:
            raise PermissionError("You can only delete your own reviews")

        review.soft_delete(deleted_by)
        await self.db.commit()
        if review.is_approved:
            await self._recalculate_entity_rating(review.entity_type, review.entity_id)
            await self.db.commit()

    async def mark_helpful(self, review_id: UUID, helpful: bool) -> Review:
        """Increment or decrement the helpful counter."""
        review = await self.get_review(review_id)
        if not review:
            raise ValueError("Review not found")
        if not review.is_approved:
            raise ValueError("Cannot mark a review as helpful before it is published")
        delta = 1 if helpful else -1
        review.helpful_count = max(0, review.helpful_count + delta)
        await self.db.commit()
        await self.db.refresh(review)
        return review

    # -----------------------------------------------------------------------
    # Admin operations
    # -----------------------------------------------------------------------

    async def admin_list(
        self,
        page: int = 1,
        page_size: int = 30,
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        is_approved: Optional[bool] = None,
        is_verified: Optional[bool] = None,
        min_rating: Optional[int] = None,
    ) -> Tuple[List[dict], int]:
        base = select(Review).where(Review.is_deleted == False)
        if entity_type:
            base = base.where(Review.entity_type == entity_type)
        if entity_id:
            base = base.where(Review.entity_id == entity_id)
        if is_approved is not None:
            base = base.where(Review.is_approved == is_approved)
        if is_verified is not None:
            base = base.where(Review.is_verified == is_verified)
        if min_rating is not None:
            base = base.where(Review.rating >= min_rating)

        total = (await self.db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
        rows = list(
            (await self.db.execute(base.order_by(Review.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
        )
        enriched = await self._enrich(rows)
        enriched = await self._attach_entity_names(enriched)
        return enriched, total

    async def admin_approve(
        self,
        review_id: UUID,
        data: AdminReviewApprove,
        admin_id: UUID,
    ) -> Review:
        review = await self.get_review(review_id)
        if not review:
            raise ValueError("Review not found")

        review.is_approved = data.approve
        review.rejection_reason = None if data.approve else data.rejection_reason
        review.updated_by = admin_id
        review.updated_at = _utcnow()
        await self.db.commit()

        # Recalculate the entity's aggregate rating
        await self._recalculate_entity_rating(review.entity_type, review.entity_id)
        await self.db.commit()
        await self.db.refresh(review)
        return review

    async def admin_respond(
        self,
        review_id: UUID,
        response_text: str,
        admin_id: UUID,
    ) -> Review:
        """Post an official response to a published review."""
        review = await self.get_review(review_id)
        if not review:
            raise ValueError("Review not found")
        if not review.is_approved:
            raise ValueError("Cannot respond to an unpublished review")

        review.response_text = response_text.strip()
        review.response_date = _utcnow()
        review.response_by = admin_id
        review.updated_by = admin_id
        review.updated_at = _utcnow()
        await self.db.commit()
        await self.db.refresh(review)
        return review

    async def admin_delete(self, review_id: UUID, admin_id: UUID) -> None:
        """Hard soft-delete by admin. Recalculates entity rating."""
        review = await self.get_review(review_id)
        if not review:
            raise ValueError("Review not found")
        was_approved = review.is_approved
        entity_type, entity_id = review.entity_type, review.entity_id

        review.soft_delete(admin_id)
        await self.db.commit()

        if was_approved:
            await self._recalculate_entity_rating(entity_type, entity_id)
            await self.db.commit()

    async def admin_feature(self, review_id: UUID, featured: bool, admin_id: UUID) -> Review:
        """Pin / unpin a review as featured."""
        review = await self.get_review(review_id)
        if not review:
            raise ValueError("Review not found")
        review.is_featured = featured
        review.updated_by = admin_id
        await self.db.commit()
        await self.db.refresh(review)
        return review
