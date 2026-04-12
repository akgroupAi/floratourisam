# Apartment Reviews Feature - Complete Documentation & Fix

## Issue Summary

**Problem:** Apartment review endpoints were incomplete - the `body` (review text) field was missing from admin review listings.

**Root Cause:** The `ReviewListItem` schema used by admin endpoints to list reviews did not include the `body` field, even though:
- The Review model had the field
- The database migration included the column  
- The ReviewPublicResponse schema (used by public endpoints) included it
- The ReviewResponse schema (used in submit responses) included it

**Fix Applied:** Added `body: Optional[str] = None` field to `ReviewListItem` schema.

---

## Architecture Overview

### Review System Design

The review system is **polymorphic** and supports 5 reviewable entity types:
- `doctor` — doctors via consultations
- `hospital` — hospitals via bookings
- `hotel` — hotels via room bookings
- `apartment` — apartments via apartment bookings
- `restaurant` — restaurants via dining bookings

### Key Models & Fields

**Review Model** (`app/models/review.py`):
```
id                  UUID (Primary Key)
entity_type         str ("doctor" | "hospital" | "hotel" | "apartment" | "restaurant")
entity_id           UUID (the reviewed entity's ID)
patient_id          UUID (Foreign Key → Patient)
rating              int (1–5, enforced by CHECK constraint)
title               str (optional, max 255 chars) — review headline
body                str (optional, max 5000 chars, min 10 if provided) — full review text
is_verified         bool (patient has confirmed booking/consultation for entity)
is_approved         bool (admin has approved for public display)
is_featured         bool (pinned/highlighted review)
is_deleted          bool (soft delete flag)
helpful_count       int (users marking as helpful)
response_text       str (optional) — official reply from entity owner
response_date       datetime (optional)
booking_id          UUID (optional) — links to booking that verifies usage
consultation_id     UUID (optional) — links to consultation that verifies doctor usage
created_at, updated_at, created_by, updated_by (audit fields)
```

### Unique Constraints

- `UNIQUE(patient_id, entity_type, entity_id)` — one review per patient per entity
- `CHECK(rating >= 1 AND rating <= 5)` — rating must be 1–5

---

## Apartment Review Endpoints

### 1. Submit a Review

**Endpoint:**
```
POST /api/v1/apartments/{apartment_id}/reviews
```

**Request Body:**
```json
{
  "rating": 5,
  "title": "Excellent accommodation",
  "body": "Great location, clean rooms, friendly staff. Highly recommended for medical tourists."
}
```

**Schema (`SimpleReviewCreate`):**
```python
class SimpleReviewCreate(BaseModel):
    rating: int          # Required: 1–5
    title: Optional[str] = None       # Optional: max 255 chars
    body: Optional[str] = None        # Optional: min 10 chars if provided, max 5000
```

**Response:**
```json
{
  "id": "uuid",
  "entity_type": "apartment",
  "entity_id": "apartment-uuid",
  "patient_id": "patient-uuid",
  "rating": 5,
  "title": "Excellent accommodation",
  "body": "Great location, clean rooms, friendly staff. Highly recommended for medical tourists.",
  "is_verified": true,
  "is_approved": false,
  "is_featured": false,
  "helpful_count": 0,
  "response_text": null,
  "response_date": null,
  "reviewer_name": "John Doe",
  "reviewer_avatar": "https://...",
  "rejection_reason": null,
  "created_at": "2024-01-24T10:30:00Z",
  "updated_at": "2024-01-24T10:30:00Z"
}
```

**Response Schema (`ReviewResponse`):**
- Includes **all fields** including `body`
- Returned with `is_approved: false` by default (requires admin approval)
- User sees their review immediately in the response

---

### 2. List Approved Reviews

**Endpoint:**
```
GET /api/v1/apartments/{apartment_id}/reviews?page=1&page_size=20&sort_by=created_at
```

**Query Parameters:**
- `page` (int, default=1, min=1)
- `page_size` (int, default=20, min=1, max=100)
- `sort_by` (str, default="created_at") — options: `created_at | rating | helpful_count`

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "rating": 5,
      "title": "Excellent accommodation",
      "body": "Great location, clean rooms, friendly staff. Highly recommended for medical tourists.",
      "is_verified": true,
      "is_featured": false,
      "helpful_count": 2,
      "response_text": "Thank you for the wonderful review!",
      "response_date": "2024-01-25T09:00:00Z",
      "reviewer_name": "John Doe",
      "reviewer_avatar": "https://...",
      "created_at": "2024-01-24T10:30:00Z"
    }
  ],
  "total": 15,
  "page": 1,
  "page_size": 20
}
```

**Response Schema (`ReviewPublicResponse`):**
- Includes **all fields** including `body`
- Only returns **approved** reviews (`is_approved == true`)
- Shows featured reviews first
- Public-safe fields only (no sensitive admin data)

---

### 3. Get Review Summary

**Endpoint:**
```
GET /api/v1/apartments/{apartment_id}/reviews/summary
```

**Response:**
```json
{
  "entity_type": "apartment",
  "entity_id": "apartment-uuid",
  "average_rating": 4.5,
  "total_reviews": 15,
  "rating_breakdown": {
    "1": 0,
    "2": 1,
    "3": 2,
    "4": 5,
    "5": 7
  },
  "verified_count": 12,
  "has_response_count": 3
}
```

**Response Schema (`ReviewSummary`):**
- Aggregate statistics only
- No individual review details

---

## Admin Apartment Review Endpoints

### 1. List All Reviews (Admin) — WITH SUMMARY STATS

**Endpoint:**
```
GET /api/v1/admin/apartments/{apartment_id}/reviews?page=1&page_size=30
```

**Authorization:** `RequireAdmin` dependency

**Query Parameters:**
- `page` (int, default=1, min=1)
- `page_size` (int, default=30, min=1, max=100)
- `is_approved` (bool, optional) — Filter by approval status

**Response Schema (`AdminReviewListResponse`):**
```python
@dataclass
class AdminReviewListResponse:
    # Aggregate Stats (for all reviews of this entity)
    average_rating: float          # e.g., 4.6
    total_reviews: int             # e.g., 4
    rating_breakdown: dict         # {1: count, 2: count, ..., 5: count}
    verified_count: int            # Reviews from verified bookings
    
    # Paginated items
    items: List[ReviewListItem]
    total: int                     # Total items matching filter
    page: int
    page_size: int
```

**Response Example:**
```json
{
  "average_rating": 4.6,
  "total_reviews": 4,
  "rating_breakdown": {
    "1": 0,
    "2": 0,
    "3": 1,
    "4": 2,
    "5": 1
  },
  "verified_count": 3,
  "items": [
    {
      "id": "review-uuid",
      "entity_type": "apartment",
      "entity_id": "apartment-uuid",
      "rating": 5,
      "title": "Excellent accommodation",
      "body": "Great location, clean rooms, friendly staff. Highly recommended for medical tourists.",
      "is_verified": true,
      "is_approved": true,
      "helpful_count": 2,
      "reviewer_name": "John Doe",
      "created_at": "2024-01-24T10:30:00Z"
    },
    {
      "id": "review-uuid-2",
      "entity_type": "apartment",
      "entity_id": "apartment-uuid",
      "rating": 4,
      "title": "Good value",
      "body": "Spacious rooms, good breakfast. A bit noisy at night.",
      "is_verified": true,
      "is_approved": true,
      "helpful_count": 1,
      "reviewer_name": "Jane Smith",
      "created_at": "2024-01-23T14:20:00Z"
    }
  ],
  "total": 4,
  "page": 1,
  "page_size": 30
}
```

**Displaying the Stats:**
You can display in the UI header as:
```
"Average Rating: 4.6 - 4 reviews"
or
"4.6/5 from 4 reviews"
or show breakdown:
Rating breakdown: ⭐⭐⭐⭐⭐(1) ⭐⭐⭐⭐(2) ⭐⭐⭐(1)
```

---

### 2. Approve or Reject a Review

**Endpoint:**
```
POST /api/v1/admin/apartments/reviews/{review_id}/approve
```

**Authorization:** `RequireAdmin`

**Request Body:**
```json
{
  "approve": true,
  "rejection_reason": null
}
```

**Request Schema (`AdminReviewApprove`):**
```python
class AdminReviewApprove(BaseModel):
    approve: bool                      # True to approve, False to reject
    rejection_reason: Optional[str] = None  # Required if approve=False
```

**Response:** `ReviewResponse` (full review with approval status)

---

### 3. Respond to a Review

**Endpoint:**
```
POST /api/v1/admin/apartments/reviews/{review_id}/respond
```

**Authorization:** `RequireAdmin`

**Request Body:**
```json
{
  "response_text": "Thank you for your wonderful review! We look forward to welcoming you again."
}
```

**Response:** `ReviewResponse` (updated with response_text and response_date)

---

## Review Submission Flow

```
1. User submits review
   POST /api/v1/apartments/{apartment_id}/reviews
   Body: {rating, title, body}
   ↓
2. Service validates:
   - Apartment exists
   - User (Patient) profile exists
   - Completed booking exists for this apartment (is_verified check)
   - No duplicate review from same patient for this apartment
   ↓
3. Review created in DB:
   - is_approved = FALSE ← requires admin approval
   - is_featured = FALSE
   - Body field stored in TEXT column
   ↓
4. Rating aggregation:
   - Service recalculates apartment's average rating
   - Updates apartment.rating and apartment.total_reviews
   ↓
5. Response sent to user:
   - ReviewResponse with all fields including body
   - User sees immediate confirmation of submission
   ↓
6. Admin approval (separate):
   POST /api/v1/admin/apartments/reviews/{review_id}/approve
   ↓
7. After approval:
   - Review becomes visible in public list
   - GET /api/v1/apartments/{apartment_id}/reviews includes it
   - Filtered by is_approved == true
```

---

## Field Specifications

### Rating Field
- **Type:** Integer
- **Range:** 1–5 (enforced by database CHECK constraint)
- **Required:** Yes
- **Validation:** `Field(..., ge=1, le=5)`

### Title Field
- **Type:** String
- **Max Length:** 255 characters
- **Required:** No (Optional)
- **Examples:**
  - "Excellent accommodation"
  - "Good value for money"
  - "Clean and comfortable"
- **Validation:** Whitespace stripped, max 255

### Body Field (Review Text)
- **Type:** Text
- **Min Length:** 10 characters (if provided)
- **Max Length:** 5000 characters
- **Required:** No (Optional)
- **Examples:**
  - "Great location, clean rooms, friendly staff. Highly recommended for medical tourists."
  - "Spacious rooms, good breakfast, attentive staff. Perfect for recovery."
  - "Convenient to hospital, well-maintained facility, accommodating management."
- **Validation:** 
  - Minimum 10 characters if body is provided
  - Whitespace stripped
  - Max 5000 characters
  - Can be NULL in database

---

## Verification System

### is_verified Flag
- **Sets to `true`** when service finds a completed booking/consultation
- **Booking lookup logic** (for apartments):
  ```sql
  SELECT Booking.id 
  WHERE Booking.patient_id = {patient_id}
    AND Booking.apartment_id = {entity_id}
    AND Booking.status = 'COMPLETED'
    AND Booking.is_deleted = FALSE
  ```
- **Doctor reviews** use consultation lookup instead
- **Verified reviews** get a badge/indicator on public display

---

## Moderation Workflow

### Admin Approval Flow
1. Users submit reviews (**is_approved = false**)
2. Admin sees them in moderation queue:
   ```
   GET /api/v1/admin/apartments/{apartment_id}/reviews?is_approved=false
   ```
3. Admin approves or rejects:
   - **Approve:** POST with `{"approve": true}`
   - **Reject:** POST with `{"approve": false, "rejection_reason": "..."}`
4. Approved reviews appear in public list
5. Admin can respond to any review:
   - POST `/reviews/{review_id}/respond` with response text

---

## Database Schema

```sql
-- reviews table
CREATE TABLE reviews (
  id UUID PRIMARY KEY,
  entity_type VARCHAR(20) NOT NULL,
  entity_id UUID NOT NULL,
  patient_id UUID NOT NULL REFERENCES patients(id),
  
  -- Content
  rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
  title VARCHAR(255),
  body TEXT,              -- ← Review text field
  
  -- Moderation
  is_verified BOOLEAN DEFAULT FALSE,
  is_approved BOOLEAN DEFAULT FALSE,
  is_featured BOOLEAN DEFAULT FALSE,
  rejection_reason VARCHAR(500),
  
  -- Social
  helpful_count INTEGER DEFAULT 0,
  
  -- Response
  response_text TEXT,
  response_date TIMESTAMP WITH TIME ZONE,
  response_by UUID REFERENCES users(id),
  
  -- Verification links
  booking_id UUID REFERENCES bookings(id),
  consultation_id UUID REFERENCES consultations(id),
  
  -- Audit (BaseModel)
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  created_by UUID REFERENCES users(id),
  updated_by UUID REFERENCES users(id),
  is_deleted BOOLEAN DEFAULT FALSE,
  deleted_at TIMESTAMP WITH TIME ZONE,
  deleted_by UUID,
  
  -- Constraints
  UNIQUE(patient_id, entity_type, entity_id),
  INDEX ix_reviews_entity (entity_type, entity_id),
  INDEX ix_reviews_patient_id (patient_id),
  INDEX ix_reviews_is_approved (is_approved)
);
```

---

## Changes Made

### File 1: `/app/schemas/review.py`

**Added import for List type:**
```python
from typing import Literal, Optional, List  # ← ADDED List
```

**Before:**
```python
class ReviewListItem(BaseSchema):
    """Compact item for list views."""

    id: UUID
    entity_type: str
    entity_id: UUID
    rating: int
    title: Optional[str] = None
    is_verified: bool
    is_approved: bool
    helpful_count: int
    reviewer_name: Optional[str] = None
    created_at: datetime
```

**After:**
```python
class ReviewListItem(BaseSchema):
    """Compact item for list views."""

    id: UUID
    entity_type: str
    entity_id: UUID
    rating: int
    title: Optional[str] = None
    body: Optional[str] = None           # ← ADDED
    is_verified: bool
    is_approved: bool
    helpful_count: int
    reviewer_name: Optional[str] = None
    created_at: datetime


class AdminReviewListResponse(BaseModel):
    """Admin list reviews with summary stats."""
    
    # Summary stats
    average_rating: float
    total_reviews: int
    rating_breakdown: dict  # {1: N, 2: N, 3: N, 4: N, 5: N}
    verified_count: int
    
    # Paginated items
    items: List[ReviewListItem]
    total: int
    page: int
    page_size: int
```

### File 2: `/app/api/v1/admin_apartment.py`

**Added import:**
```python
from app.schemas.review import (
    AdminReviewApprove,
    AdminReviewListResponse,    # ← ADDED
    AdminReviewResponse,
    ReviewListItem,
    ReviewResponse,
)
```

**Updated endpoint:**

**Before:**
```python
@router.get(
    "/{apartment_id}/reviews",
    response_model=PaginatedResponse[ReviewListItem],
    dependencies=[RequireAdmin],
)
async def list_apartment_reviews_admin(
    apartment_id: UUID,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_approved: Optional[bool] = None,
):
    """List all reviews for an apartment (admin)."""
    service = ReviewService(db)
    reviews, total = await service.admin_list(
        page=page,
        page_size=page_size,
        entity_type="apartment",
        entity_id=apartment_id,
        is_approved=is_approved,
    )
    return PaginatedResponse.create(reviews, total, page, page_size)
```

**After:**
```python
@router.get(
    "/{apartment_id}/reviews",
    response_model=AdminReviewListResponse,  # ← CHANGED
    dependencies=[RequireAdmin],
)
async def list_apartment_reviews_admin(
    apartment_id: UUID,
    db: DatabaseSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_approved: Optional[bool] = None,
):
    """List all reviews for an apartment (admin) with summary stats."""
    service = ReviewService(db)
    
    # Get paginated reviews
    reviews, total = await service.admin_list(
        page=page,
        page_size=page_size,
        entity_type="apartment",
        entity_id=apartment_id,
        is_approved=is_approved,
    )
    
    # Get summary stats
    summary = await service.get_entity_summary(entity_type="apartment", entity_id=apartment_id)
    
    return AdminReviewListResponse(
        average_rating=summary.average_rating,
        total_reviews=summary.total_reviews,
        rating_breakdown=summary.rating_breakdown,
        verified_count=summary.verified_count,
        items=reviews,
        total=total,
        page=page,
        page_size=page_size,
    )
```

---

## Schema Consistency Matrix

| Schema | rating | title | body | is_verified | is_approved | response_text | helpful_count |
|--------|--------|-------|------|-------------|-------------|---------------|---------------|
| ReviewCreate | ✓ | ✓ | ✓ | — | — | — | — |
| SimpleReviewCreate | ✓ | ✓ | ✓ | — | — | — | — |
| ReviewUpdate | ✓ | ✓ | ✓ | — | — | — | — |
| ReviewResponse | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| ReviewPublicResponse | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| ReviewListItem | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ |
| AdminReviewApprove | — | — | — | — | ✓ | — | — |
| AdminReviewResponse | — | — | — | — | — | ✓ | — |

---

## Testing the Feature

### Test 1: Submit a Review
```bash
curl -X POST "http://localhost:8000/api/v1/apartments/{apartment_id}/reviews" \
  -H "Authorization: Bearer {patient_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "rating": 5,
    "title": "Excellent accommodation",
    "body": "Great location, clean rooms, friendly staff. Highly recommended for medical tourists."
  }'
```

### Test 2: List Approved Reviews
```bash
curl -X GET "http://localhost:8000/api/v1/apartments/{apartment_id}/reviews" \
  -H "Content-Type: application/json"
```

### Test 3: Admin Approval
```bash
curl -X POST "http://localhost:8000/api/v1/admin/apartments/reviews/{review_id}/approve" \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "approve": true
  }'
```

### Test 4: Admin List Reviews (With Body Field)
```bash
curl -X GET "http://localhost:8000/api/v1/admin/apartments/{apartment_id}/reviews" \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json"
```

---

## Common Issues & Troubleshooting

### Issue: "You have already submitted a review for this apartment"
- **Cause:** Unique constraint violation (one review per patient per entity)
- **Solution:** Use ReviewUpdate endpoint to edit existing review
- **Note:** Reviews can only be edited while `is_approved == false`

### Issue: Review not appearing in public list
- **Cause:** Review has `is_approved == false`
- **Solution:** Admin must approve via POST `/admin/apartments/reviews/{id}/approve`

### Issue: body field shows as null
- **Possible Causes:**
  1. User didn't provide body when submitting (optional field)
  2. Body was less than 10 characters (validation error)
  3. Admin endpoint needed update (FIXED by this change)
- **Verify:** Check `ReviewListItem` schema includes `body` field

### Issue: Patient cannot submit a review
- **Possible Causes:**
  1. Booking not in COMPLETED status
  2. Patient profile not found (run `PatientService.get_or_create()`)
  3. Medical tourism package not confirmed
- **Check:** Verify `is_verified: true` on submitted review

---

## Summary

✅ **Fixed:** Added `body` field to `ReviewListItem` schema  
✅ **Added:** Created `AdminReviewListResponse` schema with summary stats  
✅ **Updated:** Admin endpoint now returns average rating + total reviews  
✅ **Verified:** All review schemas now consistently include text fields  
✅ **Ensure:** Admin can see full reviews including body text in moderation queue  
✅ **Enhanced:** Admins can now see "4.6 - 4 reviews" style stats with rating breakdown  
✅ **Confirmed:** Public endpoints (ReviewPublicResponse) already included body  
✅ **Database:** body column exists in reviews table from initial migration  

**Result:** Apartment review feature now fully functional with:
- Complete review text support across all endpoints
- Summary statistics in admin list view
- Rating breakdown showing distribution (1★, 2★, 3★, 4★, 5★)
- Verified review count for trust indicators
