"""Dashboard KPI endpoints for admin panel."""

from datetime import datetime, timedelta, date
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import select, func, and_, extract, cast, Date
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import text

from app.api.deps import DatabaseSession, RequireAdmin
from app.models.user import User
from app.models.booking import Booking
from app.models.consultation import Consultation
from app.models.site import LeadSubmission
from app.models.payment import Payment
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.hospital import Hospital
from app.models.hotel import Hotel, Room
from app.utils.enums import UserRole

router = APIRouter()


# ============== MAIN DASHBOARD ==============

@router.get("/summary", dependencies=[RequireAdmin])
async def get_dashboard_summary(db: DatabaseSession):
    """Get all KPIs in one call for the main dashboard."""
    
    # Date ranges
    now = datetime.utcnow()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start_of_last_month = (start_of_month - timedelta(days=1)).replace(day=1)
    
    # Total users by role
    users_result = await db.execute(
        select(
            User.role,
            func.count(User.id).label("count")
        )
        .where(User.is_deleted == False)
        .group_by(User.role)
    )
    users_by_role = {row.role: row.count for row in users_result}
    
    total_users = sum(users_by_role.values())
    
    # Total bookings by status
    bookings_result = await db.execute(
        select(
            Booking.status,
            func.count(Booking.id).label("count")
        )
        .where(Booking.is_deleted == False)
        .group_by(Booking.status)
    )
    bookings_by_status = {row.status: row.count for row in bookings_result}
    
    total_bookings = sum(bookings_by_status.values())
    
    # Revenue this month
    revenue_this_month_result = await db.execute(
        select(func.sum(Payment.amount))
        .where(
            Payment.status == "completed",
            Payment.created_at >= start_of_month
        )
    )
    revenue_this_month = revenue_this_month_result.scalar() or 0
    
    # Revenue last month
    revenue_last_month_result = await db.execute(
        select(func.sum(Payment.amount))
        .where(
            Payment.status == "completed",
            Payment.created_at >= start_of_last_month,
            Payment.created_at < start_of_month
        )
    )
    revenue_last_month = revenue_last_month_result.scalar() or 0
    
    # Revenue growth
    revenue_growth = 0
    if revenue_last_month > 0:
        revenue_growth = ((revenue_this_month - revenue_last_month) / revenue_last_month) * 100
    
    # Consultations
    consultations_result = await db.execute(
        select(
            Consultation.status,
            func.count(Consultation.id).label("count")
        )
        .where(Consultation.is_deleted == False)
        .group_by(Consultation.status)
    )
    consultations_by_status = {row.status: row.count for row in consultations_result}
    
    total_consultations = sum(consultations_by_status.values())
    
    # Leads/Quotes
    leads_result = await db.execute(
        select(
            LeadSubmission.status,
            func.count(LeadSubmission.id).label("count")
        )
        .where(LeadSubmission.is_deleted == False)
        .group_by(LeadSubmission.status)
    )
    leads_by_status = {row.status: row.count for row in leads_result}
    
    total_leads = sum(leads_by_status.values())
    
    # Active doctors
    active_doctors_result = await db.execute(
        select(func.count(Doctor.id))
        .where(
            Doctor.is_verified == True,
            Doctor.is_deleted == False
        )
    )
    active_doctors = active_doctors_result.scalar() or 0
    
    return {
        "users": {
            "total": total_users,
            "by_role": users_by_role,
            "patients": users_by_role.get(UserRole.PATIENT.value, 0),
            "doctors": users_by_role.get(UserRole.DOCTOR.value, 0),
            "admins": users_by_role.get(UserRole.ADMIN.value, 0) + users_by_role.get(UserRole.SUPER_ADMIN.value, 0),
        },
        "bookings": {
            "total": total_bookings,
            "by_status": bookings_by_status,
            "pending": bookings_by_status.get("pending", 0),
            "confirmed": bookings_by_status.get("confirmed", 0),
            "completed": bookings_by_status.get("completed", 0),
            "cancelled": bookings_by_status.get("cancelled", 0),
        },
        "revenue": {
            "this_month": float(revenue_this_month),
            "last_month": float(revenue_last_month),
            "growth_percent": round(revenue_growth, 2),
        },
        "consultations": {
            "total": total_consultations,
            "by_status": consultations_by_status,
            "completed": consultations_by_status.get("completed", 0),
            "upcoming": consultations_by_status.get("scheduled", 0),
        },
        "leads": {
            "total": total_leads,
            "by_status": leads_by_status,
            "new": leads_by_status.get("new", 0),
            "contacted": leads_by_status.get("contacted", 0),
            "converted": leads_by_status.get("converted", 0),
        },
        "doctors": {
            "active": active_doctors,
        },
    }


# ============== USER STATISTICS ==============

@router.get("/users/stats", dependencies=[RequireAdmin])
async def get_user_stats(db: DatabaseSession):
    """Get detailed user statistics."""
    
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Total users
    total_result = await db.execute(
        select(func.count(User.id)).where(User.is_deleted == False)
    )
    total_users = total_result.scalar() or 0
    
    # New users today
    new_today_result = await db.execute(
        select(func.count(User.id))
        .where(
            User.created_at >= today_start,
            User.is_deleted == False
        )
    )
    new_today = new_today_result.scalar() or 0
    
    # New users this week
    new_week_result = await db.execute(
        select(func.count(User.id))
        .where(
            User.created_at >= week_start,
            User.is_deleted == False
        )
    )
    new_week = new_week_result.scalar() or 0
    
    # New users this month
    new_month_result = await db.execute(
        select(func.count(User.id))
        .where(
            User.created_at >= month_start,
            User.is_deleted == False
        )
    )
    new_month = new_month_result.scalar() or 0
    
    # Users by role
    by_role_result = await db.execute(
        select(
            User.role,
            func.count(User.id).label("count")
        )
        .where(User.is_deleted == False)
        .group_by(User.role)
    )
    by_role = {row.role: row.count for row in by_role_result}
    
    # Active vs inactive
    active_result = await db.execute(
        select(func.count(User.id))
        .where(User.is_active == True, User.is_deleted == False)
    )
    active_users = active_result.scalar() or 0
    
    inactive_users = total_users - active_users
    
    # User growth chart (last 12 months)
    growth_chart = []
    for i in range(12, 0, -1):
        month_date = now - timedelta(days=30 * i)
        month_start_date = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = month_start_date + timedelta(days=32)
        month_end_date = next_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        count_result = await db.execute(
            select(func.count(User.id))
            .where(
                User.created_at >= month_start_date,
                User.created_at < month_end_date,
                User.is_deleted == False
            )
        )
        count = count_result.scalar() or 0
        
        growth_chart.append({
            "month": month_start_date.strftime("%b %Y"),
            "count": count
        })
    
    return {
        "total": total_users,
        "new_today": new_today,
        "new_this_week": new_week,
        "new_this_month": new_month,
        "by_role": by_role,
        "active": active_users,
        "inactive": inactive_users,
        "growth_chart": growth_chart,
    }


# ============== BOOKING STATISTICS ==============

@router.get("/bookings/stats", dependencies=[RequireAdmin])
async def get_booking_stats(db: DatabaseSession):
    """Get detailed booking statistics."""
    
    # Total bookings
    total_result = await db.execute(
        select(func.count(Booking.id)).where(Booking.is_deleted == False)
    )
    total_bookings = total_result.scalar() or 0
    
    # Bookings by status
    by_status_result = await db.execute(
        select(
            Booking.status,
            func.count(Booking.id).label("count")
        )
        .where(Booking.is_deleted == False)
        .group_by(Booking.status)
    )
    by_status = {row.status: row.count for row in by_status_result}
    
    # Revenue by booking
    revenue_result = await db.execute(
        select(func.sum(Booking.total_amount))
        .where(Booking.is_deleted == False)
    )
    total_revenue = revenue_result.scalar() or 0
    
    # Booking trends (last 12 months)
    now = datetime.utcnow()
    trends = []
    for i in range(12, 0, -1):
        month_date = now - timedelta(days=30 * i)
        month_start = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = month_start + timedelta(days=32)
        month_end = next_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        count_result = await db.execute(
            select(func.count(Booking.id))
            .where(
                Booking.created_at >= month_start,
                Booking.created_at < month_end,
                Booking.is_deleted == False
            )
        )
        count = count_result.scalar() or 0
        
        trends.append({
            "month": month_start.strftime("%b %Y"),
            "count": count
        })
    
    return {
        "total": total_bookings,
        "by_status": by_status,
        "total_revenue": float(total_revenue),
        "trends": trends,
    }


# ============== REVENUE STATISTICS ==============

@router.get("/revenue/stats", dependencies=[RequireAdmin])
async def get_revenue_stats(db: DatabaseSession):
    """Get detailed revenue statistics."""
    
    now = datetime.utcnow()
    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Total revenue (all time)
    total_result = await db.execute(
        select(func.sum(Payment.amount))
        .where(Payment.status == "completed")
    )
    total_revenue = total_result.scalar() or 0
    
    # Revenue this year
    year_result = await db.execute(
        select(func.sum(Payment.amount))
        .where(
            Payment.status == "completed",
            Payment.created_at >= year_start
        )
    )
    year_revenue = year_result.scalar() or 0
    
    # Revenue this month
    month_result = await db.execute(
        select(func.sum(Payment.amount))
        .where(
            Payment.status == "completed",
            Payment.created_at >= month_start
        )
    )
    month_revenue = month_result.scalar() or 0
    
    # Average booking value
    avg_result = await db.execute(
        select(func.avg(Booking.total_amount))
        .where(Booking.is_deleted == False)
    )
    avg_booking_value = avg_result.scalar() or 0
    
    # Revenue trends (last 12 months)
    trends = []
    for i in range(12, 0, -1):
        month_date = now - timedelta(days=30 * i)
        month_start_date = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = month_start_date + timedelta(days=32)
        month_end_date = next_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        revenue_result = await db.execute(
            select(func.sum(Payment.amount))
            .where(
                Payment.status == "completed",
                Payment.created_at >= month_start_date,
                Payment.created_at < month_end_date
            )
        )
        revenue = revenue_result.scalar() or 0
        
        trends.append({
            "month": month_start_date.strftime("%b %Y"),
            "revenue": float(revenue)
        })
    
    return {
        "total": float(total_revenue),
        "this_year": float(year_revenue),
        "this_month": float(month_revenue),
        "average_booking_value": float(avg_booking_value),
        "trends": trends,
    }


# ============== CONSULTATION STATISTICS ==============

@router.get("/consultations/stats", dependencies=[RequireAdmin])
async def get_consultation_stats(db: DatabaseSession):
    """Get detailed consultation statistics."""
    
    # Total consultations
    total_result = await db.execute(
        select(func.count(Consultation.id)).where(Consultation.is_deleted == False)
    )
    total_consultations = total_result.scalar() or 0
    
    # Consultations by type
    by_type_result = await db.execute(
        select(
            Consultation.consultation_type,
            func.count(Consultation.id).label("count")
        )
        .where(Consultation.is_deleted == False)
        .group_by(Consultation.consultation_type)
    )
    by_type = {row.consultation_type: row.count for row in by_type_result}
    
    # Consultations by status
    by_status_result = await db.execute(
        select(
            Consultation.status,
            func.count(Consultation.id).label("count")
        )
        .where(Consultation.is_deleted == False)
        .group_by(Consultation.status)
    )
    by_status = {row.status: row.count for row in by_status_result}
    
    return {
        "total": total_consultations,
        "by_type": by_type,
        "by_status": by_status,
    }


# ============== LEAD STATISTICS ==============

@router.get("/leads/stats", dependencies=[RequireAdmin])
async def get_lead_stats(db: DatabaseSession):
    """Get detailed lead/quote statistics."""
    
    # Total leads
    total_result = await db.execute(
        select(func.count(LeadSubmission.id)).where(LeadSubmission.is_deleted == False)
    )
    total_leads = total_result.scalar() or 0
    
    # Leads by status
    by_status_result = await db.execute(
        select(
            LeadSubmission.status,
            func.count(LeadSubmission.id).label("count")
        )
        .where(LeadSubmission.is_deleted == False)
        .group_by(LeadSubmission.status)
    )
    by_status = {row.status: row.count for row in by_status_result}
    
    # Conversion rate
    converted = by_status.get("converted", 0)
    conversion_rate = (converted / total_leads * 100) if total_leads > 0 else 0
    
    # Leads by country
    by_country_result = await db.execute(
        select(
            LeadSubmission.country,
            func.count(LeadSubmission.id).label("count")
        )
        .where(LeadSubmission.is_deleted == False, LeadSubmission.country.isnot(None))
        .group_by(LeadSubmission.country)
        .order_by(text("count DESC"))
        .limit(10)
    )
    by_country = {row.country: row.count for row in by_country_result}
    
    return {
        "total": total_leads,
        "by_status": by_status,
        "conversion_rate": round(conversion_rate, 2),
        "by_country": by_country,
    }


# ============== RECENT ACTIVITIES ==============

@router.get("/activities", dependencies=[RequireAdmin])
async def get_recent_activities(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    activity_type: Optional[str] = None,
):
    """Get recent system activities."""
    # This is a simplified version - in production, you'd have a dedicated Activity/AuditLog table
    
    activities = []
    
    # Recent user registrations
    users_result = await db.execute(
        select(User)
        .where(User.is_deleted == False)
        .order_by(User.created_at.desc())
        .limit(10)
    )
    for user in users_result.scalars():
        activities.append({
            "type": "user_registration",
            "description": f"New user registered: {user.full_name}",
            "timestamp": user.created_at,
            "user_id": str(user.id),
        })
    
    # Recent bookings
    bookings_result = await db.execute(
        select(Booking)
        .where(Booking.is_deleted == False)
        .order_by(Booking.created_at.desc())
        .limit(10)
    )
    for booking in bookings_result.scalars():
        activities.append({
            "type": "booking_created",
            "description": f"New booking created (ID: {booking.id})",
            "timestamp": booking.created_at,
            "booking_id": str(booking.id),
        })
    
    # Sort by timestamp
    activities.sort(key=lambda x: x["timestamp"], reverse=True)
    
    # Paginate
    start = (page - 1) * page_size
    end = start + page_size
    paginated_activities = activities[start:end]
    
    return {
        "items": paginated_activities,
        "total": len(activities),
        "page": page,
        "page_size": page_size,
    }


# ============== NEW DASHBOARD KPIs ==============

@router.get("/patients/total", dependencies=[RequireAdmin])
async def get_total_patients(db: DatabaseSession):
    """Get total registered patients count."""
    result = await db.execute(
        select(func.count(Patient.id)).where(Patient.is_deleted == False)
    )
    return {"total_patients": result.scalar() or 0}


@router.get("/hospitals/totalactive", dependencies=[RequireAdmin])
async def get_total_active_hospitals(db: DatabaseSession):
    """Get total active hospitals count."""
    result = await db.execute(
        select(func.count(Hospital.id)).where(
            Hospital.is_deleted == False,
            Hospital.is_active == True
        )
    )
    return {"total_active_hospitals": result.scalar() or 0}


@router.get("/doctors/totalregistered", dependencies=[RequireAdmin])
async def get_total_registered_doctors(db: DatabaseSession):
    """Get total registered doctors count."""
    result = await db.execute(
        select(func.count(Doctor.id)).where(Doctor.is_deleted == False)
    )
    return {"total_registered_doctors": result.scalar() or 0}


@router.get("/appointments/today", dependencies=[RequireAdmin])
async def get_appointments_today(db: DatabaseSession):
    """Get total appointments (consultations) scheduled for today."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    result = await db.execute(
        select(func.count(Consultation.id)).where(
            Consultation.is_deleted == False,
            Consultation.scheduled_at >= today_start,
            Consultation.scheduled_at < today_end,
        )
    )
    return {"appointments_today": result.scalar() or 0}


@router.get("/patients/recent", dependencies=[RequireAdmin])
async def get_recent_patients(db: DatabaseSession):
    """Get top 5 most recently registered patients."""
    result = await db.execute(
        select(Patient)
        .options(joinedload(Patient.user))
        .where(Patient.is_deleted == False)
        .order_by(Patient.created_at.desc())
        .limit(5)
    )
    patients = result.scalars().all()

    items = []
    for p in patients:
        items.append({
            "id": str(p.id),
            "full_name": p.user.full_name if p.user else "Unknown",
            "email": p.user.email if p.user else None,
            "nationality": p.nationality,
            "gender": p.gender,
            "registered_at": p.created_at,
        })

    return {"recent_patients": items}


@router.get("/appointments/schedule/today", dependencies=[RequireAdmin])
async def get_todays_schedule(db: DatabaseSession):
    """Get today's consultation schedule."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    result = await db.execute(
        select(Consultation)
        .options(
            joinedload(Consultation.patient).joinedload(Patient.user),
            joinedload(Consultation.doctor).joinedload(Doctor.user),
        )
        .where(
            Consultation.is_deleted == False,
            Consultation.scheduled_at >= today_start,
            Consultation.scheduled_at < today_end,
        )
        .order_by(Consultation.scheduled_at.asc())
    )
    consultations = result.scalars().all()

    schedule = []
    for c in consultations:
        schedule.append({
            "id": str(c.id),
            "scheduled_at": c.scheduled_at,
            "status": c.status,
            "consultation_type": c.consultation_type,
            "duration_minutes": c.duration_minutes,
            "patient_name": c.patient.user.full_name if c.patient and c.patient.user else "Unknown",
            "doctor_name": c.doctor.user.full_name if c.doctor and c.doctor.user else "Unknown",
            "reason": c.reason,
        })

    return {"date": today_start.date().isoformat(), "total": len(schedule), "schedule": schedule}


# ============== APARTMENT KPIs ==============

@router.get("/apartments/totalrooms", dependencies=[RequireAdmin])
async def get_apartment_total_rooms(db: DatabaseSession):
    """Get total apartment rooms count."""
    result = await db.execute(
        select(func.sum(Room.total_rooms)).where(
            Room.is_deleted == False,
            Room.room_type == "apartment"
        )
    )
    return {"total_rooms": int(result.scalar() or 0)}


@router.get("/apartments/availablerooms", dependencies=[RequireAdmin])
async def get_apartment_available_rooms(db: DatabaseSession):
    """Get total available apartment rooms."""
    result = await db.execute(
        select(func.sum(Room.total_rooms)).where(
            Room.is_deleted == False,
            Room.room_type == "apartment",
            Room.is_available == True
        )
    )
    return {"available_rooms": int(result.scalar() or 0)}


@router.get("/apartments/occupancy", dependencies=[RequireAdmin])
async def get_apartment_occupancy(db: DatabaseSession):
    """Get apartment occupied rooms and occupancy percentage."""
    total_result = await db.execute(
        select(func.sum(Room.total_rooms)).where(
            Room.is_deleted == False,
            Room.room_type == "apartment"
        )
    )
    total_rooms = int(total_result.scalar() or 0)

    available_result = await db.execute(
        select(func.sum(Room.total_rooms)).where(
            Room.is_deleted == False,
            Room.room_type == "apartment",
            Room.is_available == True
        )
    )
    available_rooms = int(available_result.scalar() or 0)
    occupied_rooms = max(0, total_rooms - available_rooms)
    occupancy_percentage = round((occupied_rooms / total_rooms * 100), 2) if total_rooms > 0 else 0.0

    return {
        "total_rooms": total_rooms,
        "available_rooms": available_rooms,
        "occupied_rooms": occupied_rooms,
        "occupancy_percentage": occupancy_percentage,
    }


# ============== HOTEL KPIs ==============

@router.get("/hotels/totalrooms", dependencies=[RequireAdmin])
async def get_hotel_total_rooms(db: DatabaseSession):
    """Get total hotel rooms count (excluding apartments)."""
    result = await db.execute(
        select(func.sum(Room.total_rooms)).where(
            Room.is_deleted == False,
            Room.room_type != "apartment"
        )
    )
    return {"total_rooms": int(result.scalar() or 0)}


@router.get("/hotels/availablerooms", dependencies=[RequireAdmin])
async def get_hotel_available_rooms(db: DatabaseSession):
    """Get total available hotel rooms."""
    result = await db.execute(
        select(func.sum(Room.total_rooms)).where(
            Room.is_deleted == False,
            Room.room_type != "apartment",
            Room.is_available == True
        )
    )
    return {"available_rooms": int(result.scalar() or 0)}


@router.get("/hotels/occupancy", dependencies=[RequireAdmin])
async def get_hotel_occupancy(db: DatabaseSession):
    """Get hotel occupied rooms and occupancy percentage."""
    total_result = await db.execute(
        select(func.sum(Room.total_rooms)).where(
            Room.is_deleted == False,
            Room.room_type != "apartment"
        )
    )
    total_rooms = int(total_result.scalar() or 0)

    available_result = await db.execute(
        select(func.sum(Room.total_rooms)).where(
            Room.is_deleted == False,
            Room.room_type != "apartment",
            Room.is_available == True
        )
    )
    available_rooms = int(available_result.scalar() or 0)
    occupied_rooms = max(0, total_rooms - available_rooms)
    occupancy_percentage = round((occupied_rooms / total_rooms * 100), 2) if total_rooms > 0 else 0.0

    return {
        "total_rooms": total_rooms,
        "available_rooms": available_rooms,
        "occupied_rooms": occupied_rooms,
        "occupancy_percentage": occupancy_percentage,
    }

