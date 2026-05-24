"""Enum definitions for the application."""

from enum import Enum


class UserRole(str, Enum):
    """User role definitions for RBAC."""

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    PATIENT = "patient"
    DOCTOR = "doctor"
    HOTEL_MANAGER = "hotel_manager"
    APARTMENT_MANAGER = "apartment_manager"
    RESTAURANT_MANAGER = "restaurant_manager"

    # Creator-Admin roles (self-onboarding entity owners)
    HOTEL_ADMIN = "hotel_admin"
    APARTMENT_ADMIN = "apartment_admin"
    HOSPITAL_ADMIN = "hospital_admin"
    RESTAURANT_ADMIN = "restaurant_admin"


class EntityType(str, Enum):
    """Entity types that creator admins can own."""

    HOTEL = "HOTEL"
    APARTMENT = "APARTMENT"
    HOSPITAL = "HOSPITAL"
    RESTAURANT = "RESTAURANT"


# Maps creator-admin roles to their managed entity type
CREATOR_ADMIN_ENTITY_MAP: dict = {
    UserRole.HOTEL_ADMIN: EntityType.HOTEL,
    UserRole.APARTMENT_ADMIN: EntityType.APARTMENT,
    UserRole.HOSPITAL_ADMIN: EntityType.HOSPITAL,
    UserRole.RESTAURANT_ADMIN: EntityType.RESTAURANT,
}


class BookingType(str, Enum):
    """Types of bookings in the system."""

    CONSULTATION = "consultation"
    HOTEL = "hotel"
    APARTMENT = "apartment"
    RESTAURANT = "restaurant"
    PACKAGE = "package"


class BookingStatus(str, Enum):
    """Status of bookings."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class PaymentStatus(str, Enum):
    """Payment status definitions."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class PaymentMethod(str, Enum):
    """Payment method types."""

    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    BANK_TRANSFER = "bank_transfer"
    WALLET = "wallet"
    CASH = "cash"


class ConsultationType(str, Enum):
    """Types of medical consultations."""

    VIDEO = "video"
    CHAT = "chat"
    IN_PERSON = "in_person"
    PHONE = "phone"


class ConsultationStatus(str, Enum):
    """Status of consultations."""

    PENDING = "pending"
    SCHEDULED = "scheduled"
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    MISSED = "missed"


class Gender(str, Enum):
    """Gender definitions."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class RoomType(str, Enum):
    """Hotel room types."""

    SINGLE = "single"
    DOUBLE = "double"
    SUITE = "suite"
    DELUXE = "deluxe"
    PRESIDENTIAL = "presidential"


class MealType(str, Enum):
    """Meal types for restaurant bookings."""

    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class ChatRoomType(str, Enum):
    """Types of chat rooms."""

    CONSULTATION = "consultation"
    SUPPORT = "support"
    GROUP = "group"


class MessageType(str, Enum):
    """Types of chat messages."""

    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    SYSTEM = "system"


class CMSBlockType(str, Enum):
    """Types of CMS content blocks."""

    HERO = "hero"
    TEXT = "text"
    IMAGE = "image"
    GALLERY = "gallery"
    FAQ = "faq"
    TESTIMONIAL = "testimonial"
    CTA = "cta"
    VIDEO = "video"
    FEATURES = "features"
    PRICING = "pricing"
    TEAM = "team"
    CONTACT = "contact"
    CUSTOM = "custom"


class CMSPageStatus(str, Enum):
    """Status of CMS pages."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class NotificationType(str, Enum):
    """Types of notifications."""

    BOOKING_CONFIRMED = "booking_confirmed"
    BOOKING_CANCELLED = "booking_cancelled"
    PAYMENT_RECEIVED = "payment_received"
    CONSULTATION_REMINDER = "consultation_reminder"
    MESSAGE_RECEIVED = "message_received"
    SYSTEM = "system"


class FavoriteEntityType(str, Enum):
    """Types of entities that can be saved to a patient's favorites."""

    DOCTOR = "doctor"
    HOSPITAL = "hospital"
    PACKAGE = "package"
    HOTEL = "hotel"
    APARTMENT = "apartment"
    RESTAURANT = "restaurant"


class PackageCategory(str, Enum):
    """Medical package categories."""

    CARDIAC = "cardiac"
    ORTHOPEDIC = "orthopedic"
    DENTAL = "dental"
    WELLNESS = "wellness"
    COSMETIC = "cosmetic"
    FERTILITY = "fertility"
    ONCOLOGY = "oncology"
    NEUROLOGY = "neurology"
    OPHTHALMOLOGY = "ophthalmology"
    GENERAL = "general"


class PackageItemType(str, Enum):
    """Types of items included in a medical package."""

    CONSULTATION = "consultation"
    PROCEDURE = "procedure"
    DIAGNOSTIC_TEST = "diagnostic_test"
    HOSPITAL_STAY = "hospital_stay"
    MEDICATION = "medication"
    THERAPY = "therapy"
    OTHER = "other"


class BloodGroup(str, Enum):
    """Blood group definitions."""

    A_POSITIVE = "A+"
    A_NEGATIVE = "A-"
    B_POSITIVE = "B+"
    B_NEGATIVE = "B-"
    O_POSITIVE = "O+"
    O_NEGATIVE = "O-"
    AB_POSITIVE = "AB+"
    AB_NEGATIVE = "AB-"
