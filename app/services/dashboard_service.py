"""Dashboard summary service."""
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_, extract, cast, Date, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.user import User
from app.models.booking import Booking
from app.models.consultation import Consultation
from app.models.site import LeadSubmission
from app.models.payment import Payment
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.hospital import Hospital
from app.models.hotel import Hotel, Room
from app.models.apartment import Apartment
from app.models.shared_document import SharedDocument
from app.models.chat import ChatMessage, ChatParticipant
from app.utils.enums import UserRole
from app.schemas.dashboard import (
    PatientDashboardSummary, 
    AdminDashboardSummary,
    UserStats,
    BookingStats,
    RevenueStats,
    ConsultationStats,
    LeadStats,
    Activity,
    RecentPatient,
    TodaySchedule,
    ScheduleItem,
    RoomOccupancy
)

class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_patient_dashboard_summary(self, patient_id: UUID, user_id: UUID) -> PatientDashboardSummary:
        # Documents (using SharedDocument)
        total_documents = await self.db.scalar(
            select(func.count()).select_from(SharedDocument).where(
                ((SharedDocument.sender_id == user_id) | (SharedDocument.receiver_id == user_id)),
                SharedDocument.is_deleted == False
            )
        )
        recent_documents = await self.db.scalar(
            select(func.count()).select_from(SharedDocument).where(
                ((SharedDocument.sender_id == user_id) | (SharedDocument.receiver_id == user_id)),
                SharedDocument.is_deleted == False,
                SharedDocument.created_at >= datetime.utcnow() - timedelta(days=30)
            )
        )
        pending_review_documents = await self.db.scalar(
            select(func.count()).select_from(SharedDocument).where(
                SharedDocument.receiver_id == user_id,
                SharedDocument.is_viewed == False,
                SharedDocument.is_deleted == False
            )
        )
        documents_uploaded_this_week = await self.db.scalar(
            select(func.count()).select_from(SharedDocument).where(
                SharedDocument.sender_id == user_id,
                SharedDocument.is_deleted == False,
                SharedDocument.created_at >= datetime.utcnow() - timedelta(days=7)
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

        # Last received message
        last_received_message_at = None
        if room_ids:
            last_msg = await self.db.execute(
                select(func.max(ChatMessage.created_at)).where(
                    ChatMessage.room_id.in_(room_ids),
                    ChatMessage.sender_id != user_id
                )
            )
            last_received_message_at = last_msg.scalar_one_or_none()

        # Progress
        completed_appointments = await self.db.scalar(
            select(func.count()).select_from(Consultation).where(
                Consultation.patient_id == patient_id,
                Consultation.is_deleted == False,
                Consultation.status == "completed"
            )
        ) or 0
        progress_percentage = (completed_appointments / total_appointments * 100) if total_appointments > 0 else 0.0

        # Current phase
        current_phase = None
        if upcoming_appointments > 0:
            current_phase = "Active Treatment"
        elif total_appointments > 0:
            current_phase = "Post-Treatment"
        else:
            current_phase = "Initial Consultation"

        return PatientDashboardSummary(
            total_documents=total_documents or 0,
            recent_documents=recent_documents or 0,
            pending_review_documents=pending_review_documents or 0,
            documents_uploaded_this_week=documents_uploaded_this_week or 0,
            total_appointments=total_appointments or 0,
            upcoming_appointments=upcoming_appointments or 0,
            next_appointment_at=next_appointment_at,
            total_messages=total_messages or 0,
            unread_messages=unread_messages or 0,
            last_received_message_at=last_received_message_at,
            progress_percentage=progress_percentage,
            current_phase=current_phase,
        )

    async def get_admin_dashboard_summary(self) -> AdminDashboardSummary:
        """Get all KPIs in one call for the main admin dashboard."""
        
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        week_start = today_start - timedelta(days=7)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        
        start_of_month = month_start
        start_of_last_month = (start_of_month - timedelta(days=1)).replace(day=1)

        # 1. User Stats
        users_result = await self.db.execute(
            select(User.role, func.count(User.id).label("count"))
            .where(User.is_deleted == False)
            .group_by(User.role)
        )
        users_by_role = {row.role: row.count for row in users_result}
        total_users = sum(users_by_role.values())
        
        new_today = await self.db.scalar(select(func.count(User.id)).where(User.created_at >= today_start, User.is_deleted == False)) or 0
        new_week = await self.db.scalar(select(func.count(User.id)).where(User.created_at >= week_start, User.is_deleted == False)) or 0
        new_month = await self.db.scalar(select(func.count(User.id)).where(User.created_at >= month_start, User.is_deleted == False)) or 0
        
        active_users = await self.db.scalar(select(func.count(User.id)).where(User.is_active == True, User.is_deleted == False)) or 0
        inactive_users = total_users - active_users
        
        user_growth_chart = []
        for i in range(12, 0, -1):
            m_date = now - timedelta(days=30 * i)
            m_start = m_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            next_m = m_start + timedelta(days=32)
            m_end = next_m.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            count = await self.db.scalar(select(func.count(User.id)).where(User.created_at >= m_start, User.created_at < m_end, User.is_deleted == False)) or 0
            user_growth_chart.append({"month": m_start.strftime("%b %Y"), "count": count})

        user_stats = UserStats(
            total=total_users,
            new_today=new_today,
            new_this_week=new_week,
            new_this_month=new_month,
            by_role=users_by_role,
            active=active_users,
            inactive=inactive_users,
            growth_chart=user_growth_chart
        )

        # 2. Booking Stats
        bookings_result = await self.db.execute(
            select(Booking.status, func.count(Booking.id).label("count"))
            .where(Booking.is_deleted == False)
            .group_by(Booking.status)
        )
        bookings_by_status = {row.status: row.count for row in bookings_result}
        total_bookings = sum(bookings_by_status.values())
        total_booking_revenue = await self.db.scalar(select(func.sum(Booking.total_price)).where(Booking.is_deleted == False)) or 0
        
        booking_trends = []
        for i in range(12, 0, -1):
            m_date = now - timedelta(days=30 * i)
            m_start = m_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            next_m = m_start + timedelta(days=32)
            m_end = next_m.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            count = await self.db.scalar(select(func.count(Booking.id)).where(Booking.created_at >= m_start, Booking.created_at < m_end, Booking.is_deleted == False)) or 0
            booking_trends.append({"month": m_start.strftime("%b %Y"), "count": count})

        booking_stats = BookingStats(
            total=total_bookings,
            by_status=bookings_by_status,
            total_revenue=float(total_booking_revenue),
            trends=booking_trends
        )

        # 3. Revenue Stats
        total_revenue_all_time = await self.db.scalar(select(func.sum(Payment.amount)).where(Payment.status == "completed")) or 0
        revenue_this_year = await self.db.scalar(select(func.sum(Payment.amount)).where(Payment.status == "completed", Payment.created_at >= year_start)) or 0
        revenue_this_month = await self.db.scalar(select(func.sum(Payment.amount)).where(Payment.status == "completed", Payment.created_at >= month_start)) or 0
        revenue_last_month = await self.db.scalar(select(func.sum(Payment.amount)).where(Payment.status == "completed", Payment.created_at >= start_of_last_month, Payment.created_at < start_of_month)) or 0
        avg_booking_value = await self.db.scalar(select(func.avg(Booking.total_price)).where(Booking.is_deleted == False)) or 0
        
        revenue_growth = 0
        if revenue_last_month > 0:
            revenue_growth = ((revenue_this_month - revenue_last_month) / revenue_last_month) * 100
        
        revenue_trends = []
        for i in range(12, 0, -1):
            m_date = now - timedelta(days=30 * i)
            m_start = m_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            next_m = m_start + timedelta(days=32)
            m_end = next_m.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            rev = await self.db.scalar(select(func.sum(Payment.amount)).where(Payment.status == "completed", Payment.created_at >= m_start, Payment.created_at < m_end)) or 0
            revenue_trends.append({"month": m_start.strftime("%b %Y"), "revenue": float(rev)})

        revenue_stats = RevenueStats(
            total=float(total_revenue_all_time),
            this_year=float(revenue_this_year),
            this_month=float(revenue_this_month),
            average_booking_value=float(avg_booking_value),
            trends=revenue_trends,
            growth_percent=round(revenue_growth, 2)
        )

        # 4. Consultation Stats
        consultation_total = await self.db.scalar(select(func.count(Consultation.id)).where(Consultation.is_deleted == False)) or 0
        by_type_res = await self.db.execute(select(Consultation.consultation_type, func.count(Consultation.id).label("count")).where(Consultation.is_deleted == False).group_by(Consultation.consultation_type))
        by_type = {row.consultation_type: row.count for row in by_type_res}
        by_status_res = await self.db.execute(select(Consultation.status, func.count(Consultation.id).label("count")).where(Consultation.is_deleted == False).group_by(Consultation.status))
        by_status = {row.status: row.count for row in by_status_res}

        consultation_stats = ConsultationStats(
            total=consultation_total,
            by_type=by_type,
            by_status=by_status
        )

        # 5. Lead Stats
        lead_total = await self.db.scalar(select(func.count(LeadSubmission.id)).where(LeadSubmission.is_deleted == False)) or 0
        lead_by_status_res = await self.db.execute(select(LeadSubmission.status, func.count(LeadSubmission.id).label("count")).where(LeadSubmission.is_deleted == False).group_by(LeadSubmission.status))
        lead_by_status = {row.status: row.count for row in lead_by_status_res}
        converted = lead_by_status.get("converted", 0)
        conversion_rate = (converted / lead_total * 100) if lead_total > 0 else 0
        
        by_country_res = await self.db.execute(
            select(LeadSubmission.country, func.count(LeadSubmission.id).label("count"))
            .where(LeadSubmission.is_deleted == False, LeadSubmission.country.isnot(None))
            .group_by(LeadSubmission.country)
            .order_by(text("count DESC"))
            .limit(10)
        )
        by_country = {row.country: row.count for row in by_country_res}

        lead_stats = LeadStats(
            total=lead_total,
            by_status=lead_by_status,
            conversion_rate=round(conversion_rate, 2),
            by_country=by_country
        )

        # 6. Activities
        activities = []
        users_act = await self.db.execute(select(User).where(User.is_deleted == False).order_by(User.created_at.desc()).limit(10))
        for user in users_act.scalars():
            activities.append(Activity(type="user_registration", description=f"New user registered: {user.full_name}", timestamp=user.created_at, user_id=str(user.id)))
        
        bookings_act = await self.db.execute(select(Booking).where(Booking.is_deleted == False).order_by(Booking.created_at.desc()).limit(10))
        for booking in bookings_act.scalars():
            activities.append(Activity(type="booking_created", description=f"New booking created (ID: {booking.id})", timestamp=booking.created_at, booking_id=str(booking.id)))
        
        activities.sort(key=lambda x: x.timestamp, reverse=True)
        activities = activities[:20]

        # 7. Other Counts
        total_patients = await self.db.scalar(select(func.count(Patient.id)).where(Patient.is_deleted == False)) or 0
        total_active_hospitals = await self.db.scalar(select(func.count(Hospital.id)).where(Hospital.is_deleted == False, Hospital.is_active == True)) or 0
        total_registered_doctors = await self.db.scalar(select(func.count(Doctor.id)).where(Doctor.is_deleted == False)) or 0
        appointments_today = await self.db.scalar(select(func.count(Consultation.id)).where(Consultation.is_deleted == False, Consultation.scheduled_at >= today_start, Consultation.scheduled_at < today_end)) or 0
        active_doctors = await self.db.scalar(select(func.count(Doctor.id)).where(Doctor.is_verified == True, Doctor.is_deleted == False)) or 0

        # 8. Recent Patients
        recent_patients_res = await self.db.execute(select(Patient).options(joinedload(Patient.user)).where(Patient.is_deleted == False).order_by(Patient.created_at.desc()).limit(5))
        recent_patients = []
        for p in recent_patients_res.scalars():
            recent_patients.append(RecentPatient(
                id=str(p.id),
                full_name=p.user.full_name if p.user else "Unknown",
                email=p.user.email if p.user else None,
                nationality=p.nationality,
                gender=p.gender,
                registered_at=p.created_at
            ))

        # 9. Today's Schedule
        schedule_res = await self.db.execute(
            select(Consultation)
            .options(joinedload(Consultation.patient).joinedload(Patient.user), joinedload(Consultation.doctor).joinedload(Doctor.user))
            .where(Consultation.is_deleted == False, Consultation.scheduled_at >= today_start, Consultation.scheduled_at < today_end)
            .order_by(Consultation.scheduled_at.asc())
        )
        schedule_items = []
        for c in schedule_res.scalars():
            schedule_items.append(ScheduleItem(
                id=str(c.id),
                scheduled_at=c.scheduled_at,
                status=c.status,
                consultation_type=c.consultation_type,
                duration_minutes=c.duration_minutes,
                patient_name=c.patient.user.full_name if c.patient and c.patient.user else "Unknown",
                doctor_name=c.doctor.user.full_name if c.doctor and c.doctor.user else "Unknown",
                reason=c.reason
            ))
        today_schedule = TodaySchedule(date=today_start.date(), total=len(schedule_items), schedule=schedule_items)

        # 10. Apartment Occupancy (apartments live in their own table, one row per unit)
        apt_total = await self.db.scalar(
            select(func.count(Apartment.id)).where(Apartment.is_deleted == False)
        ) or 0
        apt_avail = await self.db.scalar(
            select(func.count(Apartment.id)).where(
                Apartment.is_deleted == False,
                Apartment.is_available == True,
            )
        ) or 0
        apt_occupied = max(0, int(apt_total) - int(apt_avail))
        apt_perc = round((apt_occupied / apt_total * 100), 2) if apt_total > 0 else 0.0
        apartments = RoomOccupancy(total_rooms=int(apt_total), available_rooms=int(apt_avail), occupied_rooms=apt_occupied, occupancy_percentage=apt_perc)

        # 11. Hotel Occupancy (all rooms belong to hotels)
        hotel_total = await self.db.scalar(
            select(func.sum(Room.total_rooms)).where(Room.is_deleted == False)
        ) or 0
        hotel_avail = await self.db.scalar(
            select(func.sum(Room.total_rooms)).where(
                Room.is_deleted == False,
                Room.is_available == True,
            )
        ) or 0
        hotel_occupied = max(0, int(hotel_total) - int(hotel_avail))
        hotel_perc = round((hotel_occupied / hotel_total * 100), 2) if hotel_total > 0 else 0.0
        hotels = RoomOccupancy(total_rooms=int(hotel_total), available_rooms=int(hotel_avail), occupied_rooms=hotel_occupied, occupancy_percentage=hotel_perc)

        return AdminDashboardSummary(
            users=user_stats,
            bookings=booking_stats,
            revenue=revenue_stats,
            consultations=consultation_stats,
            leads=lead_stats,
            activities=activities,
            total_patients=total_patients,
            total_active_hospitals=total_active_hospitals,
            total_registered_doctors=total_registered_doctors,
            appointments_today=appointments_today,
            recent_patients=recent_patients,
            today_schedule=today_schedule,
            apartments=apartments,
            hotels=hotels,
            doctors_active=active_doctors
        )
