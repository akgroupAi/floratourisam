"""Patient dashboard summary service."""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.medical_report import MedicalReport
from app.models.consultation import Consultation
from app.models.chat import ChatRoom, ChatParticipant, ChatMessage
from app.services.document_service import DocumentService
from app.services.appointment_service import AppointmentService
from app.services.chat_service import ChatService
from app.schemas.dashboard import PatientDashboardSummary

class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_patient_dashboard_summary(self, patient_id: UUID, user_id: UUID) -> PatientDashboardSummary:
        # Documents
        total_documents = await self.db.scalar(
            select(func.count()).select_from(MedicalReport).where(
                MedicalReport.patient_id == patient_id,
                MedicalReport.is_deleted == False
            )
        )
        recent_documents = await self.db.scalar(
            select(func.count()).select_from(MedicalReport).where(
                MedicalReport.patient_id == patient_id,
                MedicalReport.is_deleted == False,
                MedicalReport.created_at >= datetime.utcnow() - timedelta(days=30)
            )
        )

        # Appointments
        total_appointments = await self.db.scalar(
            select(func.count()).select_from(Consultation).where(
                Consultation.patient_id == patient_id,
                Consultation.is_deleted == False
            )
        )
        upcoming_appointments = await self.db.scalar(
            select(func.count()).select_from(Consultation).where(
                Consultation.patient_id == patient_id,
                Consultation.is_deleted == False,
                Consultation.scheduled_at >= datetime.utcnow(),
                Consultation.status.in_(["scheduled", "pending", "waiting", "in_progress"])
            )
        )
        next_appointment = await self.db.execute(
            select(Consultation.scheduled_at).where(
                Consultation.patient_id == patient_id,
                Consultation.is_deleted == False,
                Consultation.scheduled_at >= datetime.utcnow(),
                Consultation.status.in_(["scheduled", "pending", "waiting", "in_progress"])
            ).order_by(Consultation.scheduled_at.asc()).limit(1)
        )
        next_appointment_at = next_appointment.scalar_one_or_none()

        # Messages (all chat rooms for this user)
        # Total messages
        room_ids_result = await self.db.execute(
            select(ChatParticipant.room_id).where(
                ChatParticipant.user_id == user_id,
                ChatParticipant.is_active == True,
                ChatParticipant.is_deleted == False
            )
        )
        room_ids = [row[0] for row in room_ids_result.all()]
        total_messages = 0
        unread_messages = 0
        if room_ids:
            total_messages = await self.db.scalar(
                select(func.count()).select_from(ChatMessage).where(
                    ChatMessage.room_id.in_(room_ids)
                )
            )
            unread_messages = await self.db.scalar(
                select(func.sum(ChatParticipant.unread_count)).where(
                    ChatParticipant.user_id == user_id,
                    ChatParticipant.room_id.in_(room_ids)
                )
            ) or 0

        return PatientDashboardSummary(
            total_documents=total_documents or 0,
            recent_documents=recent_documents or 0,
            total_appointments=total_appointments or 0,
            upcoming_appointments=upcoming_appointments or 0,
            next_appointment_at=next_appointment_at,
            total_messages=total_messages or 0,
            unread_messages=unread_messages or 0,
        )
