"""Admin endpoints for site content management."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin
from app.models.site import (
    Destination, Treatment, BlogPost, BlogComment, Testimonial, FAQ, TeamMember, LeadSubmission, HeroSlider
)
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.site import (
    DestinationCreate, DestinationUpdate, DestinationListResponse, DestinationResponse,
    TreatmentCreate, TreatmentUpdate, TreatmentListResponse, TreatmentResponse,
    BlogPostCreate, BlogPostUpdate, BlogPostListResponse, BlogPostResponse,
    BlogCommentCreate, BlogCommentUpdate, BlogCommentResponse,
    TestimonialCreate, TestimonialListResponse, TestimonialResponse, TestimonialUpdate,
    FAQCreate, FAQUpdate, FAQResponse,
    TeamMemberCreate, TeamMemberUpdate, TeamMemberResponse,
    LeadSubmissionResponse,
    HeroSliderCreate, HeroSliderUpdate, HeroSliderResponse, HeroSliderReorder,
)
from app.services.blog_comment_service import BlogCommentService

router = APIRouter()


# ============== HERO SLIDERS ADMIN ==============

@router.get("/hero-sliders", response_model=List[HeroSliderResponse])
async def admin_list_hero_sliders(db: DatabaseSession, is_active: Optional[bool] = None):
    """List all hero slides (admin)."""
    query = select(HeroSlider).where(HeroSlider.is_deleted == False)
    if is_active is not None:
        query = query.where(HeroSlider.is_active == is_active)
    
    query = query.order_by(HeroSlider.display_order)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/hero-sliders", response_model=HeroSliderResponse, dependencies=[RequireAdmin], status_code=201)
async def create_hero_slider(data: HeroSliderCreate, current_user: CurrentUser, db: DatabaseSession):
    """Create a new hero slide."""
    slider = HeroSlider(**data.model_dump(), created_by=current_user.id)
    db.add(slider)
    await db.commit()
    await db.refresh(slider)
    return slider


@router.get("/hero-sliders/{slider_id}", response_model=HeroSliderResponse, dependencies=[RequireAdmin])
async def get_hero_slider(slider_id: UUID, db: DatabaseSession):
    """Get hero slide by ID."""
    result = await db.execute(select(HeroSlider).where(HeroSlider.id == slider_id))
    slider = result.scalar_one_or_none()
    if not slider:
        raise HTTPException(status_code=404, detail="Hero slider not found")
    return slider


@router.put("/hero-sliders/{slider_id}", response_model=HeroSliderResponse, dependencies=[RequireAdmin])
async def update_hero_slider(slider_id: UUID, data: HeroSliderUpdate, current_user: CurrentUser, db: DatabaseSession):
    """Update a hero slide."""
    result = await db.execute(select(HeroSlider).where(HeroSlider.id == slider_id))
    slider = result.scalar_one_or_none()
    if not slider:
        raise HTTPException(status_code=404, detail="Hero slider not found")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(slider, field, value)
    slider.updated_by = current_user.id
    await db.commit()
    return slider


@router.put("/hero-sliders/{slider_id}/toggle", response_model=HeroSliderResponse, dependencies=[RequireAdmin])
async def toggle_hero_slider_active(slider_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Toggle the active status of a hero slide."""
    result = await db.execute(select(HeroSlider).where(HeroSlider.id == slider_id))
    slider = result.scalar_one_or_none()
    if not slider:
        raise HTTPException(status_code=404, detail="Hero slider not found")
    
    slider.is_active = not slider.is_active
    slider.updated_by = current_user.id
    await db.commit()
    return slider


@router.post("/hero-sliders/reorder", dependencies=[RequireAdmin])
async def reorder_hero_sliders(data: List[HeroSliderReorder], current_user: CurrentUser, db: DatabaseSession):
    """Reorder hero slides."""
    for item in data:
        result = await db.execute(select(HeroSlider).where(HeroSlider.id == item.id))
        slider = result.scalar_one_or_none()
        if slider:
            slider.display_order = item.display_order
            slider.updated_by = current_user.id
    await db.commit()
    return {"message": "Sliders reordered successfully"}


@router.delete("/hero-sliders/{slider_id}", dependencies=[RequireAdmin])
async def delete_hero_slider(slider_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Soft-delete a hero slide."""
    result = await db.execute(select(HeroSlider).where(HeroSlider.id == slider_id))
    slider = result.scalar_one_or_none()
    if not slider:
        raise HTTPException(status_code=404, detail="Hero slider not found")
    slider.soft_delete(current_user.id)
    await db.commit()
    return {"message": "Hero slider deleted"}


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


@router.get("/services", response_model=PaginatedResponse[TreatmentListResponse], dependencies=[RequireAdmin])
async def admin_list_services(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
):
    """List all services (admin)."""
    query = select(Treatment).where(Treatment.is_deleted == False)
    if category:
        query = query.where(Treatment.category == category)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    query = query.order_by(Treatment.display_order).offset((page - 1) * page_size).limit(page_size)
    rows = await db.execute(query)
    return PaginatedResponse.create(list(rows.scalars().all()), total, page, page_size)


@router.get("/services/{service_id}", response_model=TreatmentResponse, dependencies=[RequireAdmin])
async def get_service(service_id: UUID, db: DatabaseSession):
    """Get service by ID."""
    result = await db.execute(select(Treatment).where(Treatment.id == service_id, Treatment.is_deleted == False))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


@router.put("/services/{service_id}", response_model=TreatmentResponse, dependencies=[RequireAdmin])
async def update_service(service_id: UUID, data: TreatmentUpdate, current_user: CurrentUser, db: DatabaseSession):
    """Update a service."""
    result = await db.execute(select(Treatment).where(Treatment.id == service_id, Treatment.is_deleted == False))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(service, field, value)
    service.updated_by = current_user.id
    await db.commit()
    return service


@router.delete("/services/{service_id}", status_code=204, dependencies=[RequireAdmin])
async def delete_service(service_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Soft-delete a service."""
    result = await db.execute(select(Treatment).where(Treatment.id == service_id, Treatment.is_deleted == False))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    service.is_deleted = True
    service.deleted_by = current_user.id
    service.deleted_at = func.now()
    await db.commit()


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


# ============== BLOG COMMENTS ADMIN ==============

@router.get("/blog/{post_id}/comments", response_model=PaginatedResponse[BlogCommentResponse], dependencies=[RequireAdmin])
async def admin_list_blog_comments(
    post_id: UUID,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_approved: Optional[bool] = None,
):
    """List all comments for a blog post (approved + pending). Admin only."""
    service = BlogCommentService(db)
    comments, total = await service.get_all_for_post(post_id, page=page, page_size=page_size)
    if is_approved is not None:
        comments = [c for c in comments if c.is_approved == is_approved]
    return {
        "items": comments,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size else 1,
    }


@router.post("/blog/comments/{comment_id}/approve", response_model=BlogCommentResponse, dependencies=[RequireAdmin])
async def approve_blog_comment(comment_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Approve a pending blog comment."""
    service = BlogCommentService(db)
    comment = await service.get_by_id(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    return await service.approve(comment, updated_by=current_user.id)


@router.post("/blog/comments/{comment_id}/unapprove", response_model=BlogCommentResponse, dependencies=[RequireAdmin])
async def unapprove_blog_comment(comment_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Remove approval from a blog comment (puts it back to pending)."""
    service = BlogCommentService(db)
    comment = await service.get_by_id(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    return await service.unapprove(comment, updated_by=current_user.id)


@router.put("/blog/comments/{comment_id}", response_model=BlogCommentResponse, dependencies=[RequireAdmin])
async def update_blog_comment(comment_id: UUID, data: BlogCommentUpdate, current_user: CurrentUser, db: DatabaseSession):
    """Edit comment content (admin moderation)."""
    service = BlogCommentService(db)
    comment = await service.get_by_id(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    return await service.update(comment, data, updated_by=current_user.id)


@router.delete("/blog/comments/{comment_id}", dependencies=[RequireAdmin])
async def delete_blog_comment(comment_id: UUID, current_user: CurrentUser, db: DatabaseSession):
    """Soft-delete a blog comment."""
    service = BlogCommentService(db)
    comment = await service.get_by_id(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    await service.delete(comment, deleted_by=current_user.id)
    return {"message": "Comment deleted"}




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
async def create_testimonial(
    current_user: CurrentUser,
    db: DatabaseSession,
    patient_name: str = Form(...),
    patient_country: Optional[str] = Form(None),
    treatment_name: Optional[str] = Form(None),
    hospital_name: Optional[str] = Form(None),
    rating: int = Form(default=5, ge=1, le=5),
    title: Optional[str] = Form(None),
    content: str = Form(...),
    video_url: Optional[str] = Form(None),
    video_thumbnail: Optional[str] = Form(None),
    video_duration: Optional[str] = Form(None),
    is_verified: bool = Form(False),
    is_featured: bool = Form(False),
    patient_avatar: Optional[UploadFile] = File(None),
):
    """Create a testimonial. patient_avatar must be an image file (JPEG, PNG, WebP) under 2MB."""
    import os, shutil
    from pathlib import Path

    avatar_path: Optional[str] = None

    if patient_avatar:
        # Validate content type
        allowed_types = {"image/jpeg", "image/png", "image/webp"}
        if patient_avatar.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="patient_avatar must be a JPEG, PNG, or WebP image.")
        # Validate file size (max 2 MB)
        contents = await patient_avatar.read()
        if len(contents) > 2 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="patient_avatar must not exceed 2 MB.")
        # Save file
        upload_dir = Path("uploads/testimonials")
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_ext = patient_avatar.filename.rsplit(".", 1)[-1] if "." in patient_avatar.filename else "jpg"
        import uuid as _uuid
        filename = f"{_uuid.uuid4()}.{file_ext}"
        file_path = upload_dir / filename
        with open(file_path, "wb") as f:
            f.write(contents)
        avatar_path = f"/static/{file_path}"

    testimonial = Testimonial(
        patient_name=patient_name,
        patient_country=patient_country,
        patient_avatar=avatar_path,
        treatment_name=treatment_name,
        hospital_name=hospital_name,
        rating=rating,
        title=title,
        content=content,
        video_url=video_url,
        video_thumbnail=video_thumbnail,
        video_duration=video_duration,
        is_verified=is_verified,
        is_featured=is_featured,
        created_by=current_user.id,
    )
    db.add(testimonial)
    await db.commit()
    await db.refresh(testimonial)
    return testimonial


@router.put("/testimonials/{testimonial_id}", response_model=TestimonialResponse, dependencies=[RequireAdmin])
async def update_testimonial(
    testimonial_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
    patient_name: Optional[str] = Form(None),
    patient_country: Optional[str] = Form(None),
    treatment_name: Optional[str] = Form(None),
    hospital_name: Optional[str] = Form(None),
    rating: Optional[int] = Form(None),
    title: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    video_url: Optional[str] = Form(None),
    video_thumbnail: Optional[str] = Form(None),
    video_duration: Optional[str] = Form(None),
    is_verified: Optional[bool] = Form(None),
    is_featured: Optional[bool] = Form(None),
    is_approved: Optional[bool] = Form(None),
    patient_avatar: Optional[UploadFile] = File(None),
):
    """Update a testimonial. patient_avatar must be an image file (JPEG, PNG, WebP) under 2MB."""
    import os
    from pathlib import Path

    result = await db.execute(select(Testimonial).where(Testimonial.id == testimonial_id))
    testimonial = result.scalar_one_or_none()
    if not testimonial:
        raise HTTPException(status_code=404, detail="Testimonial not found")

    # Apply text field updates
    if patient_name is not None:
        testimonial.patient_name = patient_name
    if patient_country is not None:
        testimonial.patient_country = patient_country
    if treatment_name is not None:
        testimonial.treatment_name = treatment_name
    if hospital_name is not None:
        testimonial.hospital_name = hospital_name
    if rating is not None:
        testimonial.rating = rating
    if title is not None:
        testimonial.title = title
    if content is not None:
        testimonial.content = content
    if video_url is not None:
        testimonial.video_url = video_url
    if video_thumbnail is not None:
        testimonial.video_thumbnail = video_thumbnail
    if video_duration is not None:
        testimonial.video_duration = video_duration
    if is_verified is not None:
        testimonial.is_verified = is_verified
    if is_featured is not None:
        testimonial.is_featured = is_featured
    if is_approved is not None:
        testimonial.is_approved = is_approved

    # Handle new image upload
    if patient_avatar and patient_avatar.filename:
        allowed_types = {"image/jpeg", "image/png", "image/webp"}
        if patient_avatar.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="patient_avatar must be a JPEG, PNG, or WebP image.")
        contents = await patient_avatar.read()
        if len(contents) > 2 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="patient_avatar must not exceed 2 MB.")
        # Remove old file if it exists
        if testimonial.patient_avatar:
            old_path = testimonial.patient_avatar[8:] if testimonial.patient_avatar.startswith("/static/") else testimonial.patient_avatar
            if os.path.exists(old_path):
                os.remove(old_path)
        upload_dir = Path("uploads/testimonials")
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_ext = patient_avatar.filename.rsplit(".", 1)[-1] if "." in patient_avatar.filename else "jpg"
        import uuid as _uuid
        filename = f"{_uuid.uuid4()}.{file_ext}"
        file_path = upload_dir / filename
        with open(file_path, "wb") as f:
            f.write(contents)
        testimonial.patient_avatar = f"/static/{file_path}"

    testimonial.updated_by = current_user.id
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
    sort_by: Optional[str] = Query("created_at", pattern="^(created_at|name|email|country)$"),
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
    status: str = Query(..., pattern="^(new|contacted|qualified|converted)$"),
    current_user: CurrentUser = ...,
    db: DatabaseSession = ...
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
    current_user: CurrentUser = ...,
    db: DatabaseSession = ...
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
    current_user: CurrentUser = ...,
    db: DatabaseSession = ...
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
