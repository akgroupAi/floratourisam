"""Models module containing all SQLAlchemy models."""

from app.models.base import BaseModel, TimestampMixin, AuditMixin
from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor, DoctorSpecialization, DoctorAvailability, DoctorAssignment
from app.models.hospital import Hospital, Department
from app.models.consultation import Consultation
from app.models.medical_report import MedicalReport
from app.models.hotel import Hotel, Room, RoomAvailability
from app.models.restaurant import Restaurant, MenuItem, MealBooking, MenuCategory, Thali, DiningPass, DiningPassPurchase
from app.models.apartment import Apartment, ApartmentAvailability
from app.models.booking import Booking
from app.models.payment import Payment, PaymentTransaction
from app.models.package import MedicalPackage, PackageItem
from app.models.favorite import PatientFavorite
from app.models.chat import ChatRoom, ChatMessage, ChatParticipant
from app.models.ai_log import AILog, AIConversation
from app.models.cms import CMSPage, CMSBlock
from app.models.site import (
    Destination, Treatment, BlogPost, BlogComment, Testimonial, FAQ,
    TeamMember, LeadSubmission, SiteSettings, Navigation, HeroSlider
)
from app.models.rbac import Role, Permission
from app.models.forex import Currency, ForexRequest
from app.models.review import Review
from app.models.hospitality import HospitalityService, HospitalityPage
from app.models.system import Notification, EmailTemplate, EmailLog, Event, AdminConfig, Document, DocumentShare
from app.models.shared_document import SharedDocument, DocumentComment
from app.models.treatment_proposal import TreatmentProposal
from app.models.career import JobPosition, JobApplication
from app.models.knowledge_document import KnowledgeDocument

__all__ = [
    "BaseModel",
    "TimestampMixin",
    "AuditMixin",
    "User",
    "Patient",
    "Doctor",
    "DoctorSpecialization",
    "DoctorAvailability",
    "DoctorAssignment",
    "Hospital",
    "Department",
    "Consultation",
    "MedicalReport",
    "Hotel",
    "Room",
    "RoomAvailability",
    "Restaurant",
    "MenuItem",
    "MealBooking",
    "MenuCategory",
    "Thali",
    "Apartment",
    "ApartmentAvailability",
    "Booking",
    "Payment",
    "PaymentTransaction",
    "ChatRoom",
    "ChatMessage",
    "ChatParticipant",
    "AILog",
    "AIConversation",
    "CMSPage",
    "CMSBlock",
    "HeroSlider",
    "Role",
    "Permission",
    "Review",
    "HospitalityService",
    "HospitalityPage",
    "MedicalPackage",
    "PackageItem",
    "PatientFavorite",
    "BlogComment",
    "Currency",
    "ForexRequest",
    "Notification",
    "EmailTemplate",
    "EmailLog",
    "Event",
    "AdminConfig",
    "Document",
    "DocumentShare",
    "SharedDocument",
    "DocumentComment",
    "TreatmentProposal",
    "JobPosition",
    "JobApplication",
    "KnowledgeDocument",
]
