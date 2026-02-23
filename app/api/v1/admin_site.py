"""Admin endpoints for site content management."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.models.site import (
    Destination, Treatment, BlogPost, Testimonial, FAQ, TeamMember, LeadSubmission
)
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.site import (
    DestinationCreate, DestinationUpdate, DestinationListResponse, DestinationResponse,
    TreatmentCreate, TreatmentUpdate, TreatmentListResponse, TreatmentResponse,
    BlogPostCreate, BlogPostUpdate, BlogPostListResponse, BlogPostResponse,
    TestimonialCreate, TestimonialListResponse, TestimonialResponse,
    FAQCreate, FAQUpdate, FAQResponse,
    TeamMemberCreate, TeamMemberUpdate, TeamMemberResponse,
    LeadSubmissionResponse,
)

router = APIRouter()


# ============== DESTINATIONS ADMIN ==============

@router.get("/destinations", response_model=PaginatedResponse[DestinationListResponse], dependencies=[RequireAdmin])
async def admin_list_destinations(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20),
    is_active: Optional[bool] = None,
):
    """List all destinations (admin)."""
    query = select(Destination).where(Destination.is_deleted == False)
    if is_active is not None:
        query = query.where(Destination.is_active == is_active)
    
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    query = query.order_by(Destination.display_order).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    
    return PaginatedResponse.create(result.scalars().all(), total, page, page_size)


@router.post("/destinations", response_model=DestinationResponse, dependencies=[RequireAdmin])
async def create_destination(data: DestinationCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create a destination."""
    destination = Destination(**data.model_dump(), created_by=current_user.id)
    db.add(destination)
    await db.commit()
    await db.refresh(destination)
    return destination


@router.get("/destinations/{destination_id}", response_model=DestinationResponse, dependencies=[RequireAdmin])
async def get_destination(destination_id: UUID, db: DatabaseSession):
    """Get destination by ID."""
    result = await db.execute(select(Destination).where(Destination.id == destination_id))
    destination = result.scalar_one_or_none()
    if not destination:
        raise HTTPException(status_code=404, detail="Destination not found")
    return destination


@router.put("/destinations/{destination_id}", response_model=DestinationResponse, dependencies=[RequireAdmin])
async def update_destination(destination_id: UUID, data: DestinationUpdate, current_user: CurrentUser, db: DatabaseSession):
    """Update destination."""
    result = await db.execute(select(Destination).where(Destination.id == destination_id))
    destination = result.scalar_one_or_none()
    if not destination:
        raise HTTPException(status_code=404, detail="Destination not found")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(destination, field, value)
    destination.updated_by = current_user.id
    await db.commit()
    return destination


@router.delete("/destinations/{destination_id}", dependencies=[RequireAdmin])
async def delete_destination(destination_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Delete destination."""
    result = await db.execute(select(Destination).where(Destination.id == destination_id))
    destination = result.scalar_one_or_none()
    if not destination:
        raise HTTPException(status_code=404, detail="Destination not found")
    destination.soft_delete(current_user.id)
    await db.commit()
    return {"message": "Destination deleted"}


# ============== TREATMENTS ADMIN ==============

@router.get("/treatments", response_model=PaginatedResponse[TreatmentListResponse], dependencies=[RequireAdmin])
async def admin_list_treatments(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20),
    category: Optional[str] = None,
):
    """List all treatments (admin)."""
    query = select(Treatment).where(Treatment.is_deleted == False)
    if category:
        query = query.where(Treatment.category == category)
    
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    query = query.order_by(Treatment.display_order).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    
    return PaginatedResponse.create(result.scalars().all(), total, page, page_size)


@router.post("/treatments", response_model=TreatmentResponse, dependencies=[RequireAdmin])
async def create_treatment(data: TreatmentCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create a treatment."""
    treatment = Treatment(**data.model_dump(), created_by=current_user.id)
    db.add(treatment)
    await db.commit()
    await db.refresh(treatment)
    return treatment


@router.get("/treatments/{treatment_id}", response_model=TreatmentResponse, dependencies=[RequireAdmin])
async def get_treatment(treatment_id: UUID, db: DatabaseSession):
    """Get treatment by ID."""
    result = await db.execute(select(Treatment).where(Treatment.id == treatment_id))
    treatment = result.scalar_one_or_none()
    if not treatment:
        raise HTTPException(status_code=404, detail="Treatment not found")
    return treatment


@router.put("/treatments/{treatment_id}", response_model=TreatmentResponse, dependencies=[RequireAdmin])
async def update_treatment(treatment_id: UUID, data: TreatmentUpdate, current_user: CurrentUser, db: DatabaseSession):
    """Update treatment."""
    result = await db.execute(select(Treatment).where(Treatment.id == treatment_id))
    treatment = result.scalar_one_or_none()
    if not treatment:
        raise HTTPException(status_code=404, detail="Treatment not found")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(treatment, field, value)
    treatment.updated_by = current_user.id
    await db.commit()
    return treatment


@router.delete("/treatments/{treatment_id}", dependencies=[RequireAdmin])
async def delete_treatment(treatment_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Delete treatment."""
    result = await db.execute(select(Treatment).where(Treatment.id == treatment_id))
    treatment = result.scalar_one_or_none()
    if not treatment:
        raise HTTPException(status_code=404, detail="Treatment not found")
    treatment.soft_delete(current_user.id)
    await db.commit()
    return {"message": "Treatment deleted"}


@router.post("/services", response_model=TreatmentResponse, dependencies=[RequireAdmin])
async def create_service(data: TreatmentCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create a service (alias for treatment)."""
    # Reuse treatment logic as Service = Treatment in this system
    treatment_data = data.model_dump()
    if treatment_data.get("gallery") is None:
        treatment_data["gallery"] = []
    if treatment_data.get("procedures") is None:
        treatment_data["procedures"] = []
        
    treatment = Treatment(**treatment_data, created_by=current_user.id)
    db.add(treatment)
    await db.commit()
    await db.refresh(treatment)
    return treatment


# ============== BLOG ADMIN ==============

@router.get("/blog", response_model=PaginatedResponse[BlogPostListResponse], dependencies=[RequireAdmin])
async def admin_list_blog_posts(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20),
    status: Optional[str] = None,
):
    """List all blog posts (admin)."""
    query = select(BlogPost).options(selectinload(BlogPost.author)).where(BlogPost.is_deleted == False)
    if status:
        query = query.where(BlogPost.status == status)
    
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    query = query.order_by(BlogPost.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    
    return PaginatedResponse.create(result.scalars().all(), total, page, page_size)


@router.post("/blog", response_model=BlogPostResponse, dependencies=[RequireAdmin])
async def create_blog_post(data: BlogPostCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create a blog post."""
    from datetime import datetime, timezone
    
    post = BlogPost(**data.model_dump(), author_id=current_user.id, created_by=current_user.id)
    if data.status == "published":
        post.published_at = datetime.now(timezone.utc)
    db.add(post)
    await db.commit()
    await db.refresh(post)
    
    # Explicitly load the author relationship for the response
    from app.models.user import User
    author_result = await db.execute(select(User).where(User.id == current_user.id))
    post.author = author_result.scalar_one_or_none()
    
    return post


@router.get("/blog/{post_id}", response_model=BlogPostResponse, dependencies=[RequireAdmin])
async def get_blog_post(post_id: UUID, db: DatabaseSession):
    """Get blog post by ID."""
    result = await db.execute(select(BlogPost).options(selectinload(BlogPost.author)).where(BlogPost.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    return post


@router.put("/blog/{post_id}", response_model=BlogPostResponse, dependencies=[RequireAdmin])
async def update_blog_post(post_id: UUID, data: BlogPostUpdate, current_user: CurrentUser, db: DatabaseSession):
    """Update blog post."""
    from datetime import datetime, timezone
    
    result = await db.execute(select(BlogPost).options(selectinload(BlogPost.author)).where(BlogPost.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(post, field, value)
    
    if data.status == "published" and not post.published_at:
        post.published_at = datetime.now(timezone.utc)
    
    post.updated_by = current_user.id
    await db.commit()
    return post


@router.delete("/blog/{post_id}", dependencies=[RequireAdmin])
async def delete_blog_post(post_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Delete blog post."""
    result = await db.execute(select(BlogPost).where(BlogPost.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    post.soft_delete(current_user.id)
    await db.commit()
    return {"message": "Blog post deleted"}


# ============== TESTIMONIALS ADMIN ==============

@router.get("/testimonials", response_model=PaginatedResponse[TestimonialListResponse], dependencies=[RequireAdmin])
async def admin_list_testimonials(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20),
    is_approved: Optional[bool] = None,
):
    """List all testimonials (admin)."""
    query = select(Testimonial).where(Testimonial.is_deleted == False)
    if is_approved is not None:
        query = query.where(Testimonial.is_approved == is_approved)
    
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    query = query.order_by(Testimonial.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    
    return PaginatedResponse.create(result.scalars().all(), total, page, page_size)


@router.post("/testimonials", response_model=TestimonialResponse, dependencies=[RequireAdmin])
async def create_testimonial(data: TestimonialCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create a testimonial."""
    testimonial = Testimonial(**data.model_dump(), created_by=current_user.id)
    db.add(testimonial)
    await db.commit()
    await db.refresh(testimonial)
    return testimonial


@router.put("/testimonials/{testimonial_id}/approve", dependencies=[RequireAdmin])
async def approve_testimonial(testimonial_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Approve a testimonial."""
    result = await db.execute(select(Testimonial).where(Testimonial.id == testimonial_id))
    testimonial = result.scalar_one_or_none()
    if not testimonial:
        raise HTTPException(status_code=404, detail="Testimonial not found")
    testimonial.is_approved = True
    testimonial.updated_by = current_user.id
    await db.commit()
    return {"message": "Testimonial approved"}


@router.delete("/testimonials/{testimonial_id}", dependencies=[RequireAdmin])
async def delete_testimonial(testimonial_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Delete testimonial."""
    result = await db.execute(select(Testimonial).where(Testimonial.id == testimonial_id))
    testimonial = result.scalar_one_or_none()
    if not testimonial:
        raise HTTPException(status_code=404, detail="Testimonial not found")
    testimonial.soft_delete(current_user.id)
    await db.commit()
    return {"message": "Testimonial deleted"}


# ============== FAQ ADMIN ==============

@router.get("/faqs", response_model=PaginatedResponse[FAQResponse], dependencies=[RequireAdmin])
async def admin_list_faqs(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(50),
    category: Optional[str] = None,
):
    """List all FAQs (admin)."""
    query = select(FAQ).where(FAQ.is_deleted == False)
    if category:
        query = query.where(FAQ.category == category)
    
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    query = query.order_by(FAQ.category, FAQ.display_order).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    
    return PaginatedResponse.create(result.scalars().all(), total, page, page_size)


@router.post("/faqs", response_model=FAQResponse, dependencies=[RequireAdmin])
async def create_faq(data: FAQCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create a FAQ."""
    faq = FAQ(**data.model_dump(), created_by=current_user.id)
    db.add(faq)
    await db.commit()
    await db.refresh(faq)
    return faq


@router.put("/faqs/{faq_id}", response_model=FAQResponse, dependencies=[RequireAdmin])
async def update_faq(faq_id: UUID, data: FAQUpdate, current_user: CurrentUser, db: DatabaseSession):
    """Update FAQ."""
    result = await db.execute(select(FAQ).where(FAQ.id == faq_id))
    faq = result.scalar_one_or_none()
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(faq, field, value)
    faq.updated_by = current_user.id
    await db.commit()
    return faq


@router.delete("/faqs/{faq_id}", dependencies=[RequireAdmin])
async def delete_faq(faq_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Delete FAQ."""
    result = await db.execute(select(FAQ).where(FAQ.id == faq_id))
    faq = result.scalar_one_or_none()
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    faq.soft_delete(current_user.id)
    await db.commit()
    return {"message": "FAQ deleted"}


# ============== TEAM ADMIN ==============

@router.get("/team", response_model=List[TeamMemberResponse], dependencies=[RequireAdmin])
async def admin_list_team(db: DatabaseSession):
    """List all team members (admin)."""
    result = await db.execute(
        select(TeamMember).where(TeamMember.is_deleted == False).order_by(TeamMember.display_order)
    )
    return result.scalars().all()


@router.post("/team", response_model=TeamMemberResponse, dependencies=[RequireAdmin])
async def create_team_member(data: TeamMemberCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create team member."""
    member = TeamMember(**data.model_dump(), created_by=current_user.id)
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


@router.put("/team/{member_id}", response_model=TeamMemberResponse, dependencies=[RequireAdmin])
async def update_team_member(member_id: UUID, data: TeamMemberUpdate, current_user: CurrentUser, db: DatabaseSession):
    """Update team member."""
    result = await db.execute(select(TeamMember).where(TeamMember.id == member_id))
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(member, field, value)
    member.updated_by = current_user.id
    await db.commit()
    return member


@router.delete("/team/{member_id}", dependencies=[RequireAdmin])
async def delete_team_member(member_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Delete team member."""
    result = await db.execute(select(TeamMember).where(TeamMember.id == member_id))
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    member.soft_delete(current_user.id)
    await db.commit()
    return {"message": "Team member deleted"}


# ============== LEADS ADMIN ==============

@router.get("/leads", response_model=PaginatedResponse[LeadSubmissionResponse], dependencies=[RequireAdmin])
async def admin_list_leads(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20),
    status: Optional[str] = None,
):
    """List all lead submissions (admin)."""
    query = select(LeadSubmission).where(LeadSubmission.is_deleted == False)
    if status:
        query = query.where(LeadSubmission.status == status)
    
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    query = query.order_by(LeadSubmission.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    
    return PaginatedResponse.create(result.scalars().all(), total, page, page_size)


# ============== QUOTES ADMIN ==============

@router.get("/quotes", response_model=PaginatedResponse[LeadSubmissionResponse], dependencies=[RequireAdmin])
async def admin_list_quotes(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20),
    status: Optional[str] = None,
    country: Optional[str] = None,
    medical_condition: Optional[str] = None,
    sort_by: Optional[str] = Query("created_at", regex="^(created_at|name|email|country)$"),
):
    """
    List all quote submissions with filtering (admin).
    
    Filter options:
    - status: new, contacted, qualified, converted
    - country: Filter by country
    - medical_condition: Filter by medical condition
    - sort_by: created_at, name, email, country
    """
    query = select(LeadSubmission).where(
        LeadSubmission.is_deleted == False,
        LeadSubmission.form_source == "quote_form"
    )
    
    # Apply filters
    if status:
        query = query.where(LeadSubmission.status == status)
    
    if country:
        query = query.where(LeadSubmission.country.ilike(f"%{country}%"))
    
    if medical_condition:
        query = query.where(LeadSubmission.medical_condition.ilike(f"%{medical_condition}%"))
    
    # Count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    # Sort
    if sort_by == "name":
        query = query.order_by(LeadSubmission.name)
    elif sort_by == "email":
        query = query.order_by(LeadSubmission.email)
    elif sort_by == "country":
        query = query.order_by(LeadSubmission.country)
    else:
        query = query.order_by(LeadSubmission.created_at.desc())
    
    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    
    return PaginatedResponse.create(result.scalars().all(), total, page, page_size)


@router.get("/quotes/{quote_id}", dependencies=[RequireAdmin])
async def get_quote_detail(quote_id: UUID, db: DatabaseSession):
    """Get detailed quote submission with attached documents."""
    result = await db.execute(
        select(LeadSubmission).where(
            LeadSubmission.id == quote_id,
            LeadSubmission.form_source == "quote_form"
        )
    )
    quote = result.scalar_one_or_none()
    
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    return {
        "id": quote.id,
        "email": quote.email,
        "phone": quote.phone,
        "name": quote.name,
        "country": quote.country,
        "medical_condition": quote.medical_condition,
        "treatment_interest": quote.treatment_interest,
        "message": quote.message,
        "documents": quote.documents,
        "status": quote.status,
        "form_source": quote.form_source,
        "assigned_to": quote.assigned_to,
        "notes": quote.notes,
        "utm_source": quote.utm_source,
        "utm_medium": quote.utm_medium,
        "utm_campaign": quote.utm_campaign,
        "created_at": quote.created_at,
        "updated_at": quote.updated_at,
    }


@router.put("/quotes/{quote_id}/status", dependencies=[RequireAdmin])
async def update_quote_status(
    quote_id: UUID,
    status: str = Query(..., regex="^(new|contacted|qualified|converted)$"),
    current_user: CurrentUser = None,
    db: DatabaseSession = None
):
    """
    Update quote status.
    
    Status options: new, contacted, qualified, converted
    """
    result = await db.execute(
        select(LeadSubmission).where(
            LeadSubmission.id == quote_id,
            LeadSubmission.form_source == "quote_form"
        )
    )
    quote = result.scalar_one_or_none()
    
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    quote.status = status
    quote.updated_by = current_user.id
    await db.commit()
    
    return {
        "success": True,
        "message": f"Quote status updated to {status}",
        "quote_id": str(quote.id),
        "new_status": status
    }


@router.put("/quotes/{quote_id}/assign", dependencies=[RequireAdmin])
async def assign_quote(
    quote_id: UUID,
    assigned_to: UUID = Query(...),
    current_user: CurrentUser = None,
    db: DatabaseSession = None
):
    """Assign quote to a team member."""
    result = await db.execute(
        select(LeadSubmission).where(
            LeadSubmission.id == quote_id,
            LeadSubmission.form_source == "quote_form"
        )
    )
    quote = result.scalar_one_or_none()
    
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    quote.assigned_to = assigned_to
    quote.updated_by = current_user.id
    await db.commit()
    
    return {
        "success": True,
        "message": "Quote assigned successfully",
        "quote_id": str(quote.id),
        "assigned_to": str(assigned_to)
    }


@router.put("/quotes/{quote_id}/notes", dependencies=[RequireAdmin])
async def update_quote_notes(
    quote_id: UUID,
    notes: str = Query(...),
    current_user: CurrentUser = None,
    db: DatabaseSession = None
):
    """Add/update notes on quote."""
    result = await db.execute(
        select(LeadSubmission).where(
            LeadSubmission.id == quote_id,
            LeadSubmission.form_source == "quote_form"
        )
    )
    quote = result.scalar_one_or_none()
    
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    quote.notes = notes
    quote.updated_by = current_user.id
    await db.commit()
    
    return {
        "success": True,
        "message": "Notes updated successfully",
        "quote_id": str(quote.id),
        "notes": notes
    }


@router.get("/quotes/stats/summary", dependencies=[RequireAdmin])
async def get_quotes_stats(db: DatabaseSession):
    """Get quote statistics dashboard."""
    total_result = await db.execute(
        select(func.count(LeadSubmission.id)).where(
            LeadSubmission.form_source == "quote_form",
            LeadSubmission.is_deleted == False
        )
    )
    total = total_result.scalar() or 0
    
    new_result = await db.execute(
        select(func.count(LeadSubmission.id)).where(
            LeadSubmission.form_source == "quote_form",
            LeadSubmission.status == "new",
            LeadSubmission.is_deleted == False
        )
    )
    new_count = new_result.scalar() or 0
    
    contacted_result = await db.execute(
        select(func.count(LeadSubmission.id)).where(
            LeadSubmission.form_source == "quote_form",
            LeadSubmission.status == "contacted",
            LeadSubmission.is_deleted == False
        )
    )
    contacted_count = contacted_result.scalar() or 0
    
    qualified_result = await db.execute(
        select(func.count(LeadSubmission.id)).where(
            LeadSubmission.form_source == "quote_form",
            LeadSubmission.status == "qualified",
            LeadSubmission.is_deleted == False
        )
    )
    qualified_count = qualified_result.scalar() or 0
    
    converted_result = await db.execute(
        select(func.count(LeadSubmission.id)).where(
            LeadSubmission.form_source == "quote_form",
            LeadSubmission.status == "converted",
            LeadSubmission.is_deleted == False
        )
    )
    converted_count = converted_result.scalar() or 0
    
    return {
        "total_quotes": total,
        "new": new_count,
        "contacted": contacted_count,
        "qualified": qualified_count,
        "converted": converted_count,
        "conversion_rate": f"{(converted_count / total * 100) if total > 0 else 0:.1f}%"
    }


@router.put("/leads/{lead_id}/status", dependencies=[RequireAdmin])
async def update_lead_status(lead_id: UUID, status: str, current_user: CurrentUser, db: DatabaseSession):
    """Update lead status."""
    result = await db.execute(select(LeadSubmission).where(LeadSubmission.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead.status = status
    lead.updated_by = current_user.id
    await db.commit()
    return {"message": "Lead status updated"}
