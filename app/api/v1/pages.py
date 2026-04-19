"""Public pages API endpoints for Flora Medical frontend."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, File, UploadFile, Form
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
import os
import shutil
from pathlib import Path

from app.api.deps import DatabaseSession, CurrentUser
from app.models.site import Destination, Treatment, BlogPost, BlogComment, Testimonial, FAQ, TeamMember, HeroSlider
from app.models.apartment import Apartment
from app.models.restaurant import Restaurant
from app.models.hotel import Hotel
from app.models.hospitality import HospitalityService, HospitalityPage
from app.services.hospitality_service import HospitalityServiceManager
from app.schemas.common import PaginatedResponse
from app.schemas.apartment import ApartmentResponse
from app.schemas.site import (
    DestinationListResponse, DestinationResponse,
    TreatmentListResponse, TreatmentResponse,
    BlogPostListResponse, BlogPostResponse,
    BlogCommentCreate, BlogCommentResponse,
    TestimonialListResponse, FAQResponse, TeamMemberResponse,
    DoctorPublicListResponse, DoctorPublicDetailResponse, HeroSliderResponse
)
from app.services.blog_comment_service import BlogCommentService

router = APIRouter()


# ============== HOME PAGE ==============

@router.get("/home")
async def get_home_page(db: DatabaseSession):
    """Get home page content."""
    
    # Featured treatments
    treatments_result = await db.execute(
        select(Treatment)
        .where(Treatment.is_active == True, Treatment.is_featured == True)
        .order_by(Treatment.display_order)
        .limit(6)
    )
    featured_treatments = treatments_result.scalars().all()
    
    # Featured destinations
    destinations_result = await db.execute(
        select(Destination)
        .where(Destination.is_active == True, Destination.is_featured == True)
        .order_by(Destination.display_order)
        .limit(4)
    )
    featured_destinations = destinations_result.scalars().all()
    
    # Testimonials
    testimonials_result = await db.execute(
        select(Testimonial)
        .where(Testimonial.is_approved == True, Testimonial.is_featured == True)
        .order_by(Testimonial.display_order)
        .limit(5)
    )
    testimonials = testimonials_result.scalars().all()
    
    # Hero Sliders
    hero_sliders_result = await db.execute(
        select(HeroSlider)
        .where(HeroSlider.is_active == True, HeroSlider.is_deleted == False)
        .order_by(HeroSlider.display_order)
    )
    hero_sliders = hero_sliders_result.scalars().all()
    
    # Stats
    patient_count = 5000  # Calculate from bookings
    doctor_count = await db.scalar(select(func.count()).select_from(Treatment))
    hospital_count = 100  # Calculate from hospitals
    
    return {
        "hero_sliders": [HeroSliderResponse.model_validate(h) for h in hero_sliders],
        "hero": {
            "title": "AI-Powered Healthcare Journey",
            "subtitle": "World-class medical care, personalized for you",
            "primary_cta": {"text": "Start Treatment Plan", "url": "/services"},
            "secondary_cta": {"text": "Talk to AI Assistant", "url": "/ai-chat"},
        },
        "trust_bar": {
            "patient_count": f"{patient_count:,}+",
            "countries": ["US", "UK", "AE", "NG", "CA"],
            "message": "Trusted by patients worldwide",
        },
        "category_links": [
            {"icon": "stethoscope", "label": "Medical Care", "url": "/services"},
            {"icon": "hotel", "label": "Stays", "url": "/accommodations"},
            {"icon": "utensils", "label": "Dining", "url": "/restaurants"},
            {"icon": "car", "label": "Transport", "url": "/transport"},
        ],
        "featured_services": [TreatmentListResponse.model_validate(t) for t in featured_treatments],
        "how_it_works": {
            "title": "How It Works",
            "steps": [
                {"number": 1, "icon": "upload", "title": "Upload Records", "description": "Share your medical history securely"},
                {"number": 2, "icon": "brain", "title": "AI Suggestions", "description": "Get personalized treatment recommendations"},
                {"number": 3, "icon": "calendar", "title": "Schedule Consult", "description": "Book with top specialists"},
            ],
        },
        "destinations": [DestinationListResponse.model_validate(d) for d in featured_destinations],
        "testimonials": [TestimonialListResponse.model_validate(t) for t in testimonials],
        "stats": {
            "items": [
                {"label": "Patients Served", "value": f"{patient_count:,}+"},
                {"label": "Success Rate", "value": "98%"},
                {"label": "Partner Hospitals", "value": f"{hospital_count}+"},
                {"label": "Countries", "value": "50+"},
            ],
        },
    }


# ============== HERO SLIDERS ==============

@router.get("/hero-sliders", response_model=List[HeroSliderResponse])
async def list_hero_sliders(db: DatabaseSession):
    """List all active hero sliders."""
    query = select(HeroSlider).where(
        HeroSlider.is_active == True,
        HeroSlider.is_deleted == False
    ).order_by(HeroSlider.display_order)
    
    result = await db.execute(query)
    return result.scalars().all()


# ============== SERVICES/TREATMENTS ==============

@router.get("/services", response_model=PaginatedResponse[TreatmentListResponse])
async def list_services(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    category: Optional[str] = None,
    search: Optional[str] = None,
):
    """List all medical services/treatments."""
    query = select(Treatment).where(Treatment.is_active == True, Treatment.is_deleted == False)
    
    if category:
        query = query.where(Treatment.category == category)
    if search:
        query = query.where(Treatment.name.ilike(f"%{search}%"))
    
    # Count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    # Paginate
    query = query.order_by(Treatment.display_order, Treatment.name)
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    treatments = result.scalars().all()
    
    return PaginatedResponse.create(
        [TreatmentListResponse.model_validate(t) for t in treatments],
        total, page, page_size
    )


@router.get("/services/categories")
async def get_service_categories(db: DatabaseSession):
    """Get all treatment categories."""
    result = await db.execute(
        select(Treatment.category, func.count(Treatment.id))
        .where(Treatment.is_active == True)
        .group_by(Treatment.category)
        .order_by(Treatment.category)
    )
    return [{"name": cat, "count": count} for cat, count in result.all()]


@router.get("/services/{slug}", response_model=TreatmentResponse)
async def get_service(slug: str, db: DatabaseSession):
    """Get treatment by slug."""
    result = await db.execute(
        select(Treatment).where(Treatment.slug == slug, Treatment.is_active == True)
    )
    treatment = result.scalar_one_or_none()
    if not treatment:
        raise HTTPException(status_code=404, detail="Treatment not found")
    return treatment


# ============== DESTINATIONS ==============

@router.get("/destinations", response_model=PaginatedResponse[DestinationListResponse])
async def list_destinations(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    country: Optional[str] = None,
):
    """List all destinations."""
    query = select(Destination).where(Destination.is_active == True, Destination.is_deleted == False)
    
    if country:
        query = query.where(Destination.country == country)
    
    # Count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    # Paginate
    query = query.order_by(Destination.display_order, Destination.name)
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    destinations = result.scalars().all()
    
    return PaginatedResponse.create(
        [DestinationListResponse.model_validate(d) for d in destinations],
        total, page, page_size
    )


@router.get("/destinations/{slug}", response_model=DestinationResponse)
async def get_destination(slug: str, db: DatabaseSession):
    """Get destination by slug with related content."""
    result = await db.execute(
        select(Destination).where(Destination.slug == slug, Destination.is_active == True)
    )
    destination = result.scalar_one_or_none()
    if not destination:
        raise HTTPException(status_code=404, detail="Destination not found")
    return destination


@router.get("/destinations/{slug}/hospitals")
async def get_destination_hospitals(slug: str, db: DatabaseSession):
    """Get hospitals in a destination."""
    # Would query hospitals by destination
    return {"items": [], "total": 0}


@router.get("/services/{slug}/doctors", response_model=PaginatedResponse[TeamMemberResponse])
async def get_service_doctors(
    slug: str,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
):
    """Get doctors related to a service (treatment)."""
    # 1. Get treatment to find category
    treatment_result = await db.execute(
        select(Treatment).where(Treatment.slug == slug)
    )
    treatment = treatment_result.scalar_one_or_none()
    if not treatment:
        raise HTTPException(status_code=404, detail="Treatment not found")
    
    # 2. Find doctors with specialization matching category or name
    # Using TeamMemberResponse temporarily as we don't have a public DoctorResponse in site schemas
    # Effectively we should use a proper doctor schema, but let's assume we map it to TeamMember for now or generic list
    
    # Actually, let's use a join
    from app.models.doctor import Doctor, DoctorSpecialization
    from app.models.user import User
    from sqlalchemy.orm import selectinload
    
    query = (
        select(Doctor)
        .join(DoctorSpecialization, Doctor.id == DoctorSpecialization.doctor_id)
        .join(User, Doctor.user_id == User.id)
        .options(selectinload(Doctor.user))
        .where(
            Doctor.is_verified == True,
            or_(
                DoctorSpecialization.specialization == treatment.category,
                DoctorSpecialization.specialization == treatment.name
            )
        )
        .order_by(Doctor.rating.desc().nulls_last())
        .distinct()
    )
    
    # Count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    doctors = result.scalars().all()
    
    # Transform to response
    items = []
    for doc in doctors:
        items.append(TeamMemberResponse(
            id=doc.id,  # This might need to be user_id or doc_id depending on frontend expectation used in other places
            name=doc.user.full_name if doc.user else f"Dr. {doc.id}", 
            role=doc.title or "Specialist",
            department=treatment.category,
            image_url=doc.user.avatar_url if doc.user else None,
            bio=doc.bio,
            is_active=True,
            display_order=0
        ))

    return PaginatedResponse.create(items, total, page, page_size)


@router.get("/destinations/{slug}/doctors")
async def get_destination_doctors(slug: str, db: DatabaseSession, limit: int = 10):
    """Get top doctors in a destination."""
    # Would query doctors by destination
    return {"items": [], "total": 0}


# ============== DOCTORS ==============

@router.get("/doctors")
async def list_doctors(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    search: Optional[str] = None,
    specialization: Optional[str] = None,
    location: Optional[str] = None,
):
    """List all verified doctors."""
    from app.models.doctor import Doctor, DoctorSpecialization
    from app.models.user import User
    from app.models.hospital import Hospital
    from sqlalchemy.orm import selectinload
    
    query = (
        select(Doctor)
        .join(User, Doctor.user_id == User.id)
        .options(selectinload(Doctor.user))
        .options(selectinload(Doctor.specializations))
        .options(selectinload(Doctor.hospital))
        .where(Doctor.is_verified == True, Doctor.is_deleted == False)
    )
    
    # Filters
    if search:
        query = query.where(
            or_(
                User.full_name.ilike(f"%{search}%"),
                Doctor.title.ilike(f"%{search}%")
            )
        )
    
    if specialization:
        query = query.join(
            DoctorSpecialization,
            DoctorSpecialization.doctor_id == Doctor.id
        ).where(
            DoctorSpecialization.specialization == specialization
        )
    
    if location:
        # Assuming we filter by city from hospital or doctor's primary location
        query = query.join(
            Hospital,
            Doctor.hospital_id == Hospital.id
        ).where(Hospital.city.ilike(f"%{location}%"))
    
    # Count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    # Paginate
    query = query.order_by(Doctor.rating.desc().nulls_last(), Doctor.years_of_experience.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    doctors = result.scalars().all()
    
    # Transform to response
    items = []
    for doc in doctors:
        # Get specializations
        specs = [s.specialization for s in doc.specializations] if doc.specializations else []
        
        # Get primary hospital
        hospital_name = None
        location_city = None
        if doc.hospital:
            hospital_name = doc.hospital.name
            location_city = doc.hospital.city
        
        items.append(DoctorPublicListResponse(
            id=doc.id,
            name=doc.user.full_name if doc.user else f"Dr. {doc.id}",
            title=doc.title,
            specializations=specs,
            rating=doc.rating,
            years_of_experience=doc.years_of_experience,
            hospital_name=hospital_name,
            location=location_city,
            image_url=doc.user.avatar_url if doc.user else None,
            consultation_fee=doc.consultation_fee,
        ))
    
    return PaginatedResponse.create(items, total, page, page_size)


@router.get("/doctors/{doctor_id}")
async def get_doctor_detail(doctor_id: UUID, db: DatabaseSession):
    """Get detailed doctor profile."""
    from app.models.doctor import Doctor
    from app.models.user import User
    from sqlalchemy.orm import selectinload
    
    query = (
        select(Doctor)
        .options(selectinload(Doctor.user))
        .options(selectinload(Doctor.specializations))
        .options(selectinload(Doctor.hospital))
        .where(Doctor.id == doctor_id, Doctor.is_verified == True)
    )
    
    result = await db.execute(query)
    doctor = result.scalar_one_or_none()
    
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    # Get specializations
    specs = [s.specialization for s in doctor.specializations] if doctor.specializations else []
    
    # Get primary hospital
    hospital_name = None
    location_city = None
    if doctor.hospital:
        hospital_name = doctor.hospital.name
        location_city = doctor.hospital.city
    
    return DoctorPublicDetailResponse(
        id=doctor.id,
        name=doctor.user.full_name if doctor.user else f"Dr. {doctor.id}",
        title=doctor.title,
        specializations=specs,
        rating=doctor.rating,
        years_of_experience=doctor.years_of_experience,
        hospital_name=hospital_name,
        location=location_city,
        image_url=doctor.user.avatar_url if doctor.user else None,
        bio=doctor.bio,
        consultation_fee=doctor.consultation_fee,
        languages_spoken=doctor.languages_spoken or [],
        qualifications=doctor.qualifications or [],
    )


# ============== BLOG ==============

@router.get("/blog", response_model=PaginatedResponse[BlogPostListResponse])
async def list_blog_posts(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    category: Optional[str] = None,
    tag: Optional[str] = None,
    search_query: Optional[str] = None,
):
    """List published blog posts."""
    query = select(BlogPost).options(selectinload(BlogPost.author)).where(BlogPost.status == "published", BlogPost.is_deleted == False)
    
    if category:
        query = query.where(BlogPost.category == category)
    if tag:
        query = query.where(BlogPost.tags.any(tag))
    if search_query:
        query = query.where(
            or_(
                BlogPost.title.ilike(f"%{search_query}%"),
                BlogPost.excerpt.ilike(f"%{search_query}%"),
                BlogPost.content.ilike(f"%{search_query}%")
            )
        )
    
    # Count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    # Paginate
    query = query.order_by(BlogPost.published_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    posts = result.scalars().all()
    
    return PaginatedResponse.create(
        [BlogPostListResponse.model_validate(p) for p in posts],
        total, page, page_size
    )


@router.get("/blog/search", response_model=PaginatedResponse[BlogPostListResponse])
async def search_blog_posts(
    db: DatabaseSession,
    q: str = Query(..., min_length=1, description="Search query"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
):
    """Search blog posts."""
    query = select(BlogPost).options(selectinload(BlogPost.author)).where(
        BlogPost.status == "published",
        BlogPost.is_deleted == False,
        or_(
            BlogPost.title.ilike(f"%{q}%"),
            BlogPost.excerpt.ilike(f"%{q}%"),
            BlogPost.content.ilike(f"%{q}%")
        )
    )
    
    # Count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    # Paginate
    query = query.order_by(BlogPost.published_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    posts = result.scalars().all()
    
    return PaginatedResponse.create(
        [BlogPostListResponse.model_validate(p) for p in posts],
        total, page, page_size
    )


@router.get("/blog/categories")
async def get_blog_categories(db: DatabaseSession):
    """Get blog categories."""
    result = await db.execute(
        select(BlogPost.category, func.count(BlogPost.id))
        .where(BlogPost.status == "published")
        .group_by(BlogPost.category)
    )
    return [{"name": cat, "count": count} for cat, count in result.all()]


@router.get("/blog/{slug}", response_model=BlogPostResponse)
async def get_blog_post(slug: str, db: DatabaseSession):
    """Get blog post by slug."""
    result = await db.execute(
        select(BlogPost).options(selectinload(BlogPost.author)).where(BlogPost.slug == slug, BlogPost.status == "published")
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    # Increment view count
    post.view_count += 1
    await db.commit()
    
    return post


@router.get("/blog/{slug}/comments", response_model=List[BlogCommentResponse])
async def list_blog_comments(slug: str, db: DatabaseSession):
    """List approved (threaded) comments for a blog post."""
    result = await db.execute(
        select(BlogPost).where(BlogPost.slug == slug, BlogPost.status == "published")
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")

    service = BlogCommentService(db)
    return await service.get_for_post(post.id, approved_only=True)


@router.post("/blog/{slug}/comments", response_model=BlogCommentResponse, status_code=201)
async def create_blog_comment(
    slug: str,
    data: BlogCommentCreate,
    db: DatabaseSession,
    current_user: CurrentUser = None,
):
    """Submit a comment on a blog post. Auth is optional; guests must supply guest_name."""
    result = await db.execute(
        select(BlogPost).where(BlogPost.slug == slug, BlogPost.status == "published")
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")

    service = BlogCommentService(db)
    user_id = current_user.id if current_user else None
    try:
        return await service.create(post.id, data, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))




@router.get("/about")
async def get_about_page(db: DatabaseSession):
    """Get about page content."""
    
    # Team members
    team_result = await db.execute(
        select(TeamMember)
        .where(TeamMember.is_active == True, TeamMember.is_deleted == False)
        .order_by(TeamMember.display_order)
    )
    team = team_result.scalars().all()
    
    leadership = [m for m in team if m.is_leadership]
    other_members = [m for m in team if not m.is_leadership]
    
    return {
        "hero": {
            "title": "About Flora Medical",
            "subtitle": "Bridging Global Healthcare",
            "background_image": "/images/about-hero.jpg",
        },
        "vision": {
            "title": "Our Vision",
            "content": "To make world-class healthcare accessible to everyone, everywhere.",
        },
        "mission": {
            "title": "Our Mission",
            "content": "We connect patients with the best medical care globally, providing end-to-end support for their healthcare journey.",
        },
        "values": [
            {"icon": "shield", "title": "Trust", "description": "Building lasting relationships through transparency"},
            {"icon": "lightbulb", "title": "Innovation", "description": "Leveraging technology to improve healthcare access"},
            {"icon": "heart", "title": "Compassion", "description": "Treating every patient with care and empathy"},
            {"icon": "eye", "title": "Transparency", "description": "Clear communication at every step"},
        ],
        "timeline": [
            {"year": "2018", "title": "Founded", "description": "Flora Medical was established"},
            {"year": "2020", "title": "Global Expansion", "description": "Expanded to 20+ countries"},
            {"year": "2022", "title": "AI Integration", "description": "Launched AI-powered recommendations"},
            {"year": "2024", "title": "5000+ Patients", "description": "Milestone of serving patients worldwide"},
        ],
        "leadership": [TeamMemberResponse.model_validate(m) for m in leadership],
        "team": [TeamMemberResponse.model_validate(m) for m in other_members],
        "stats": {
            "items": [
                {"label": "Patients Served", "value": "5,000+"},
                {"label": "Partner Hospitals", "value": "100+"},
                {"label": "Countries", "value": "50+"},
                {"label": "Success Rate", "value": "98%"},
            ],
        },
    }


# ============== FAQ ==============

@router.get("/faq")
async def get_faq_page(db: DatabaseSession, category: Optional[str] = None):
    """Get FAQ page content."""
    query = select(FAQ).where(FAQ.is_active == True, FAQ.is_deleted == False)
    
    if category:
        query = query.where(FAQ.category == category)
    
    query = query.order_by(FAQ.category, FAQ.display_order)
    result = await db.execute(query)
    faqs = result.scalars().all()
    
    # Group by category
    categories = {}
    for faq in faqs:
        if faq.category not in categories:
            categories[faq.category] = []
        categories[faq.category].append(FAQResponse.model_validate(faq))
    
    return {
        "hero": {
            "title": "Frequently Asked Questions",
            "subtitle": "Find answers to common questions about medical tourism",
        },
        "categories": list(categories.keys()),
        "faqs_by_category": categories,
        "all_faqs": [FAQResponse.model_validate(f) for f in faqs],
    }


@router.get("/faq/categories")
async def get_faq_categories(db: DatabaseSession):
    """Get FAQ categories."""
    result = await db.execute(
        select(FAQ.category, func.count(FAQ.id))
        .where(FAQ.is_active == True)
        .group_by(FAQ.category)
    )
    return [{"name": cat, "count": count} for cat, count in result.all()]


# ============== TESTIMONIALS ==============

@router.get("/testimonials", response_model=PaginatedResponse[TestimonialListResponse])
async def list_testimonials(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
):
    """List approved testimonials."""
    query = select(Testimonial).where(
        Testimonial.is_approved == True, Testimonial.is_deleted == False
    )
    
    # Count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    # Paginate
    query = query.order_by(Testimonial.display_order, Testimonial.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    testimonials = result.scalars().all()
    
    return PaginatedResponse.create(
        [TestimonialListResponse.model_validate(t) for t in testimonials],
        total, page, page_size
    )



@router.get("/team")
async def get_team_page(db: DatabaseSession):
    """Get team page content."""
    team_result = await db.execute(
        select(TeamMember)
        .where(TeamMember.is_active == True, TeamMember.is_deleted == False)
        .order_by(TeamMember.display_order)
    )
    team = team_result.scalars().all()
    
    leadership = [TeamMemberResponse.model_validate(m) for m in team if m.is_leadership]
    other_members = [TeamMemberResponse.model_validate(m) for m in team if not m.is_leadership]
    
    return {
        "hero": {
            "title": "Our Team",
            "subtitle": "Meet the experts behind Flora Medical",
        },
        "leadership": leadership,
        "team": other_members,
    }


# ============== CONTACT ==============

@router.get("/contact")
async def get_contact_page(db: DatabaseSession):
    """Get contact page content."""
    return {
        "hero": {
            "badge": "We'd Love to Hear From You",
            "title": "Let's Start Your Healing Journey",
            "subtitle": "Whether you need a second opinion, treatment estimate, or travel assistance — our team is ready to help around the clock.",
        },
        "contact_methods": [
            {
                "icon": "phone",
                "title": "Call Us",
                "value": "+91 1800 123 4567",
                "description": "24/7 Patient Helpline",
            },
            {
                "icon": "email",
                "title": "Email Us",
                "value": "hello@floramedical.com",
                "description": "Reply within 2 hours",
            },
            {
                "icon": "headset",
                "title": "Live Support",
                "value": "Chat with us",
                "description": "Available 24/7",
            },
            {
                "icon": "whatsapp",
                "title": "WhatsApp",
                "value": "+91 98765 43210",
                "description": "Instant messaging",
            },
        ],
        "form": {
            "title": "Send a Message",
            "subtitle": "Get a free consultation within 24 hours",
            "fields": [
                {"name": "name", "label": "Full Name", "type": "text", "required": True, "placeholder": "John Doe"},
                {"name": "email", "label": "Email", "type": "email", "required": True, "placeholder": "john@example.com"},
                {"name": "phone", "label": "Phone", "type": "tel", "required": False, "placeholder": "+1 234 567 890"},
                {"name": "country", "label": "Country", "type": "text", "required": False, "placeholder": "United States"},
                {"name": "treatment_interest", "label": "Treatment of Interest", "type": "text", "required": False, "placeholder": "e.g. Knee Replacement, Heart Surgery"},
                {"name": "message", "label": "Message", "type": "textarea", "required": True, "placeholder": "Tell us about your medical needs..."},
            ],
            "submit_text": "Send Message",
            "privacy_note": "By submitting, you agree to our Privacy Policy. We never share your data.",
        },
        "offices": [
            {
                "name": "Ahmedabad",
                "badge": "HQ",
                "address": "SG Highway, Ahmedabad",
                "city_state": "Gujarat 380015",
                "lat": 23.0225,
                "lng": 72.5714,
            },
            {
                "name": "New Delhi",
                "badge": "Branch",
                "address": "Connaught Place",
                "city_state": "New Delhi 110001",
                "lat": 28.6315,
                "lng": 77.2167,
            },
        ],
        "working_hours": {
            "helpline": "24/7",
            "office": "Mon-Sat, 9AM-6PM IST",
        },
    }


# ============== QUOTE REQUEST FORM ==============

@router.get("/quote-form")
async def get_quote_form(db: DatabaseSession):
    """Get quote request form structure (public)."""
    return {
        "form_fields": [
            {
                "name": "country",
                "label": "Your Country",
                "type": "select",
                "required": True,
                "placeholder": "Select your country",
                "options": [
                    "United States", "United Kingdom", "Canada", "Australia",
                    "India", "Nigeria", "Dubai", "Germany", "France", "Other"
                ]
            },
            {
                "name": "medical_condition",
                "label": "Medical Condition",
                "type": "select",
                "required": True,
                "placeholder": "Select condition type",
                "options": [
                    "Orthopedics", "Cardiology", "Neurology", "Oncology", 
                    "Dental", "Ophthalmology", "Gastroenterology", "Urology",
                    "Dermatology", "Rheumatology", "Other"
                ]
            },
            {
                "name": "email",
                "label": "Email Address",
                "type": "email",
                "required": True,
                "placeholder": "your.email@example.com"
            },
            {
                "name": "documents",
                "label": "Upload Medical Documents (Optional)",
                "type": "file",
                "required": False,
                "accept": ".pdf,.jpg,.jpeg,.png",
                "placeholder": "Drag & drop files here or click to browse\nPDF, JPG, PNG up to 10MB"
            }
        ],
        "form_config": {
            "submit_button_text": "Get My Free Quote",
            "submit_endpoint": "/api/v1/pages/quote-form"
        }
    }


@router.post("/quote-form")
async def submit_quote_form(
    country: str = Form(...),
    medical_condition: str = Form(...),
    email: str = Form(...),
    documents: list[UploadFile] = File(default=[]),
    db: DatabaseSession = None
):
    """
    Submit quote form with file uploads (public).
    
    Accepts form data and optionally uploads medical documents.
    """
    from app.models.site import LeadSubmission
    
    try:
        # Create uploads directory if it doesn't exist
        upload_dir = Path("uploads/quote_submissions")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Store file paths
        file_paths = []
        
        # Process uploaded files
        if documents:
            for file in documents:
                # Validate file type
                allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
                file_ext = Path(file.filename).suffix.lower()
                
                if file_ext not in allowed_extensions:
                    return {
                        "success": False,
                        "message": f"File type {file_ext} not allowed. Only PDF, JPG, JPEG, PNG are allowed."
                    }
                
                # Validate file size (10MB max)
                file_size = 0
                content = await file.read()
                file_size = len(content)
                
                if file_size > 10 * 1024 * 1024:  # 10MB
                    return {
                        "success": False,
                        "message": f"File {file.filename} exceeds 10MB limit."
                    }
                
                # Save file with unique name
                import uuid
                unique_filename = f"{uuid.uuid4()}{file_ext}"
                file_path = upload_dir / unique_filename
                
                with open(file_path, "wb") as f:
                    f.write(content)
                
                file_paths.append(str(file_path))
        
        # Create lead submission in database
        lead = LeadSubmission(
            email=email,
            country=country,
            medical_condition=medical_condition,
            documents=file_paths if file_paths else None,
            form_source="quote_form"
        )
        
        db.add(lead)
        await db.commit()
        await db.refresh(lead)
        
        return {
            "success": True,
            "message": "Thank you! We've received your quote request. Our team will contact you within 24 hours.",
            "reference_id": str(lead.id),
            "data": {
                "country": country,
                "medical_condition": medical_condition,
                "email": email,
                "files_uploaded": len(file_paths)
            }
        }
    
    except Exception as e:
        return {
            "success": False,
            "message": f"Error processing form: {str(e)}"
        }


# ============== HOSPITALITY — BEYOND MEDICAL CARE ==============

@router.get("/hospitality")
async def get_hospitality_section(db: DatabaseSession):
    """Get the 'Beyond Medical Care' section for the home page.

    Returns the service grid. Cards come from the DB (hospitality_services table).
    If no rows exist yet, returns the original hardcoded defaults so the frontend
    keeps working while the admin seeds the data.
    """

    mgr = HospitalityServiceManager(db)
    services = await mgr.list_services(active_only=True)

    if services:
        cards = [
            {
                "key": s.key,
                "title": s.title,
                "description": s.description,
                "image_url": s.image_url,
                "icon": s.icon,
                "highlight": s.highlight,
                "url": s.url,
            }
            for s in services
        ]
    else:
        # ── Fallback: hardcoded defaults (used until admin seeds data) ──
        apartment_count = await db.scalar(
            select(func.count()).select_from(
                select(Apartment.id).where(Apartment.is_deleted == False, Apartment.is_available == True).subquery()
            )
        ) or 0
        restaurant_count = await db.scalar(
            select(func.count()).select_from(
                select(Restaurant.id).where(Restaurant.is_deleted == False, Restaurant.is_active == True).subquery()
            )
        ) or 0
        hotel_count = await db.scalar(
            select(func.count()).select_from(
                select(Hotel.id).where(Hotel.is_deleted == False, Hotel.is_active == True).subquery()
            )
        ) or 0
        cards = [
            {"key": "apartments_stays", "title": "Apartments & Stays", "description": "Recovery apartments near top hospitals", "image_url": "/images/hospitality/apartments.jpg", "icon": "building", "highlight": f"{apartment_count + hotel_count}+ Stays", "url": "/hospitality/apartments-stays"},
            {"key": "restaurants_dining", "title": "Restaurants & Dining", "description": "Healthy dining with medical dietary menus", "image_url": "/images/hospitality/restaurants.jpg", "icon": "utensils", "highlight": f"{restaurant_count}+ Partners", "url": "/hospitality/restaurants-dining"},
            {"key": "forex_exchange", "title": "Forex Exchange", "description": "RBI-authorized, best rates, zero hidden fees", "image_url": "/images/hospitality/forex.jpg", "icon": "currency-exchange", "highlight": "30+ Currencies", "url": "/forex"},
            {"key": "airport_pickup", "title": "Airport Pickup & Drop", "description": "24/7 meet-and-greet airport transfers", "image_url": "/images/hospitality/airport.jpg", "icon": "plane-arrival", "highlight": "24/7 Available", "url": "/hospitality/airport-transfer"},
            {"key": "patient_management", "title": "Daily Patient Management", "description": "Dedicated coordinators & recovery tracking", "image_url": "/images/hospitality/patient-care.jpg", "icon": "user-nurse", "highlight": "1:5 Ratio", "url": "/hospitality/patient-management"},
            {"key": "home_made_food", "title": "Home Made Food", "description": "Fresh home-cooked meals for patients", "image_url": "/images/hospitality/homefood.jpg", "icon": "bowl-food", "highlight": "3x Daily", "url": "/hospitality/home-food"},
            {"key": "visa_assistance", "title": "Visa Assistance", "description": "Medical visa processing & extensions", "image_url": "/images/hospitality/visa.jpg", "icon": "passport", "highlight": "98% Approval", "url": "/hospitality/visa-assistance"},
            {"key": "travel_insurance", "title": "Travel Insurance", "description": "Comprehensive medical travel coverage", "image_url": "/images/hospitality/insurance.jpg", "icon": "shield-check", "highlight": "100% Claims", "url": "/hospitality/travel-insurance"},
            {"key": "travel_planning", "title": "Travel Planning", "description": "Flights, itinerary & sightseeing planned", "image_url": "/images/hospitality/travel.jpg", "icon": "map", "highlight": "50+ Countries", "url": "/hospitality/travel-planning"},
        ]

    return {
        "section_tag": "Complete Care Package",
        "title": "Beyond Medical Care",
        "subtitle": "We take care of everything — from comfortable stays to healthy meals, travel, and trusted forex exchange",
        "services": cards,
    }


# ============== HOSPITALITY — DYNAMIC INTERNAL PAGE ==============

@router.get("/hospitality/{slug}")
async def get_hospitality_page(slug: str, db: DatabaseSession):
    """Return the full detail page for a hospitality service.

    Content (hero, stats, features, steps, gallery, testimonials, FAQs)
    is read from the DB.  If the page doesn't exist yet in the DB, a
    hardcoded fallback is returned for *apartments-stays* only.
    """

    mgr = HospitalityServiceManager(db)
    page = await mgr.get_page_by_slug(slug)

    if page:
        # ── Dynamic content from DB ──
        faq_cat = page.faq_category or "general"
        faq_result = await db.execute(
            select(FAQ)
            .where(FAQ.is_active == True, FAQ.is_deleted == False, FAQ.category == faq_cat)
            .order_by(FAQ.display_order)
            .limit(10)
        )
        faqs = faq_result.scalars().all()
        if not faqs:
            faq_result = await db.execute(
                select(FAQ).where(FAQ.is_active == True, FAQ.is_deleted == False).order_by(FAQ.display_order).limit(10)
            )
            faqs = faq_result.scalars().all()

        testimonials_result = await db.execute(
            select(Testimonial)
            .where(Testimonial.is_approved == True, Testimonial.is_deleted == False)
            .order_by(Testimonial.display_order)
            .limit(6)
        )
        testimonials = testimonials_result.scalars().all()

        # Gallery: use page-level images if set, else auto-collect from apartments
        gallery_images = page.gallery_images or []
        if not gallery_images and slug == "apartments-stays":
            all_apt_result = await db.execute(
                select(Apartment.gallery, Apartment.cover_image_url)
                .where(Apartment.is_deleted == False, Apartment.is_available == True)
                .limit(20)
            )
            for row in all_apt_result.all():
                if row.cover_image_url:
                    gallery_images.append(row.cover_image_url)
                if row.gallery:
                    gallery_images.extend(row.gallery[:3])
            gallery_images = gallery_images[:12]

        # Featured apartments (only for apartments-stays page)
        featured_apartments_data = []
        if slug == "apartments-stays":
            featured_result = await db.execute(
                select(Apartment)
                .where(Apartment.is_deleted == False, Apartment.is_available == True, Apartment.is_featured == True)
                .order_by(Apartment.rating.desc().nullslast())
                .limit(6)
            )
            featured_apartments_data = [ApartmentResponse.model_validate(a) for a in featured_result.scalars().all()]

        return {
            "hero": {
                "title": page.hero_title,
                "subtitle": page.hero_subtitle,
                "background_image": page.hero_background_image,
                "breadcrumb": page.hero_breadcrumb or [
                    {"label": "Home", "url": "/"},
                    {"label": page.hero_title, "url": f"/hospitality/{slug}"},
                ],
                "ctas": page.hero_ctas or [],
            },
            "stats": page.stats or [],
            "whats_included": {
                "title": page.features_title or "What's Included",
                "subtitle": page.features_subtitle or "",
                "features": page.features or [],
            },
            "how_it_works": {
                "title": page.steps_title or "How It Works",
                "subtitle": page.steps_subtitle or "",
                "steps": page.steps or [],
            },
            "gallery": {
                "title": page.gallery_title or "Gallery",
                "subtitle": page.gallery_subtitle or "",
                "images": gallery_images,
            },
            "featured_apartments": featured_apartments_data,
            "testimonials": {
                "title": page.testimonials_title or "What Patients Say",
                "subtitle": page.testimonials_subtitle or "",
                "items": [
                    {
                        "id": str(t.id),
                        "patient_name": t.patient_name,
                        "country": t.patient_country,
                        "avatar": t.patient_avatar,
                        "rating": t.rating,
                        "content": t.content,
                        "treatment": t.treatment_name,
                    }
                    for t in testimonials
                ],
            },
            "faqs": {
                "title": page.faq_title or "Frequently Asked Questions",
                "items": [{"question": f.question, "answer": f.answer} for f in faqs],
            },
            "extra_sections": page.extra_sections or {},
            "meta": {
                "title": page.meta_title or page.hero_title,
                "description": page.meta_description or page.hero_subtitle,
            },
        }

    # ── Fallback for apartments-stays (hardcoded) ──
    if slug == "apartments-stays":
        return await _fallback_apartments_stays_page(db)

    raise HTTPException(404, f"Hospitality page '{slug}' not found")


async def _fallback_apartments_stays_page(db: AsyncSession):
    """Hardcoded apartments-stays page — used until admin creates the page in the DB."""

    apartment_count = await db.scalar(
        select(func.count()).select_from(
            select(Apartment.id).where(Apartment.is_deleted == False, Apartment.is_available == True).subquery()
        )
    ) or 0
    hotel_count = await db.scalar(
        select(func.count()).select_from(
            select(Hotel.id).where(Hotel.is_deleted == False, Hotel.is_active == True).subquery()
        )
    ) or 0

    featured_result = await db.execute(
        select(Apartment)
        .where(Apartment.is_deleted == False, Apartment.is_available == True, Apartment.is_featured == True)
        .order_by(Apartment.rating.desc().nullslast())
        .limit(6)
    )
    featured_apartments = featured_result.scalars().all()

    gallery_images = []
    all_apt_result = await db.execute(
        select(Apartment.gallery, Apartment.cover_image_url)
        .where(Apartment.is_deleted == False, Apartment.is_available == True)
        .limit(20)
    )
    for row in all_apt_result.all():
        if row.cover_image_url:
            gallery_images.append(row.cover_image_url)
        if row.gallery:
            gallery_images.extend(row.gallery[:3])
    gallery_images = gallery_images[:12]

    testimonials_result = await db.execute(
        select(Testimonial).where(Testimonial.is_approved == True, Testimonial.is_deleted == False).order_by(Testimonial.display_order).limit(6)
    )
    testimonials = testimonials_result.scalars().all()

    faq_result = await db.execute(
        select(FAQ).where(FAQ.is_active == True, FAQ.is_deleted == False, FAQ.category == "accommodation").order_by(FAQ.display_order).limit(10)
    )
    faqs = faq_result.scalars().all()
    if not faqs:
        faq_result = await db.execute(
            select(FAQ).where(FAQ.is_active == True, FAQ.is_deleted == False).order_by(FAQ.display_order).limit(10)
        )
        faqs = faq_result.scalars().all()

    return {
        "hero": {
            "title": "Apartments & Stays",
            "subtitle": "Choose from our handpicked collection of furnished apartments and recovery stays located near top hospitals, from cooking-capable, daily-grocery-stocked kitchens to patient-friendly, hygiene, safety, and patient-friendly amenities — making your recovery comfortable and stress-free.",
            "background_image": "/images/hospitality/apartments-hero.jpg",
            "breadcrumb": [{"label": "Home", "url": "/"}, {"label": "Apartments & Stays", "url": "/hospitality/apartments-stays"}],
            "ctas": [{"text": "Get Started", "url": "/contact", "variant": "primary"}, {"text": "Contact Us", "url": "/contact", "variant": "secondary"}],
        },
        "stats": [
            {"value": f"{apartment_count + hotel_count}+", "label": "Available Stays"},
            {"value": "10+", "label": "Top Hospitals"},
            {"value": "4.8+", "label": "Avg Rating"},
            {"value": "24/7", "label": "Support"},
        ],
        "whats_included": {
            "title": "What's Included",
            "subtitle": "Everything you need for a comfortable experience",
            "features": [
                {"icon": "hospital", "title": "Near Hospitals", "description": "All stays within 5km of partner hospitals"},
                {"icon": "sofa", "title": "Fully Furnished", "description": "Cozy, fully-furnished with all modern amenities"},
                {"icon": "wifi", "title": "High-Speed WiFi", "description": "Stay connected with fast, reliable internet"},
                {"icon": "utensils", "title": "Kitchen Access", "description": "Cook your own meals or use in-room dining"},
                {"icon": "shield-check", "title": "Verified Properties", "description": "Every stay independently verified for safety and hygiene"},
                {"icon": "users", "title": "Family Friendly", "description": "Spacious options for parents, aids and attendants"},
            ],
        },
        "how_it_works": {
            "title": "How It Works",
            "subtitle": "Simple 4-step process to get started",
            "steps": [
                {"number": 1, "title": "Share Your Requirements", "description": "Tell us your location, dates, and any medical needs"},
                {"number": 2, "title": "Browse Options", "description": "Explore curated apartments near your hospital"},
                {"number": 3, "title": "Book Instantly", "description": "Reserve your stay online with a few clicks and get instant confirmation"},
                {"number": 4, "title": "Move In", "description": "Check in, relax, and focus on your recovery"},
            ],
        },
        "gallery": {"title": "Gallery", "subtitle": "A glimpse of what to expect", "images": gallery_images},
        "featured_apartments": [ApartmentResponse.model_validate(a) for a in featured_apartments],
        "testimonials": {
            "title": "What Patients Say",
            "subtitle": "Real experiences from families who stayed with us",
            "items": [
                {"id": str(t.id), "patient_name": t.patient_name, "country": t.patient_country, "avatar": t.patient_avatar, "rating": t.rating, "content": t.content, "treatment": t.treatment_name}
                for t in testimonials
            ],
        },
        "faqs": {
            "title": "Frequently Asked Questions",
            "items": [{"question": f.question, "answer": f.answer} for f in faqs],
        },
        "extra_sections": {},
        "meta": {"title": "Apartments & Stays", "description": "Recovery apartments near top hospitals"},
    }


# ============== NAVIGATION & SETTINGS ==============

@router.get("/navigation")
async def get_navigation(db: DatabaseSession):
    """Get site navigation structure."""
    return {
        "main_menu": [
            {"label": "Home", "url": "/"},
            {
                "label": "Services",
                "url": "/services",
                "children": [
                    {"label": "All Services", "url": "/services"},
                    {"label": "Find Doctors", "url": "/doctors"},
                    {"label": "Hospitals", "url": "/hospitals"},
                    {"label": "Packages", "url": "/packages"},
                ],
            },
            {
                "label": "Destinations",
                "url": "/destinations",
                "children": [
                    {"label": "Delhi NCR", "url": "/destinations/delhi-ncr"},
                    {"label": "Mumbai", "url": "/destinations/mumbai"},
                    {"label": "Bengaluru", "url": "/destinations/bengaluru"},
                    {"label": "Chennai", "url": "/destinations/chennai"},
                ],
            },
            {
                "label": "Company",
                "url": "/about",
                "children": [
                    {"label": "About Us", "url": "/about"},
                    {"label": "Our Team", "url": "/team"},
                    {"label": "Careers", "url": "/careers"},
                    {"label": "Press", "url": "/press"},
                ],
            },
            {"label": "Blog", "url": "/blog"},
            {
                "label": "Support",
                "url": "/contact",
                "children": [
                    {"label": "Contact Us", "url": "/contact"},
                    {"label": "Help Center", "url": "/help"},
                    {"label": "FAQs", "url": "/faq"},
                ],
            },
        ],
        "footer_menu": {
            "company": [
                {"label": "About", "url": "/about"},
                {"label": "Team", "url": "/team"},
                {"label": "Careers", "url": "/careers"},
                {"label": "Press", "url": "/press"},
            ],
            "services": [
                {"label": "Find Doctors", "url": "/doctors"},
                {"label": "Treatments", "url": "/services"},
                {"label": "Hospitals", "url": "/hospitals"},
                {"label": "Packages", "url": "/packages"},
            ],
            "support": [
                {"label": "Help Center", "url": "/help"},
                {"label": "Contact Us", "url": "/contact"},
                {"label": "FAQs", "url": "/faq"},
                {"label": "Live Chat", "url": "/chat"},
            ],
            "legal": [
                {"label": "Terms of Service", "url": "/terms"},
                {"label": "Privacy Policy", "url": "/privacy"},
                {"label": "Cookie Policy", "url": "/cookies"},
                {"label": "HIPAA Compliance", "url": "/hipaa"},
            ],
        },
        "social_links": {
            "facebook": "https://facebook.com/floramedical",
            "twitter": "https://twitter.com/floramedical",
            "instagram": "https://instagram.com/floramedical",
            "linkedin": "https://linkedin.com/company/floramedical",
        },
    }


@router.get("/settings")
async def get_site_settings(db: DatabaseSession):
    """Get public site settings."""
    return {
        "site_name": "Flora Medical",
        "tagline": "AI-Powered Medical Tourism",
        "logo_url": "/images/logo.svg",
        "favicon_url": "/favicon.ico",
        "contact": {
            "email": "care@floramedical.com",
            "phone": "+1 (888) 123-4567",
            "address": "123 Healthcare Avenue, New Delhi, India 110001",
        },
        "social_links": {
            "facebook": "https://facebook.com/floramedical",
            "twitter": "https://twitter.com/floramedical",
            "instagram": "https://instagram.com/floramedical",
            "linkedin": "https://linkedin.com/company/floramedical",
        },
        "default_currency": "USD",
        "supported_languages": ["en", "ar", "hi"],
    }
