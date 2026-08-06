"""API v1 router aggregating all endpoints."""

from fastapi import APIRouter

from app.api.v1 import (
    auth, users, patients, doctors, consultations, appointments,
    hotels, restaurants, bookings, apartments, stays, payments, chat, ai, cms,
    pages, admin_site, leads, notifications, email, events, config, documents,
    patient_documents, patient_medical_records, patient_medical_reports, rbac, dashboard,
    admin_hospital, admin_department, admin_doctor, admin_patient,
    admin_hotel, admin_apartment, admin_restaurant,
    admin_forex, admin_package, forex,
    hospitals, departments, reviews,
    packages, favorites, images,
    shared_documents, treatment_proposals,
    careers, admin_career,
    admin_knowledge,
    admin_hospitality,
    rbac_admin,
    admin_bookings,
    contact,
    admin_contact,
)

api_router = APIRouter()

# Authentication
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# Core user management
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(patients.router, prefix="/patients", tags=["Patients"])
api_router.include_router(patient_documents.router, prefix="/patients", tags=["Patient Documents"])
api_router.include_router(patient_medical_records.router, prefix="/patients", tags=["Patient Medical Records"])
api_router.include_router(patient_medical_reports.router, prefix="/patients", tags=["Patient Medical Reports"])
api_router.include_router(doctors.router, prefix="/doctors", tags=["Doctors"])
api_router.include_router(hospitals.router, prefix="/hospitals", tags=["Hospitals"])
api_router.include_router(departments.router, prefix="/departments", tags=["Departments"])

# Medical services
api_router.include_router(consultations.router, prefix="/consultations", tags=["Consultations"])
api_router.include_router(appointments.router, prefix="/appointments", tags=["Appointments"])

# Accommodation & Dining
api_router.include_router(hotels.router, prefix="/hotels", tags=["Hotels"])
api_router.include_router(apartments.router, prefix="/apartments", tags=["Apartments"])
api_router.include_router(stays.router, prefix="/stays", tags=["Stays (Apartments)"])
api_router.include_router(reviews.router, prefix="/reviews", tags=["Reviews & Ratings"])
api_router.include_router(restaurants.router, prefix="/restaurants", tags=["Restaurants"])

# Bookings & Payments
api_router.include_router(bookings.router, prefix="/bookings", tags=["Bookings"])
api_router.include_router(admin_bookings.router, prefix="/admin/bookings", tags=["Admin - Bookings"])
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

# Admin - RBAC (Role-Based Access Control)
api_router.include_router(rbac.router, prefix="/admin/rbac", tags=["Admin - RBAC"])
api_router.include_router(rbac_admin.router)  # Already has prefix

# Admin - Dashboard KPIs
api_router.include_router(dashboard.router, prefix="/admin/dashboard", tags=["Admin - Dashboard"])

# Admin - Hospital Management
api_router.include_router(admin_hospital.router, prefix="/admin/hospitals", tags=["Admin - Hospitals"])

# Admin - Department Management
api_router.include_router(admin_department.router, prefix="/admin/departments", tags=["Admin - Departments"])

# Admin - Doctor Management
api_router.include_router(admin_doctor.router, prefix="/admin/doctors", tags=["Admin - Doctors"])

# Admin - Patient Management
api_router.include_router(admin_patient.router, prefix="/admin/patients", tags=["Admin - Patients"])

# Admin - Hotel Management
api_router.include_router(admin_hotel.router, prefix="/admin/hotels", tags=["Admin - Hotels"])

# Admin - Apartment Management
api_router.include_router(admin_apartment.router, prefix="/admin/apartments", tags=["Admin - Apartments"])

# Admin - Restaurant Management
api_router.include_router(admin_restaurant.router, prefix="/admin/restaurants", tags=["Admin - Restaurants"])

# Admin - Hospitality (Beyond Medical Care)
api_router.include_router(admin_hospitality.router, prefix="/admin/hospitality", tags=["Admin - Hospitality"])

# Admin - Forex Management
api_router.include_router(admin_forex.router, prefix="/admin/forex", tags=["Admin - Forex Exchange"])

# Forex Management
api_router.include_router(forex.router, prefix="/forex", tags=["Forex Exchange"])

# Medical Packages
api_router.include_router(packages.router, prefix="/packages", tags=["Medical Packages"])
api_router.include_router(admin_package.router, prefix="/admin/packages", tags=["Admin - Medical Packages"])

# Favorites / Wishlist
api_router.include_router(favorites.router, prefix="/favorites", tags=["Favorites"])

# Lead Generation
api_router.include_router(leads.router, prefix="/leads", tags=["Lead Generation"])

# Contact Us
api_router.include_router(contact.router, prefix="/contact", tags=["Contact"])
api_router.include_router(admin_contact.router, prefix="/admin/contacts", tags=["Admin - Contacts"])

# System & Infrastructure
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(email.router, prefix="/email", tags=["Email System"])
api_router.include_router(events.router, prefix="/events", tags=["Events & Calendar"])
api_router.include_router(config.router, prefix="/config", tags=["Configuration"])
api_router.include_router(documents.router, prefix="/documents", tags=["Document Management"])
api_router.include_router(shared_documents.router, prefix="/shared-documents", tags=["Shared Documents"])

# Treatment Proposals
api_router.include_router(treatment_proposals.router, prefix="/treatment-proposals", tags=["Treatment Proposals"])

# Careers
api_router.include_router(careers.router, prefix="/careers", tags=["Careers"])
api_router.include_router(admin_career.router, prefix="/admin/careers", tags=["Admin - Careers"])

# Admin - Knowledge Documents (RAG)
api_router.include_router(admin_knowledge.router, prefix="/admin/knowledge", tags=["Admin - Knowledge Documents"])

# Image Management
api_router.include_router(images.admin_router, prefix="/admin/images", tags=["Admin - Image Upload"])
api_router.include_router(images.admin_router, prefix="/images", tags=["Image Upload"])
api_router.include_router(images.public_router, prefix="/images", tags=["Images (Public)"])

