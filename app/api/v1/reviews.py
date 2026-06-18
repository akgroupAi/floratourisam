"""Reviews & Ratings API router.

Mount layout (registered under /reviews in api_router.py):

  Patient (authenticated):
    POST   /reviews                        — submit a review
    GET    /reviews/me                     — list own reviews
    PUT    /reviews/{review_id}            — edit own (pending) review
    DELETE /reviews/{review_id}            — soft-delete own review
    POST   /reviews/{review_id}/helpful    — mark helpful / unhelpful

  Public (no auth):
    GET    /reviews/{entity_type}/{entity_id}           — list approved reviews
    GET    /reviews/{entity_type}/{entity_id}/summary   — aggregate stats

  Admin (RequireAdmin):
    GET    /reviews/admin/all                           — all reviews, every entity (filterable)
    GET    /admin/reviews                              — all reviews (filterable)
    PUT    /admin/reviews/{review_id}/approve          — approve or reject
    POST   /admin/reviews/{review_id}/respond          — official response
    PUT    /admin/reviews/{review_id}/feature          — pin / unpin
    DELETE /admin/reviews/{review_id}                  — hard-delete
"""

from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser, DatabaseSession, RequireAdmin, RequirePatient
from app.schemas.common import PaginatedResponse
from app.schemas.review import (
    AdminReviewApprove,
    AdminReviewResponse,
    AllReviewsPaginatedResponse,
    EntityType,
    ReviewCreate,
    ReviewHelpfulRequest,
    ReviewListItem,
    ReviewPaginatedResponse,
    ReviewPublicResponse,
    ReviewResponse,
    ReviewSummary,
    ReviewUpdate,
)
from app.services.review_service import ReviewService

router = APIRouter()


# ---------------------------------------------------------------------------
# Patient endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[RequirePatient],
    summary="Submit a review",
    description=(
        "Submit a star rating + review text for a doctor, hospital, hotel, "
        "apartment, or restaurant.\n\n"
        "**Validation rules:**\n"
        "- Rating must be 1–5\n"
        "- Body text min 10 characters if provided\n"
        "- One review per entity per patient\n"
        "- Review goes to admin moderation before appearing publicly\n"
        "- `is_verified` is set automatically if a completed booking/consultation is found"
    ),
)
async def submit_review(
    data: ReviewCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = ReviewService(db)
    try:
        return await service.submit_review(current_user.id, data, current_user.id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/me",
    response_model=PaginatedResponse[ReviewListItem],
    dependencies=[RequirePatient],
    summary="My submitted reviews",
)
async def list_my_reviews(
    current_user: CurrentUser,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    service = ReviewService(db)
    reviews, total = await service.list_mine(current_user.id, page, page_size)
    return PaginatedResponse.create(reviews, total, page, page_size)


@router.put(
    "/{review_id}",
    response_model=ReviewResponse,
    dependencies=[RequirePatient],
    summary="Edit own review",
    description="Only allowed while the review is still pending admin approval.",
)
async def update_review(
    review_id: UUID,
    data: ReviewUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = ReviewService(db)
    try:
        return await service.update_review(review_id, current_user.id, data, current_user.id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete(
    "/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[RequirePatient],
    summary="Delete own review",
)
async def delete_review(
    review_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = ReviewService(db)
    try:
        await service.delete_review(review_id, current_user.id, current_user.id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/{review_id}/helpful",
    response_model=ReviewResponse,
    summary="Mark a review as helpful",
    description="Any authenticated user can mark a published review as helpful or unmark it.",
)
async def mark_helpful(
    review_id: UUID,
    data: ReviewHelpfulRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = ReviewService(db)
    try:
        return await service.mark_helpful(review_id, data.helpful)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# Public endpoints (no auth)
# ---------------------------------------------------------------------------


@router.get(
    "/{entity_type}/{entity_id}/summary",
    response_model=ReviewSummary,
    summary="Review summary for an entity",
    description="Returns average rating, star breakdown, and counts. No auth required.",
)
async def get_review_summary(
    entity_type: EntityType,
    entity_id: UUID,
    db: DatabaseSession,
):
    service = ReviewService(db)
    return await service.get_entity_summary(entity_type, entity_id)


@router.get(
    "/{entity_type}/{entity_id}",
    response_model=ReviewPaginatedResponse,
    summary="List approved reviews for an entity",
    description=(
        "Returns paginated published reviews. Supports filtering by verified-only "
        "and minimum star rating."
    ),
)
async def list_entity_reviews(
    entity_type: EntityType,
    entity_id: UUID,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    verified_only: bool = Query(False, description="Only show verified purchases"),
    min_rating: Optional[int] = Query(None, ge=1, le=5, description="Minimum star rating"),
    sort_by: Literal["created_at", "rating", "helpful_count"] = Query("created_at"),
):
    service = ReviewService(db)
    reviews, total, average_rating = await service.list_for_entity(
        entity_type=entity_type,
        entity_id=entity_id,
        page=page,
        page_size=page_size,
        verified_only=verified_only,
        min_rating=min_rating,
        sort_by=sort_by,
    )
    return ReviewPaginatedResponse.create(reviews, total, page, page_size, average_rating)


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/admin",
    response_model=PaginatedResponse[ReviewResponse],
    dependencies=[RequireAdmin],
    summary="[Admin] List all reviews",
    description="Full review queue with moderation filters.",
)
async def admin_list_reviews(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    entity_type: Optional[EntityType] = Query(None),
    is_approved: Optional[bool] = Query(None, description="True=approved, False=pending/rejected"),
    is_verified: Optional[bool] = Query(None),
    min_rating: Optional[int] = Query(None, ge=1, le=5),
):
    service = ReviewService(db)
    reviews, total = await service.admin_list(
        page=page,
        page_size=page_size,
        entity_type=entity_type,
        is_approved=is_approved,
        is_verified=is_verified,
        min_rating=min_rating,
    )
    return PaginatedResponse.create(reviews, total, page, page_size)


@router.get(
    "/admin/all",
    response_model=AllReviewsPaginatedResponse,
    dependencies=[RequireAdmin],
    summary="[Admin] All reviews across every entity",
    description=(
        "Returns paginated reviews for **all** hotels, apartments, restaurants, "
        "doctors and hospitals in one feed. Each item includes the reviewed "
        "entity's name.\n\n"
        "By default every moderation status is included. Narrow with `entity_type`, "
        "`is_approved` (True=approved, False=pending/rejected), `is_verified`, or "
        "`min_rating`, and sort by newest, rating or helpfulness."
    ),
)
async def admin_list_all_reviews(
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    entity_type: Optional[EntityType] = Query(
        None, description="Limit to one category (hotel, apartment, restaurant, doctor, hospital)"
    ),
    min_rating: Optional[int] = Query(None, ge=1, le=5, description="Minimum star rating"),
    is_approved: Optional[bool] = Query(None, description="True=approved, False=pending/rejected"),
    is_verified: Optional[bool] = Query(None, description="Only verified purchases"),
    sort_by: Literal["created_at", "rating", "helpful_count"] = Query("created_at"),
):
    service = ReviewService(db)
    reviews, total, average_rating = await service.list_all_admin(
        page=page,
        page_size=page_size,
        entity_type=entity_type,
        min_rating=min_rating,
        is_approved=is_approved,
        is_verified=is_verified,
        sort_by=sort_by,
    )
    return AllReviewsPaginatedResponse.create(reviews, total, page, page_size, average_rating)


@router.put(
    "/admin/{review_id}/approve",
    response_model=ReviewResponse,
    dependencies=[RequireAdmin],
    summary="[Admin] Approve or reject a review",
    description=(
        "Approve → review goes live and entity rating is recalculated.\n"
        "Reject → `rejection_reason` is required and stored (not shown publicly)."
    ),
)
async def admin_approve_review(
    review_id: UUID,
    data: AdminReviewApprove,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = ReviewService(db)
    try:
        return await service.admin_approve(review_id, data, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/admin/{review_id}/respond",
    response_model=ReviewResponse,
    dependencies=[RequireAdmin],
    summary="[Admin] Post official response to a review",
)
async def admin_respond_to_review(
    review_id: UUID,
    data: AdminReviewResponse,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = ReviewService(db)
    try:
        return await service.admin_respond(review_id, data.response_text, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.put(
    "/admin/{review_id}/feature",
    response_model=ReviewResponse,
    dependencies=[RequireAdmin],
    summary="[Admin] Pin or unpin a review as featured",
)
async def admin_feature_review(
    review_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
    featured: bool = Query(..., description="True to feature, False to unfeature"),
):
    service = ReviewService(db)
    try:
        return await service.admin_feature(review_id, featured, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete(
    "/admin/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[RequireAdmin],
    summary="[Admin] Delete any review",
)
async def admin_delete_review(
    review_id: UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    service = ReviewService(db)
    try:
        await service.admin_delete(review_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
