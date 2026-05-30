"""Dashboard summary schemas."""

from datetime import datetime, date
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel

class PatientDashboardSummary(BaseModel):
    total_documents: int
    recent_documents: int
    pending_review_documents: int
    documents_uploaded_this_week: int
    total_appointments: int
    upcoming_appointments: int
    next_appointment_at: Optional[datetime]
    total_messages: int
    unread_messages: int
    last_received_message_at: Optional[datetime]
    progress_percentage: float
    current_phase: Optional[str]

# Admin Dashboard Schemas

class UserStats(BaseModel):
    total: int
    new_today: int
    new_this_week: int
    new_this_month: int
    by_role: Dict[str, int]
    active: int
    inactive: int
    growth_chart: List[Dict[str, Any]]

class BookingStats(BaseModel):
    total: int
    by_status: Dict[str, int]
    total_revenue: float
    trends: List[Dict[str, Any]]

class RevenueStats(BaseModel):
    total: float
    this_year: float
    this_month: float
    average_booking_value: float
    trends: List[Dict[str, Any]]
    growth_percent: Optional[float] = None

class ConsultationStats(BaseModel):
    total: int
    by_type: Dict[str, int]
    by_status: Dict[str, int]

class LeadStats(BaseModel):
    total: int
    by_status: Dict[str, int]
    conversion_rate: float
    by_country: Dict[str, int]

class Activity(BaseModel):
    type: str
    description: str
    timestamp: datetime
    user_id: Optional[str] = None
    booking_id: Optional[str] = None

class RecentPatient(BaseModel):
    id: str
    full_name: str
    email: Optional[str]
    nationality: Optional[str]
    gender: Optional[str]
    registered_at: datetime

class ScheduleItem(BaseModel):
    id: str
    scheduled_at: datetime
    status: str
    consultation_type: str
    duration_minutes: Optional[int]
    patient_name: str
    doctor_name: str
    reason: Optional[str]

class TodaySchedule(BaseModel):
    date: date
    total: int
    schedule: List[ScheduleItem]

class RoomOccupancy(BaseModel):
    total_rooms: int
    available_rooms: int
    occupied_rooms: int
    occupancy_percentage: float

class AdminDashboardSummary(BaseModel):
    users: UserStats
    bookings: BookingStats
    revenue: RevenueStats
    consultations: ConsultationStats
    leads: LeadStats
    activities: List[Activity]
    total_patients: int
    total_active_hospitals: int
    total_registered_doctors: int
    appointments_today: int
    recent_patients: List[RecentPatient]
    today_schedule: TodaySchedule
    apartments: RoomOccupancy
    hotels: RoomOccupancy
    doctors_active: int
