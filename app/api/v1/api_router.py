"""API v1 router aggregating all endpoints."""

from fastapi import APIRouter

from app.api.v1 import (
    auth, users, patients, doctors, consultations,
    hotels, restaurants, bookings, payments, chat, ai, cms,
    pages, admin_site, leads, notifications, email, events, config, documents,
)

api_router = APIRouter()

# Authentication
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# Core user management
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(patients.router, prefix="/patients", tags=["Patients"])
api_router.include_router(doctors.router, prefix="/doctors", tags=["Doctors"])

# Medical services
api_router.include_router(consultations.router, prefix="/consultations", tags=["Consultations"])

# Accommodation & Dining
api_router.include_router(hotels.router, prefix="/hotels", tags=["Hotels"])
api_router.include_router(restaurants.router, prefix="/restaurants", tags=["Restaurants"])

# Bookings & Payments
api_router.include_router(bookings.router, prefix="/bookings", tags=["Bookings"])
api_router.include_router(payments.router, prefix="/payments", tags=["Payments"])

# Communication
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
api_router.include_router(ai.router, prefix="/ai", tags=["AI Assistant"])

# CMS (generic)
api_router.include_router(cms.router, prefix="/cms", tags=["CMS"])

# Public Pages (Flora Medical specific)
api_router.include_router(pages.router, prefix="/pages", tags=["Public Pages"])

# Admin Site Management
api_router.include_router(admin_site.router, prefix="/admin/site", tags=["Admin - Site Content"])

# Lead Generation
api_router.include_router(leads.router, prefix="/leads", tags=["Lead Generation"])

# System & Infrastructure
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(email.router, prefix="/email", tags=["Email System"])
api_router.include_router(events.router, prefix="/events", tags=["Events & Calendar"])
api_router.include_router(config.router, prefix="/config", tags=["Configuration"])
api_router.include_router(documents.router, prefix="/documents", tags=["Document Management"])
