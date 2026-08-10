"""Treatment Proposal service."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.patient import Patient
from app.models.treatment_proposal import TreatmentProposal
from app.models.user import User
from app.schemas.treatment_proposal import (
    TreatmentProposalCreate,
    TreatmentProposalUpdate,
)
from app.utils.helpers import generate_reference_id
from app.utils.notifications import notify

logger = get_logger(__name__)


class TreatmentProposalService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Create proposal (doctor → patient)
    # ------------------------------------------------------------------

    async def create_proposal(
        self,
        doctor_user_id: UUID,
        data: TreatmentProposalCreate,
        created_by: UUID,
    ) -> TreatmentProposal:
        """Doctor creates a treatment proposal for a patient."""

        # Verify the user is a doctor and get doctor profile
        doctor_result = await self.db.execute(
            select(Doctor).where(
                Doctor.user_id == doctor_user_id,
                Doctor.is_deleted == False,
            )
        )
        doctor = doctor_result.scalar_one_or_none()
        if not doctor:
            raise ValueError("Doctor profile not found")

        # Verify patient exists
        patient_result = await self.db.execute(
            select(Patient).where(
                Patient.id == data.patient_id,
                Patient.is_deleted == False,
            )
        )
        if not patient_result.scalar_one_or_none():
            raise ValueError("Patient not found")

        # Calculate total
        total = (
            data.consultation_fee
            + data.surgery_fee
            + data.hospital_stay_fee
            + data.medications_fee
            + data.other_fees
        )

        # Use doctor's hospital if not specified
        hospital_id = data.hospital_id or doctor.hospital_id

        proposal = TreatmentProposal(
            consultation_id=data.consultation_id,
            doctor_id=doctor.id,
            patient_id=data.patient_id,
            hospital_id=hospital_id,
            treatment_name=data.treatment_name,
            description=data.description,
            estimated_duration=data.estimated_duration,
            proposed_visit_date=data.proposed_visit_date,
            proposed_visit_time=data.proposed_visit_time,
            currency=data.currency,
            consultation_fee=data.consultation_fee,
            surgery_fee=data.surgery_fee,
            hospital_stay_fee=data.hospital_stay_fee,
            medications_fee=data.medications_fee,
            other_fees=data.other_fees,
            other_fees_description=data.other_fees_description,
            total_amount=total,
            doctor_notes=data.doctor_notes,
            status="pending",
            reference_number=generate_reference_id("TRP"),
            created_by=created_by,
        )
        self.db.add(proposal)
        await self.db.commit()
        await self.db.refresh(proposal)

        logger.info(
            "treatment_proposal_created",
            proposal_id=str(proposal.id),
            ref=proposal.reference_number,
        )

        # Notify patient about new proposal
        try:
            patient_result = await self.db.execute(
                select(Patient).where(Patient.id == data.patient_id)
            )
            patient_rec = patient_result.scalar_one_or_none()
            if patient_rec:
                p_user_result = await self.db.execute(
                    select(User).where(User.id == patient_rec.user_id)
                )
                p_user = p_user_result.scalar_one_or_none()
                if p_user:
                    # Get doctor display name
                    d_user_result = await self.db.execute(
                        select(User).where(User.id == doctor.user_id)
                    )
                    d_user = d_user_result.scalar_one_or_none()
                    doctor_display = f"{doctor.title or 'Dr.'} {d_user.full_name if d_user else 'your doctor'}".strip()
                    await notify(
                        db=self.db,
                        user_id=p_user.id,
                        title="New Treatment Proposal",
                        message=f"{doctor_display} has sent you a treatment proposal: {data.treatment_name}. Ref: {proposal.reference_number}",
                        notification_type="treatment_proposal",
                        entity_type="treatment_proposal",
                        entity_id=proposal.id,
                        action_url=f"/treatment-proposals/{proposal.id}",
                        created_by=created_by,
                    )
        except Exception as exc:
            logger.error("proposal_create_notification_failed", error=str(exc))

        # Re-fetch with eager loading for response serialization
        return await self._get_proposal(proposal.id)

    async def update_proposal(
        self,
        proposal_id: UUID,
        doctor_user_id: UUID,
        data: TreatmentProposalUpdate,
    ) -> TreatmentProposal:
        """Doctor updates a pending proposal."""
        proposal = await self._get_proposal(proposal_id)
        if not proposal:
            raise ValueError("Proposal not found")

        # Verify ownership
        doctor_result = await self.db.execute(
            select(Doctor).where(
                Doctor.id == proposal.doctor_id,
                Doctor.is_deleted == False,
            )
        )
        doctor = doctor_result.scalar_one_or_none()
        if not doctor or doctor.user_id != doctor_user_id:
            raise ValueError("Only the proposing doctor can update this proposal")

        if proposal.status not in ("pending", "revision_requested"):
            raise ValueError(f"Cannot update a {proposal.status} proposal")

        for field, value in data.model_dump(exclude_none=True).items():
            setattr(proposal, field, value)

        # Recalculate total
        proposal.total_amount = (
            proposal.consultation_fee
            + proposal.surgery_fee
            + proposal.hospital_stay_fee
            + proposal.medications_fee
            + proposal.other_fees
        )
        proposal.updated_by = doctor_user_id

        # If it was revision_requested, reset to pending on update
        if proposal.status == "revision_requested":
            proposal.status = "pending"

        await self.db.commit()
        await self.db.refresh(proposal)
        logger.info("treatment_proposal_updated", proposal_id=str(proposal_id))

        # Notify patient about updated proposal
        try:
            patient_result = await self.db.execute(
                select(Patient).where(Patient.id == proposal.patient_id)
            )
            patient_rec = patient_result.scalar_one_or_none()
            if patient_rec:
                p_user_result = await self.db.execute(
                    select(User).where(User.id == patient_rec.user_id)
                )
                p_user = p_user_result.scalar_one_or_none()
                if p_user:
                    await notify(
                        db=self.db,
                        user_id=p_user.id,
                        title="Treatment Proposal Updated",
                        message=f"Your treatment proposal {proposal.reference_number} has been updated. Please review the changes.",
                        notification_type="treatment_proposal",
                        entity_type="treatment_proposal",
                        entity_id=proposal.id,
                        action_url=f"/treatment-proposals/{proposal.id}",
                        created_by=doctor_user_id,
                    )
        except Exception as exc:
            logger.error("proposal_update_notification_failed", error=str(exc))

        # Re-fetch with eager loading for response serialization
        return await self._get_proposal(proposal.id)

    async def patient_respond(
        self,
        proposal_id: UUID,
        patient_user_id: UUID,
        action: str,
        notes: Optional[str] = None,
    ) -> TreatmentProposal:
        """Patient approves, rejects, or requests revision of a proposal."""
        proposal = await self._get_proposal(proposal_id)
        if not proposal:
            raise ValueError("Proposal not found")

        # Verify the patient owns this proposal
        patient_result = await self.db.execute(
            select(Patient).where(
                Patient.id == proposal.patient_id,
                Patient.is_deleted == False,
            )
        )
        patient = patient_result.scalar_one_or_none()
        if not patient or patient.user_id != patient_user_id:
            raise ValueError("You can only respond to your own proposals")

        if proposal.status not in ("pending",):
            raise ValueError(f"Cannot respond to a {proposal.status} proposal")

        action_map = {
            "approve": "approved",
            "reject": "rejected",
            "request_revision": "revision_requested",
        }
        new_status = action_map.get(action)
        if not new_status:
            raise ValueError("Invalid action. Use: approve, reject, or request_revision")

        proposal.status = new_status
        proposal.patient_response_notes = notes
        proposal.responded_at = datetime.now(timezone.utc)
        proposal.updated_by = patient_user_id

        await self.db.commit()
        await self.db.refresh(proposal)
        logger.info(
            "treatment_proposal_responded",
            proposal_id=str(proposal_id),
            action=action,
        )

        # Notify doctor about patient's response
        try:
            doctor_result = await self.db.execute(
                select(Doctor).where(Doctor.id == proposal.doctor_id)
            )
            doctor_rec = doctor_result.scalar_one_or_none()
            if doctor_rec:
                d_user_result = await self.db.execute(
                    select(User).where(User.id == doctor_rec.user_id)
                )
                d_user = d_user_result.scalar_one_or_none()
                if d_user:
                    action_label = {"approve": "approved", "reject": "rejected", "request_revision": "requested a revision for"}.get(action, action)
                    # Get patient name
                    p_user_result = await self.db.execute(
                        select(User).where(User.id == patient.user_id)
                    )
                    p_user = p_user_result.scalar_one_or_none()
                    patient_name = p_user.full_name if p_user else "A patient"
                    await notify(
                        db=self.db,
                        user_id=d_user.id,
                        title="Treatment Proposal Response",
                        message=f"{patient_name} has {action_label} your treatment proposal {proposal.reference_number}.",
                        notification_type="treatment_proposal",
                        entity_type="treatment_proposal",
                        entity_id=proposal.id,
                        action_url=f"/treatment-proposals/{proposal.id}",
                        created_by=patient_user_id,
                    )
        except Exception as exc:
            logger.error("proposal_respond_notification_failed", error=str(exc))

        # Re-fetch with eager loading for response serialization
        return await self._get_proposal(proposal.id)

    async def admin_review(
        self,
        proposal_id: UUID,
        admin_user_id: UUID,
        approved: bool,
        notes: Optional[str] = None,
    ) -> TreatmentProposal:
        """Admin approves or rejects a proposal."""
        proposal = await self._get_proposal(proposal_id)
        if not proposal:
            raise ValueError("Proposal not found")

        proposal.admin_approved = approved
        proposal.admin_notes = notes
        proposal.admin_reviewed_at = datetime.now(timezone.utc)
        proposal.admin_reviewed_by = admin_user_id
        proposal.updated_by = admin_user_id

        await self.db.commit()
        logger.info(
            "treatment_proposal_admin_reviewed",
            proposal_id=str(proposal_id),
            approved=approved,
        )
        # Re-fetch with eager loading for response serialization
        return await self._get_proposal(proposal.id)

    # ------------------------------------------------------------------
    # Get single proposal
    # ------------------------------------------------------------------

    async def get_proposal(self, proposal_id: UUID) -> Optional[TreatmentProposal]:
        """Get a proposal by ID with related data."""
        return await self._get_proposal(proposal_id)

    # ------------------------------------------------------------------
    # List proposals for patient
    # ------------------------------------------------------------------

    async def list_patient_proposals(
        self,
        patient_user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> tuple[List[TreatmentProposal], int]:
        """List proposals received by a patient."""
        patient_result = await self.db.execute(
            select(Patient).where(
                Patient.user_id == patient_user_id,
                Patient.is_deleted == False,
            )
        )
        patient = patient_result.scalar_one_or_none()
        if not patient:
            return [], 0

        query = select(TreatmentProposal).options(
            selectinload(TreatmentProposal.doctor).selectinload(Doctor.user),
            selectinload(TreatmentProposal.patient).selectinload(Patient.user),
            selectinload(TreatmentProposal.hospital),
        ).where(
            TreatmentProposal.patient_id == patient.id,
            TreatmentProposal.is_deleted == False,
        )
        if status:
            query = query.where(TreatmentProposal.status == status)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = (
            query.order_by(TreatmentProposal.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = await self.db.execute(query)
        return list(rows.scalars().all()), total

    # ------------------------------------------------------------------
    # List proposals sent by doctor
    # ------------------------------------------------------------------

    async def list_doctor_proposals(
        self,
        doctor_user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> tuple[List[TreatmentProposal], int]:
        """List proposals sent by a doctor."""
        doctor_result = await self.db.execute(
            select(Doctor).where(
                Doctor.user_id == doctor_user_id,
                Doctor.is_deleted == False,
            )
        )
        doctor = doctor_result.scalar_one_or_none()
        if not doctor:
            return [], 0

        query = select(TreatmentProposal).options(
            selectinload(TreatmentProposal.doctor).selectinload(Doctor.user),
            selectinload(TreatmentProposal.patient).selectinload(Patient.user),
            selectinload(TreatmentProposal.hospital),
        ).where(
            TreatmentProposal.doctor_id == doctor.id,
            TreatmentProposal.is_deleted == False,
        )
        if status:
            query = query.where(TreatmentProposal.status == status)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = (
            query.order_by(TreatmentProposal.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = await self.db.execute(query)
        return list(rows.scalars().all()), total

    # ------------------------------------------------------------------
    # List all proposals (admin)
    # ------------------------------------------------------------------

    async def can_view_proposal(self, proposal: TreatmentProposal, user) -> bool:
        """Whether this user may read this proposal.

        Proposals carry a patient's diagnosis and full cost breakdown, so access is
        limited to the doctor who sent it, the patient who received it, and admins.
        """
        role = getattr(user, "role", None)
        if role in ("admin", "super_admin"):
            return True

        doctor = await self.db.execute(
            select(Doctor.id).where(Doctor.user_id == user.id)
        )
        if proposal.doctor_id in set(doctor.scalars().all()):
            return True

        patient = await self.db.execute(
            select(Patient.id).where(Patient.user_id == user.id)
        )
        return proposal.patient_id in set(patient.scalars().all())

    async def admin_list_proposals(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        doctor_id: Optional[UUID] = None,
        patient_id: Optional[UUID] = None,
        hospital_id: Optional[UUID] = None,
        admin_approved: Optional[bool] = None,
        pending_review_only: bool = False,
        search: Optional[str] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        from_date=None,
        to_date=None,
        sort_by: str = "created_at",
    ) -> tuple[List[TreatmentProposal], int]:
        """Admin: list proposals with the filters a review queue needs."""
        from datetime import timedelta

        from sqlalchemy import or_
        from app.models.user import User

        filters = [TreatmentProposal.is_deleted == False]
        if status:
            filters.append(TreatmentProposal.status == status)
        if doctor_id:
            filters.append(TreatmentProposal.doctor_id == doctor_id)
        if patient_id:
            filters.append(TreatmentProposal.patient_id == patient_id)
        if hospital_id:
            filters.append(TreatmentProposal.hospital_id == hospital_id)
        if pending_review_only:
            filters.append(TreatmentProposal.admin_approved.is_(None))
        elif admin_approved is not None:
            filters.append(TreatmentProposal.admin_approved == admin_approved)
        if min_amount is not None:
            filters.append(TreatmentProposal.total_amount >= min_amount)
        if max_amount is not None:
            filters.append(TreatmentProposal.total_amount <= max_amount)
        if from_date:
            filters.append(
                TreatmentProposal.created_at
                >= datetime(from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc)
            )
        if to_date:
            filters.append(
                TreatmentProposal.created_at
                < datetime(to_date.year, to_date.month, to_date.day, tzinfo=timezone.utc)
                + timedelta(days=1)
            )
        if search:
            like = f"%{search}%"
            doctor_ids = select(Doctor.id).join(User, Doctor.user_id == User.id).where(
                or_(User.full_name.ilike(like), User.email.ilike(like))
            )
            patient_ids = select(Patient.id).join(User, Patient.user_id == User.id).where(
                or_(User.full_name.ilike(like), User.email.ilike(like))
            )
            filters.append(
                or_(
                    TreatmentProposal.reference_number.ilike(like),
                    TreatmentProposal.treatment_name.ilike(like),
                    TreatmentProposal.doctor_id.in_(doctor_ids),
                    TreatmentProposal.patient_id.in_(patient_ids),
                )
            )

        base = select(TreatmentProposal).where(*filters)
        total = (
            await self.db.execute(select(func.count()).select_from(base.subquery()))
        ).scalar() or 0

        order = {
            "amount": TreatmentProposal.total_amount.desc(),
            "amount_asc": TreatmentProposal.total_amount.asc(),
            "visit_date": TreatmentProposal.proposed_visit_date.asc(),
        }.get(sort_by, TreatmentProposal.created_at.desc())

        rows = await self.db.execute(
            base.options(
                selectinload(TreatmentProposal.doctor).selectinload(Doctor.user),
                selectinload(TreatmentProposal.patient).selectinload(Patient.user),
                selectinload(TreatmentProposal.hospital),
            )
            .order_by(order)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(rows.scalars().all()), total

    async def admin_stats(self, top_doctors: int = 5) -> dict:
        """Proposal funnel, budget totals, and who is sending them."""
        from app.models.user import User

        base = [TreatmentProposal.is_deleted == False]

        by_status_rows = (
            await self.db.execute(
                select(
                    TreatmentProposal.status,
                    func.count(TreatmentProposal.id),
                    func.coalesce(func.sum(TreatmentProposal.total_amount), 0.0),
                )
                .where(*base)
                .group_by(TreatmentProposal.status)
            )
        ).all()
        by_status = {row[0]: row[1] for row in by_status_rows}
        value_by_status = {row[0]: float(row[2] or 0) for row in by_status_rows}

        pending_review = (
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
        admin_rejected = (
            await self.db.execute(
                select(func.count(TreatmentProposal.id)).where(
                    *base, TreatmentProposal.admin_approved == False
                )
            )
        ).scalar() or 0

        totals = (
            await self.db.execute(
                select(
                    func.coalesce(func.sum(TreatmentProposal.total_amount), 0.0),
                    func.coalesce(func.avg(TreatmentProposal.total_amount), 0.0),
                    func.coalesce(func.max(TreatmentProposal.total_amount), 0.0),
                ).where(*base)
            )
        ).one()
        total_value, average_value, largest_value = (float(v or 0) for v in totals)

        pending_value = float(
            (
                await self.db.execute(
                    select(func.coalesce(func.sum(TreatmentProposal.total_amount), 0.0)).where(
                        *base, TreatmentProposal.admin_approved.is_(None)
                    )
                )
            ).scalar()
            or 0
        )

        currencies = dict(
            (
                await self.db.execute(
                    select(
                        TreatmentProposal.currency,
                        func.coalesce(func.sum(TreatmentProposal.total_amount), 0.0),
                    )
                    .where(*base)
                    .group_by(TreatmentProposal.currency)
                )
            ).all()
        )

        sender_rows = (
            await self.db.execute(
                select(
                    TreatmentProposal.doctor_id,
                    User.full_name,
                    func.count(TreatmentProposal.id).label("sent"),
                    func.coalesce(func.sum(TreatmentProposal.total_amount), 0.0),
                )
                .join(Doctor, TreatmentProposal.doctor_id == Doctor.id)
                .join(User, Doctor.user_id == User.id)
                .where(*base)
                .group_by(TreatmentProposal.doctor_id, User.full_name)
                .order_by(func.count(TreatmentProposal.id).desc())
                .limit(top_doctors)
            )
        ).all()

        total = sum(by_status.values())
        accepted = by_status.get("accepted", 0)

        return {
            "total": total,
            "by_status": by_status,
            "value_by_status": {k: round(v, 2) for k, v in value_by_status.items()},
            "pending_admin_review": pending_review,
            "admin_approved": admin_approved,
            "admin_rejected": admin_rejected,
            "accepted": accepted,
            "acceptance_rate": round(accepted / total * 100, 2) if total else 0.0,
            "total_proposed_value": round(total_value, 2),
            "accepted_value": round(value_by_status.get("accepted", 0.0), 2),
            "pending_review_value": round(pending_value, 2),
            "average_proposal_value": round(average_value, 2),
            "largest_proposal_value": round(largest_value, 2),
            "value_by_currency": {k: round(float(v or 0), 2) for k, v in currencies.items()},
            "top_senders": [
                {
                    "doctor_id": str(doctor_id),
                    "doctor_name": name,
                    "proposals_sent": sent,
                    "total_value": round(float(value or 0), 2),
                }
                for doctor_id, name, sent, value in sender_rows
            ],
        }

    async def list_all_proposals(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> tuple[List[TreatmentProposal], int]:
        """Admin: list all proposals."""
        query = select(TreatmentProposal).options(
            selectinload(TreatmentProposal.doctor).selectinload(Doctor.user),
            selectinload(TreatmentProposal.patient).selectinload(Patient.user),
            selectinload(TreatmentProposal.hospital),
        ).where(
            TreatmentProposal.is_deleted == False,
        )
        if status:
            query = query.where(TreatmentProposal.status == status)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = (
            query.order_by(TreatmentProposal.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = await self.db.execute(query)
        return list(rows.scalars().all()), total

    # ------------------------------------------------------------------
    # List proposals for a consultation
    # ------------------------------------------------------------------

    async def list_consultation_proposals(
        self, consultation_id: UUID
    ) -> List[TreatmentProposal]:
        """Get all proposals linked to a specific consultation."""
        result = await self.db.execute(
            select(TreatmentProposal)
            .options(
                selectinload(TreatmentProposal.doctor).selectinload(Doctor.user),
                selectinload(TreatmentProposal.patient).selectinload(Patient.user),
                selectinload(TreatmentProposal.hospital),
            )
            .where(
                TreatmentProposal.consultation_id == consultation_id,
                TreatmentProposal.is_deleted == False,
            ).order_by(TreatmentProposal.created_at.desc())
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    async def _get_proposal(self, proposal_id: UUID) -> Optional[TreatmentProposal]:
        result = await self.db.execute(
            select(TreatmentProposal)
            .options(
                selectinload(TreatmentProposal.doctor).selectinload(Doctor.user),
                selectinload(TreatmentProposal.patient).selectinload(Patient.user),
                selectinload(TreatmentProposal.hospital),
            )
            .where(
                TreatmentProposal.id == proposal_id,
                TreatmentProposal.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()
