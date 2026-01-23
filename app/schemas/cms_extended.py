"""Extended CMS schemas based on Flora Medical site structure."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import BaseSchema, PaginatedResponse
from app.utils.enums import CMSBlockType, CMSPageStatus


# ============== Extended Block Types ==============

class HeroBlockConfig(BaseModel):
    """Hero section configuration."""
    title: str
    subtitle: Optional[str] = None
    background_image: Optional[str] = None
    background_video: Optional[str] = None
    primary_cta_text: Optional[str] = None
    primary_cta_url: Optional[str] = None
    secondary_cta_text: Optional[str] = None
    secondary_cta_url: Optional[str] = None
    overlay_opacity: float = 0.5
    text_alignment: str = "center"  # left, center, right


class StatsItem(BaseModel):
    """Single stat item."""
    icon: Optional[str] = None
    label: str
    value: str
    suffix: Optional[str] = None  # %, +, etc.


class StatsGridConfig(BaseModel):
    """Stats grid configuration."""
    title: Optional[str] = None
    items: List[StatsItem]
    columns: int = 4
    style: str = "default"  # default, card, minimal


class ServiceCardItem(BaseModel):
    """Service/treatment card."""
    id: Optional[UUID] = None
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    icon: Optional[str] = None
    rating: Optional[float] = None
    patient_count: Optional[int] = None
    success_rate: Optional[float] = None
    savings_percent: Optional[int] = None
    tags: List[str] = []
    price_from: Optional[float] = None
    cta_text: str = "Learn More"
    cta_url: Optional[str] = None


class ListingGridConfig(BaseModel):
    """Listing grid for services, doctors, hospitals."""
    title: Optional[str] = None
    subtitle: Optional[str] = None
    entity_type: str  # services, doctors, hospitals, destinations
    show_filters: bool = True
    filter_categories: List[str] = []
    items_per_page: int = 12
    show_search: bool = True
    layout: str = "grid"  # grid, list


class DoctorCardItem(BaseModel):
    """Doctor profile card."""
    id: Optional[UUID] = None
    name: str
    title: Optional[str] = None
    specialization: str
    hospital_name: Optional[str] = None
    image_url: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    experience_years: Optional[int] = None
    consultation_fee: Optional[float] = None
    is_verified: bool = False
    available_for_video: bool = True
    languages: List[str] = []


class HospitalCardItem(BaseModel):
    """Hospital card."""
    id: Optional[UUID] = None
    name: str
    city: str
    country: str
    image_url: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    accreditations: List[str] = []
    specialties: List[str] = []
    beds: Optional[int] = None
    established_year: Optional[int] = None


class DestinationCardItem(BaseModel):
    """Destination card."""
    id: Optional[UUID] = None
    name: str
    slug: str
    country: str
    image_url: Optional[str] = None
    hospital_count: int = 0
    doctor_count: int = 0
    accommodation_count: int = 0
    description: Optional[str] = None
    highlights: List[str] = []


class FAQItem(BaseModel):
    """FAQ accordion item."""
    question: str
    answer: str
    category: Optional[str] = None
    order: int = 0


class AccordionConfig(BaseModel):
    """FAQ accordion configuration."""
    title: Optional[str] = None
    show_categories: bool = True
    categories: List[str] = []
    items: List[FAQItem]
    allow_multiple_open: bool = False


class StepItem(BaseModel):
    """Step wizard item."""
    number: int
    icon: Optional[str] = None
    title: str
    description: str


class StepWizardConfig(BaseModel):
    """How it works step wizard."""
    title: Optional[str] = None
    subtitle: Optional[str] = None
    steps: List[StepItem]
    layout: str = "horizontal"  # horizontal, vertical


class FormFieldConfig(BaseModel):
    """Form field configuration."""
    name: str
    label: str
    field_type: str  # text, email, phone, select, textarea, file, country
    placeholder: Optional[str] = None
    required: bool = False
    options: List[str] = []  # for select fields
    validation_regex: Optional[str] = None


class FormBlockConfig(BaseModel):
    """Lead generation form configuration."""
    title: str
    subtitle: Optional[str] = None
    fields: List[FormFieldConfig]
    submit_text: str = "Submit"
    success_message: str = "Thank you for your submission!"
    redirect_url: Optional[str] = None
    notification_email: Optional[str] = None


class MediaCardConfig(BaseModel):
    """Media card for accommodations, dining."""
    title: str
    subtitle: Optional[str] = None
    image_url: str
    description: Optional[str] = None
    cta_text: Optional[str] = None
    cta_url: Optional[str] = None
    badge: Optional[str] = None
    price: Optional[str] = None


class TestimonialItem(BaseModel):
    """Patient testimonial."""
    id: Optional[UUID] = None
    patient_name: str
    patient_country: Optional[str] = None
    patient_avatar: Optional[str] = None
    rating: int = 5
    treatment: Optional[str] = None
    hospital: Optional[str] = None
    content: str
    video_url: Optional[str] = None
    date: Optional[datetime] = None


class TestimonialsConfig(BaseModel):
    """Testimonials section configuration."""
    title: Optional[str] = None
    subtitle: Optional[str] = None
    items: List[TestimonialItem]
    layout: str = "carousel"  # carousel, grid
    show_rating: bool = True


class TeamMemberItem(BaseModel):
    """Team member card."""
    name: str
    role: str
    image_url: Optional[str] = None
    bio: Optional[str] = None
    linkedin: Optional[str] = None
    twitter: Optional[str] = None


class TeamConfig(BaseModel):
    """Team section configuration."""
    title: Optional[str] = None
    subtitle: Optional[str] = None
    members: List[TeamMemberItem]


class ValueItem(BaseModel):
    """Core value item."""
    icon: str
    title: str
    description: str


class ValuesConfig(BaseModel):
    """Core values section."""
    title: Optional[str] = None
    items: List[ValueItem]


class TimelineItem(BaseModel):
    """Timeline/milestone item."""
    year: str
    title: str
    description: str


class TimelineConfig(BaseModel):
    """Timeline/milestones section."""
    title: Optional[str] = None
    items: List[TimelineItem]


class NewsletterConfig(BaseModel):
    """Newsletter subscription."""
    title: str = "Subscribe to our newsletter"
    subtitle: Optional[str] = None
    placeholder: str = "Enter your email"
    button_text: str = "Subscribe"


class ContactInfoConfig(BaseModel):
    """Contact information block."""
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    working_hours: Optional[str] = None
    map_embed_url: Optional[str] = None
    social_links: Dict[str, str] = {}


class TrustBarConfig(BaseModel):
    """Trust bar with patient count and flags."""
    patient_count: str
    countries: List[str] = []
    message: Optional[str] = None


class CategoryLinksConfig(BaseModel):
    """Category fast links."""
    items: List[Dict[str, str]]  # [{icon, label, url}]


# ============== Page Templates ==============

class HomePageData(BaseModel):
    """Home page structured data."""
    hero: HeroBlockConfig
    trust_bar: Optional[TrustBarConfig] = None
    category_links: Optional[CategoryLinksConfig] = None
    featured_services: Optional[ListingGridConfig] = None
    how_it_works: Optional[StepWizardConfig] = None
    featured_doctors: Optional[List[DoctorCardItem]] = None
    destinations: Optional[List[DestinationCardItem]] = None
    testimonials: Optional[TestimonialsConfig] = None
    lead_form: Optional[FormBlockConfig] = None
    stats: Optional[StatsGridConfig] = None


class ServicesPageData(BaseModel):
    """Services page structured data."""
    hero: HeroBlockConfig
    categories: List[str] = []
    services: List[ServiceCardItem] = []


class DoctorsPageData(BaseModel):
    """Doctors listing page data."""
    hero: HeroBlockConfig
    filters: Dict[str, List[str]] = {}
    doctors: List[DoctorCardItem] = []


class HospitalsPageData(BaseModel):
    """Hospitals listing page data."""
    hero: HeroBlockConfig
    filters: Dict[str, List[str]] = {}
    hospitals: List[HospitalCardItem] = []


class DestinationPageData(BaseModel):
    """Single destination page data."""
    hero: HeroBlockConfig
    stats: StatsGridConfig
    hospitals: List[HospitalCardItem] = []
    doctors: List[DoctorCardItem] = []
    accommodations: List[MediaCardConfig] = []
    restaurants: List[MediaCardConfig] = []
    why_choose: List[ValueItem] = []


class AboutPageData(BaseModel):
    """About page structured data."""
    hero: HeroBlockConfig
    vision: Optional[Dict[str, str]] = None
    values: Optional[ValuesConfig] = None
    timeline: Optional[TimelineConfig] = None
    team: Optional[TeamConfig] = None
    stats: Optional[StatsGridConfig] = None


class FAQPageData(BaseModel):
    """FAQ page structured data."""
    hero: HeroBlockConfig
    categories: List[str] = []
    faqs: AccordionConfig


class ContactPageData(BaseModel):
    """Contact page structured data."""
    hero: HeroBlockConfig
    contact_info: ContactInfoConfig
    form: FormBlockConfig


class BlogPostSummary(BaseModel):
    """Blog post summary for listings."""
    id: UUID
    title: str
    slug: str
    excerpt: str
    featured_image: Optional[str] = None
    author_name: str
    author_avatar: Optional[str] = None
    category: str
    published_at: datetime
    read_time_minutes: int = 5
    tags: List[str] = []


class BlogPageData(BaseModel):
    """Blog listing page data."""
    hero: HeroBlockConfig
    categories: List[str] = []
    featured_post: Optional[BlogPostSummary] = None
    posts: List[BlogPostSummary] = []


# ============== API Response Schemas ==============

class PageContentResponse(BaseSchema):
    """Dynamic page content API response."""
    slug: str
    title: str
    template: str
    meta: Dict[str, Any] = {}
    content: Dict[str, Any] = {}


class NavigationItem(BaseModel):
    """Navigation menu item."""
    label: str
    url: str
    icon: Optional[str] = None
    children: List["NavigationItem"] = []
    badge: Optional[str] = None


NavigationItem.model_rebuild()


class NavigationResponse(BaseModel):
    """Full navigation structure."""
    main_menu: List[NavigationItem]
    footer_menu: Dict[str, List[NavigationItem]]
    social_links: Dict[str, str] = {}


class SiteSettingsResponse(BaseModel):
    """Global site settings."""
    site_name: str
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    social_links: Dict[str, str] = {}
    analytics_id: Optional[str] = None
    default_currency: str = "USD"
    supported_languages: List[str] = ["en"]
