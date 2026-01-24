# Flora Medical - Site API Documentation

Complete API documentation for the Flora Medical medical tourism platform.

## Base URL
```
http://localhost:8000/api/v1
```

---

## 🏠 Public Pages API

### GET /pages/home
Get home page content with all sections.

**Response:**
```json
{
  "hero": {
    "title": "AI-Powered Healthcare Journey",
    "subtitle": "World-class medical care, personalized for you",
    "primary_cta": {"text": "Start Treatment Plan", "url": "/services"},
    "secondary_cta": {"text": "Talk to AI Assistant", "url": "/ai-chat"}
  },
  "trust_bar": {
    "patient_count": "5,000+",
    "countries": ["US", "UK", "AE", "NG", "CA"],
    "message": "Trusted by patients worldwide"
  },
  "category_links": [
    {"icon": "stethoscope", "label": "Medical Care", "url": "/services"},
    {"icon": "hotel", "label": "Stays", "url": "/accommodations"}
  ],
  "featured_services": [...],
  "how_it_works": {
    "title": "How It Works",
    "steps": [
      {"number": 1, "icon": "upload", "title": "Upload Records", "description": "..."},
      {"number": 2, "icon": "brain", "title": "AI Suggestions", "description": "..."},
      {"number": 3, "icon": "calendar", "title": "Schedule Consult", "description": "..."}
    ]
  },
  "destinations": [...],
  "testimonials": [...],
  "stats": {...}
}
```

---

### GET /pages/services
List all medical services with filters.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| page | int | Page number (default: 1) |
| page_size | int | Items per page (default: 12) |
| category | string | Filter by category |
| search | string | Search by name |

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Orthopedics",
      "slug": "orthopedics",
      "category": "Surgery",
      "icon": "bone",
      "image_url": "/images/orthopedics.jpg",
      "success_rate": 98.5,
      "patient_count": 1200,
      "savings_percent": 70,
      "price_from": 5000,
      "is_featured": true
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 12,
  "pages": 5
}
```

### GET /pages/services/categories
Get all treatment categories.

**Response:**
```json
[
  {"name": "Surgery", "count": 15},
  {"name": "Dental", "count": 8},
  {"name": "Treatment", "count": 12},
  {"name": "Checkup", "count": 5}
]
```

### GET /pages/services/{slug}
Get treatment details by slug.

---

### GET /pages/destinations
List all destinations.

### GET /pages/destinations/{slug}
Get destination details with hospitals, doctors, accommodations.

### GET /pages/destinations/{slug}/hospitals
Get hospitals in a specific destination.

### GET /pages/destinations/{slug}/doctors
Get top doctors in a destination.

---

### GET /pages/blog
List published blog posts.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| page | int | Page number |
| page_size | int | Items per page |
| category | string | Filter by category |
| tag | string | Filter by tag |

### GET /pages/blog/categories
Get blog categories.

### GET /pages/blog/{slug}
Get blog post by slug.

---

### GET /pages/about
Get about page content.

**Response:**
```json
{
  "hero": {...},
  "vision": {"title": "Our Vision", "content": "..."},
  "mission": {"title": "Our Mission", "content": "..."},
  "values": [
    {"icon": "shield", "title": "Trust", "description": "..."},
    {"icon": "lightbulb", "title": "Innovation", "description": "..."}
  ],
  "timeline": [
    {"year": "2018", "title": "Founded", "description": "..."},
    {"year": "2024", "title": "5000+ Patients", "description": "..."}
  ],
  "leadership": [...],
  "team": [...],
  "stats": {...}
}
```

---

### GET /pages/faq
Get FAQ page with categories.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| category | string | Filter by category (General, Medical, Travel, Payment) |

**Response:**
```json
{
  "hero": {...},
  "categories": ["General", "Medical", "Travel", "Payment"],
  "faqs_by_category": {
    "General": [
      {"id": "uuid", "question": "How do I book?", "answer": "Simply...", "category": "General"}
    ],
    "Medical": [...]
  },
  "all_faqs": [...]
}
```

### GET /pages/faq/categories
Get FAQ categories with counts.

---

### GET /pages/testimonials
List approved testimonials.

---

### GET /pages/contact
Get contact page content.

**Response:**
```json
{
  "hero": {...},
  "contact_info": {
    "email": "care@floramedical.com",
    "phone": "+1 (888) 123-4567",
    "address": "123 Healthcare Avenue, New Delhi, India",
    "working_hours": "24/7 Support Available"
  },
  "form_fields": [
    {"name": "name", "label": "Full Name", "type": "text", "required": true},
    {"name": "email", "label": "Email", "type": "email", "required": true},
    {"name": "message", "label": "Message", "type": "textarea", "required": true}
  ],
  "social_links": {...}
}
```

---

### GET /pages/navigation
Get site navigation structure.

**Response:**
```json
{
  "main_menu": [
    {"label": "Home", "url": "/"},
    {
      "label": "Services",
      "url": "/services",
      "children": [
        {"label": "All Services", "url": "/services"},
        {"label": "Find Doctors", "url": "/doctors"},
        {"label": "Hospitals", "url": "/hospitals"}
      ]
    },
    {
      "label": "Destinations",
      "url": "/destinations",
      "children": [
        {"label": "Delhi NCR", "url": "/destinations/delhi-ncr"},
        {"label": "Mumbai", "url": "/destinations/mumbai"}
      ]
    }
  ],
  "footer_menu": {
    "company": [...],
    "services": [...],
    "support": [...],
    "legal": [...]
  },
  "social_links": {...}
}
```

### GET /pages/settings
Get public site settings.

---

## 📝 Lead Generation API

### POST /leads/quote
Submit a quote request.

**Request:**
```json
{
  "email": "patient@example.com",
  "phone": "+1234567890",
  "name": "John Doe",
  "country": "United States",
  "medical_condition": "Need knee replacement surgery",
  "treatment_interest": "Orthopedics",
  "preferred_destination": "Delhi NCR",
  "message": "Looking for affordable options"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Thank you! We've received your request and will contact you within 24 hours.",
  "reference_id": "uuid"
}
```

### POST /leads/contact
Submit contact form.

**Request:**
```json
{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "phone": "+1234567890",
  "subject": "General Inquiry",
  "message": "I have questions about..."
}
```

### POST /leads/newsletter
Subscribe to newsletter.

**Query: `email=user@example.com`**

### POST /leads/callback
Request a callback.

**Query: `phone=+1234567890&name=John`**

---

## 🔧 Admin Site Content API

All admin endpoints require `Authorization: Bearer <token>` with admin role.

---

### Destinations Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /admin/site/destinations | List all destinations |
| POST | /admin/site/destinations | Create destination |
| GET | /admin/site/destinations/{id} | Get destination |
| PUT | /admin/site/destinations/{id} | Update destination |
| DELETE | /admin/site/destinations/{id} | Delete destination |

**Create/Update Request:**
```json
{
  "name": "Delhi NCR",
  "slug": "delhi-ncr",
  "country": "India",
  "region": "North India",
  "tagline": "The Healthcare Capital",
  "description": "...",
  "hero_image": "/images/delhi.jpg",
  "highlights": ["World-class hospitals", "Affordable care"],
  "is_featured": true
}
```

---

### Treatments Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /admin/site/treatments | List all treatments |
| POST | /admin/site/treatments | Create treatment |
| GET | /admin/site/treatments/{id} | Get treatment |
| PUT | /admin/site/treatments/{id} | Update treatment |
| DELETE | /admin/site/treatments/{id} | Delete treatment |

**Create/Update Request:**
```json
{
  "name": "Knee Replacement",
  "slug": "knee-replacement",
  "category": "Surgery",
  "short_description": "Total knee replacement surgery",
  "description": "...",
  "icon": "bone",
  "image_url": "/images/knee.jpg",
  "success_rate": 98.5,
  "price_from": 5000,
  "price_to": 15000,
  "procedures": ["Total Knee Replacement", "Partial Knee Replacement"],
  "is_featured": true
}
```

---

### Blog Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /admin/site/blog | List all posts |
| POST | /admin/site/blog | Create post |
| GET | /admin/site/blog/{id} | Get post |
| PUT | /admin/site/blog/{id} | Update post |
| DELETE | /admin/site/blog/{id} | Delete post |

**Create/Update Request:**
```json
{
  "title": "5 Tips for Medical Travel",
  "slug": "5-tips-medical-travel",
  "excerpt": "Planning your medical journey abroad?",
  "content": "# Full markdown content...",
  "category": "Travel Tips",
  "tags": ["travel", "tips", "preparation"],
  "featured_image": "/images/blog/medical-travel.jpg",
  "status": "published"
}
```

---

### Testimonials Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /admin/site/testimonials | List all testimonials |
| POST | /admin/site/testimonials | Create testimonial |
| PUT | /admin/site/testimonials/{id}/approve | Approve testimonial |
| DELETE | /admin/site/testimonials/{id} | Delete testimonial |

**Create Request:**
```json
{
  "patient_name": "John D.",
  "patient_country": "United States",
  "patient_avatar": "/images/patients/john.jpg",
  "treatment_name": "Knee Replacement",
  "hospital_name": "Fortis Hospital",
  "rating": 5,
  "title": "Life-changing experience",
  "content": "I received excellent care...",
  "video_url": "https://youtube.com/...",
  "is_featured": true
}
```

---

### FAQ Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /admin/site/faqs | List all FAQs |
| POST | /admin/site/faqs | Create FAQ |
| PUT | /admin/site/faqs/{id} | Update FAQ |
| DELETE | /admin/site/faqs/{id} | Delete FAQ |

**Create/Update Request:**
```json
{
  "question": "How do I book a consultation?",
  "answer": "You can book through our website...",
  "category": "General",
  "is_featured": true,
  "display_order": 1
}
```

---

### Team Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /admin/site/team | List all team members |
| POST | /admin/site/team | Create team member |
| PUT | /admin/site/team/{id} | Update team member |
| DELETE | /admin/site/team/{id} | Delete team member |

**Create/Update Request:**
```json
{
  "name": "Dr. Sarah Johnson",
  "role": "Chief Medical Officer",
  "department": "Leadership",
  "image_url": "/images/team/sarah.jpg",
  "bio": "Dr. Johnson brings 20 years of experience...",
  "linkedin_url": "https://linkedin.com/in/sarah-johnson",
  "is_leadership": true
}
```

---

### Leads Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /admin/site/leads | List all leads |
| PUT | /admin/site/leads/{id}/status | Update lead status |

**Status Values:** `new`, `contacted`, `qualified`, `converted`

---

## 🔗 CMS Block Types Reference

| Block Type | Config Fields |
|------------|---------------|
| `HERO` | title, subtitle, background_image, primary_cta, secondary_cta |
| `STATS_GRID` | title, items: [{icon, label, value, suffix}] |
| `LISTING_GRID` | entity_type, show_filters, items_per_page |
| `ACCORDION` | title, categories, items: [{question, answer}] |
| `STEP_WIZARD` | title, steps: [{number, icon, title, description}] |
| `FORM_BLOCK` | title, fields: [{name, label, type, required}] |
| `MEDIA_CARD` | title, image_url, description, cta_text, cta_url |
| `TESTIMONIALS` | title, items, layout (carousel/grid) |
| `TEAM` | title, members: [{name, role, image_url, bio}] |
| `VALUES` | title, items: [{icon, title, description}] |
| `TIMELINE` | title, items: [{year, title, description}] |
| `NEWSLETTER` | title, subtitle, placeholder, button_text |
| `CONTACT_INFO` | email, phone, address, social_links |
| `TRUST_BAR` | patient_count, countries, message |

---

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Missing/invalid token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 422 | Validation Error - Invalid field values |
| 500 | Server Error - Internal error |
