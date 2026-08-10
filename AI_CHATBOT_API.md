# Flora AI Chatbot — API Reference (Input / Output)

Base URL: `http://localhost:8000/api/v1/ai`  
Auth: All endpoints require `Authorization: Bearer <JWT_TOKEN>` (except `/refresh-knowledge` which requires Admin role)

---

## 1. POST `/chat` — Send Message to AI

### Input (Request Body)

```json
{
  "message": "Hello",
  "session_id": null,
  "context_type": null,
  "context_data": null,
  "report_text": null
}
```

| Field          | Type           | Required | Description                                                  |
|----------------|----------------|----------|--------------------------------------------------------------|
| `message`      | string (≤5000) | ✅       | User's message to the AI assistant                           |
| `session_id`   | string (≤100)  | ❌       | Pass to continue an existing conversation. `null` = new chat |
| `context_type` | string (≤50)   | ❌       | Hint: `"general"`, `"booking"`, `"medical"`, `"support"`     |
| `context_data` | object         | ❌       | Any extra context (e.g. `{"doctor_id": "..."}`)              |
| `report_text`  | string (≤20k)  | ❌       | Paste a medical report inline for context                    |

### Output (200 OK)

```json
{
  "response": "Hello Abc@gmail.com, it is a pleasure to meet you. I'm Flora, and I am here to help guide you through your healthcare journey with empathy and care.\n\nTo ensure I provide you with the most helpful guidance and connect you with the right specialist, could you tell me a little bit about what is bringing you here today?\n\nSpecifically, are you experiencing any particular **symptoms or pain**, and is there a specific **treatment or surgery** you are already considering?",
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "conversation_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "doctor_suggestions": [
    {
      "id": "d1e2f3a4-b5c6-7890-abcd-1234567890ab",
      "name": "Dr. Pranjel Pipara",
      "specialty": "Orthopedic Surgery",
      "specialties": ["Joint Replacement", "Arthroscopy", "ACL Surgery"],
      "hospital": "OrthoSport Speciality Hospital",
      "city": "Ahmedabad",
      "country": "India",
      "rating": 4.9,
      "fee": 750.0,
      "experience_years": 13,
      "languages": ["English", "Hindi", "Gujarati"],
      "photo_url": "/uploads/avatars/dr-pranjel.jpg",
      "profile_url": "/doctors/d1e2f3a4-b5c6-7890-abcd-1234567890ab",
      "recommendation": "Highly recommended specialist with 13+ years experience and great reviews."
    },
    {
      "id": "a2b3c4d5-e6f7-8901-bcde-234567890abc",
      "name": "Dr. Manish Dhawan",
      "specialty": "Urology & Kidney Transplant",
      "specialties": ["Kidney Transplant", "Minimally Invasive Urology", "Renal Surgery"],
      "hospital": "Fusion Kidney Institute",
      "city": "Ahmedabad",
      "country": "India",
      "rating": 4.6,
      "fee": null,
      "experience_years": 10,
      "languages": ["English", "Hindi", "Gujarati"],
      "photo_url": "/uploads/avatars/dr-manish.jpg",
      "profile_url": "/doctors/a2b3c4d5-e6f7-8901-bcde-234567890abc",
      "recommendation": "Excellent alternative with 10+ years experience and great reviews."
    }
  ],
  "recommendations": [
    {
      "type": "hotel",
      "id": "9f8e7d6c-5b4a-3210-fedc-ba9876543210",
      "name": "Grand Care Hotel",
      "description": "0.8 km from Apollo Hospital · 4-star · medical amenities available · rated 4.6/5",
      "city": "Ahmedabad",
      "country": "India",
      "rating": 4.6,
      "price": 3500.0,
      "currency": "INR",
      "image_url": "/uploads/hotels/grand-care.jpg",
      "url": "/hotels/grand-care-hotel",
      "relevance_score": 0.7412
    },
    {
      "type": "apartment",
      "id": "1a2b3c4d-5e6f-7890-abcd-ef1234567890",
      "name": "Serenity Serviced Apartments",
      "description": "1.5 km from Apollo Hospital · 2BR · rated 4.4/5",
      "city": "Ahmedabad",
      "country": "India",
      "rating": 4.4,
      "price": 2800.0,
      "currency": "INR",
      "image_url": null,
      "url": "/apartments/serenity-serviced-apartments",
      "relevance_score": 0.6893
    },
    {
      "type": "page",
      "id": null,
      "name": "Hotels",
      "description": "Book hotel accommodation near partner hospitals for patients and accompanying family.",
      "city": null,
      "country": null,
      "rating": null,
      "price": null,
      "currency": null,
      "image_url": null,
      "url": "/hotels",
      "relevance_score": 0.5120
    }
  ],
  "follow_up_questions": [
    "What treatment options are available for knee replacement?",
    "How do I book a video consultation with a doctor?",
    "Can you help me compare doctors for my condition?"
  ],
  "in_scope": true,
  "tokens_used": 487,
  "response_time_ms": 1243
}
```

### Output Fields

| Field | Type | Notes |
|---|---|---|
| `response` | string | Markdown. Links are site-relative (`/hotels/slug`) — render them as internal routes. |
| `doctor_suggestions` | array | Doctors only, with full profile detail. Unchanged. |
| `recommendations` | array | **Everything else the assistant matched**: hotels, apartments, restaurants, packages, hospitals, treatments, and website sections. Render as cards. |
| `follow_up_questions` | string[] | Exactly 3 suggested next questions. |
| `in_scope` | bool | `false` when the question was off-topic and the assistant redirected instead of answering. |

### `recommendations[].type`

`hotel` · `apartment` · `restaurant` · `package` · `hospital` · `treatment` · `page`

The array is **ordered by type** in exactly that sequence, so you can group it without sorting.
`url` is always site-relative and always present; `description` is a pre-built one-line reason
(distance to hospital first, since that is what matters to a patient) and may be `null`.
`page` entries point at browse sections like `/hotels` — use them when the user is exploring
rather than choosing.

### Off-Topic Questions

Ask the chatbot something unrelated to the website and it will not answer:

```json
{
  "response": "I can only help with Flora Medical services — I can help you find a doctor, compare treatment packages, or book a hotel near your hospital.",
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "doctor_suggestions": [],
  "recommendations": [],
  "follow_up_questions": [
    "Which hospitals do you partner with?",
    "How do I book a consultation?",
    "What accommodation is available near the hospital?"
  ],
  "in_scope": false,
  "tokens_used": 96,
  "response_time_ms": 604
}
```

Use `in_scope: false` to style the reply differently or to skip logging it as a real query.

### Continue Conversation (pass `session_id` back)

```json
{
  "message": "What treatment options are available for knee replacement?",
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### Error Responses

| Code | Detail                        | When                        |
|------|-------------------------------|-----------------------------|
| 401  | Not authenticated             | Missing/invalid JWT         |
| 503  | OPENAI_API_KEY is not configured | API key not set in `.env` |
| 500  | AI service error: ...         | OpenAI or internal error    |

---

## 2. POST `/analyze-report` — Medical Report Analysis

### Input (Request Body)

```json
{
  "report_text": "Patient: John Doe, Age: 45\nDiagnosis: Severe osteoarthritis of the right knee (Grade IV)\nFindings: Complete loss of joint space in medial compartment, subchondral sclerosis, osteophyte formation.\nRecommendation: Total Knee Replacement (TKR) advised.\nAdditional: Mild hypertension controlled with medication.",
  "session_id": null
}
```

| Field         | Type           | Required | Description                    |
|---------------|----------------|----------|--------------------------------|
| `report_text` | string (≤20k)  | ✅       | Full medical report text       |
| `session_id`  | string (≤100)  | ❌       | Optional session to associate  |

### Output (200 OK)

```json
{
  "report_analysis": {
    "primary_condition": "Severe osteoarthritis of the right knee (Grade IV)",
    "secondary_conditions": ["Mild hypertension"],
    "recommended_specialty": "Orthopedic Surgery",
    "urgency": "soon",
    "summary": "The patient has advanced knee osteoarthritis requiring total knee replacement surgery. The condition is Grade IV with complete joint space loss. Hypertension is controlled and should not affect surgical planning."
  },
  "recommended_doctors": [
    {
      "id": "d1e2f3a4-b5c6-7890-abcd-1234567890ab",
      "name": "Dr. Pranjel Pipara",
      "specialty": "Orthopedic Surgery",
      "specialties": ["Joint Replacement", "Arthroscopy", "ACL Surgery"],
      "hospital": "OrthoSport Speciality Hospital",
      "city": "Ahmedabad",
      "rating": 4.9,
      "fee": 750.0,
      "experience_years": 13,
      "profile_url": "/doctors/d1e2f3a4-b5c6-7890-abcd-1234567890ab",
      "relevance_score": 0.8921
    }
  ],
  "total_matches": 1,
  "response_time_ms": 2150
}
```

---

## 3. POST `/upload-report` — Upload File (Image/PDF) for AI Analysis

> **Multipart/form-data** — use this when the user attaches a file via a 📎 button.

### Input (Form Data)

```
POST /api/v1/ai/upload-report
Content-Type: multipart/form-data
```

| Field        | Type           | Required | Description                                            |
|--------------|----------------|----------|--------------------------------------------------------|
| `file`       | file           | ✅       | Medical report image (JPG, PNG, WebP) or PDF. Max 10 MB |
| `message`    | string (≤2000) | ❌       | Optional context message (e.g. "What does this mean?")  |
| `session_id` | string (≤100)  | ❌       | Pass to associate with an existing conversation         |

**Allowed file types:** `image/jpeg`, `image/jpg`, `image/png`, `image/webp`, `application/pdf`

- **Images** — analyzed using GPT-4o-mini vision (reads the image directly)
- **PDFs** — text is extracted with PyPDF2 then analyzed by GPT (scanned/image-only PDFs may not work)

### Output (200 OK)

```json
{
  "file_type": "image",
  "filename": "knee-xray.jpg",
  "report_analysis": {
    "primary_condition": "Severe osteoarthritis of the right knee (Grade IV)",
    "secondary_conditions": ["Mild joint effusion"],
    "recommended_specialty": "Orthopedic Surgery",
    "urgency": "soon",
    "summary": "X-ray shows Grade IV osteoarthritis with complete loss of joint space in the medial compartment. Total knee replacement is recommended."
  },
  "recommended_doctors": [
    {
      "id": "d1e2f3a4-b5c6-7890-abcd-1234567890ab",
      "name": "Dr. Pranjel Pipara",
      "specialty": "Orthopedic Surgery",
      "specialties": ["Joint Replacement", "Arthroscopy"],
      "hospital": "OrthoSport Speciality Hospital",
      "city": "Ahmedabad",
      "rating": 4.9,
      "fee": 750.0,
      "experience_years": 13,
      "profile_url": "/doctors/d1e2f3a4-b5c6-7890-abcd-1234567890ab",
      "relevance_score": 0.8921
    }
  ],
  "total_matches": 1,
  "response_time_ms": 3200
}
```

### Error Responses

| Code | Detail                              | When                                  |
|------|-------------------------------------|---------------------------------------|
| 400  | Unsupported file type: ...          | File is not JPG/PNG/WebP/PDF          |
| 400  | File too large. Maximum size is 10 MB | File exceeds 10 MB                  |
| 400  | Empty file.                         | Uploaded file has 0 bytes             |
| 401  | Not authenticated                   | Missing/invalid JWT                   |
| 500  | AI service error: ...               | OpenAI or internal error              |

---

## 4. GET `/conversations` — List Chat History (Sidebar)

### Input (Query Parameters)

```
GET /api/v1/ai/conversations?page=1&page_size=20&search=knee
```

| Param       | Type      | Default | Description                      |
|-------------|-----------|---------|----------------------------------|
| `page`      | int (≥1)  | 1       | Page number                      |
| `page_size` | int (1-100)| 20     | Results per page                 |
| `search`    | string    | —       | Filter by conversation title     |

### Output (200 OK)

```json
{
  "items": [
    {
      "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "title": "Hello",
      "context_type": "general",
      "is_active": true,
      "message_count": 3,
      "total_tokens_used": 1250,
      "estimated_cost": 0.00045,
      "rating": null,
      "feedback": null,
      "created_at": "2026-04-17T10:30:00Z",
      "ended_at": null
    },
    {
      "id": "b23dc10b-48cc-4372-a567-0e02b2c3d123",
      "session_id": "x9y8z7w6-v5u4-3210-fedc-ba9876543210",
      "title": "What treatment options are available for knee repl...",
      "context_type": "general",
      "is_active": true,
      "message_count": 5,
      "total_tokens_used": 2100,
      "estimated_cost": 0.00078,
      "rating": null,
      "feedback": null,
      "created_at": "2026-04-16T14:20:00Z",
      "ended_at": null
    }
  ],
  "total": 2,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

---

## 5. GET `/conversations/{conversation_id}` — Full Chat Messages

### Input

```
GET /api/v1/ai/conversations/f47ac10b-58cc-4372-a567-0e02b2c3d479
```

### Output (200 OK)

```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Hello",
  "context_type": "general",
  "is_active": true,
  "message_count": 3,
  "total_tokens_used": 1250,
  "estimated_cost": 0.00045,
  "rating": null,
  "feedback": null,
  "created_at": "2026-04-17T10:30:00Z",
  "ended_at": null,
  "messages": [
    {
      "id": "11111111-1111-1111-1111-111111111111",
      "conversation_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "user_message": "Hello",
      "ai_response": "Hello! I'm Flora, your medical health assistant...",
      "model_name": "gpt-4o-mini",
      "model_version": null,
      "prompt_tokens": 320,
      "completion_tokens": 167,
      "total_tokens": 487,
      "response_time_ms": 1243,
      "cost": 0.00015,
      "detected_intent": null,
      "detected_entities": null,
      "confidence_score": null,
      "actions_triggered": null,
      "is_error": false,
      "error_message": null,
      "is_helpful": null,
      "feedback": null,
      "created_at": "2026-04-17T10:30:01Z"
    },
    {
      "id": "22222222-2222-2222-2222-222222222222",
      "conversation_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "user_message": "I need a knee replacement doctor",
      "ai_response": "I understand you're looking for a knee replacement specialist...",
      "model_name": "gpt-4o-mini",
      "model_version": null,
      "prompt_tokens": 450,
      "completion_tokens": 230,
      "total_tokens": 680,
      "response_time_ms": 1580,
      "cost": 0.00021,
      "detected_intent": null,
      "detected_entities": null,
      "confidence_score": null,
      "actions_triggered": null,
      "is_error": false,
      "error_message": null,
      "is_helpful": true,
      "feedback": "Very helpful!",
      "created_at": "2026-04-17T10:31:15Z"
    }
  ]
}
```

---

## 6. PATCH `/conversations/{conversation_id}` — Rename Conversation

### Input (Query Parameter)

```
PATCH /api/v1/ai/conversations/f47ac10b-58cc-4372-a567-0e02b2c3d479?title=Knee%20Replacement%20Inquiry
```

| Param  | Type           | Required | Description       |
|--------|----------------|----------|-------------------|
| `title`| string (≤255)  | ✅       | New title         |

### Output (200 OK)

```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "title": "Knee Replacement Inquiry",
  "context_type": "general",
  "is_active": true,
  "message_count": 3,
  "total_tokens_used": 1250,
  "estimated_cost": 0.00045,
  "rating": null,
  "feedback": null,
  "created_at": "2026-04-17T10:30:00Z",
  "ended_at": null
}
```

---

## 7. DELETE `/conversations/{conversation_id}` — Delete One Conversation

### Input

```
DELETE /api/v1/ai/conversations/f47ac10b-58cc-4372-a567-0e02b2c3d479
```

### Output (200 OK)

```json
{
  "message": "Conversation deleted"
}
```

---

## 8. DELETE `/conversations` — Clear All Conversations

### Input

```
DELETE /api/v1/ai/conversations
```

### Output (200 OK)

```json
{
  "message": "All conversations cleared"
}
```

---

## 9. POST `/feedback` — Rate an AI Response

### Input (Request Body)

```json
{
  "log_id": "11111111-1111-1111-1111-111111111111",
  "is_helpful": true,
  "feedback": "Very accurate doctor recommendation!"
}
```

| Field       | Type           | Required | Description                        |
|-------------|----------------|----------|------------------------------------|
| `log_id`    | UUID           | ✅       | The `id` from a message in history |
| `is_helpful`| boolean        | ✅       | Thumbs up / down                   |
| `feedback`  | string (≤1000) | ❌       | Optional text feedback             |

### Output (200 OK)

```json
{
  "message": "Feedback submitted successfully"
}
```

---

## 10. POST `/refresh-knowledge` — Rebuild RAG Knowledge Base (Admin Only)

### Input

```
POST /api/v1/ai/refresh-knowledge
Authorization: Bearer <ADMIN_JWT_TOKEN>
```

No request body needed.

### Output (200 OK)

```json
{
  "message": "Knowledge base rebuilt with 47 documents"
}
```

| Code | Detail              | When                     |
|------|---------------------|--------------------------|
| 401  | Not authenticated   | Missing JWT              |
| 403  | Forbidden           | Non-admin user           |

### What the knowledge base contains

Everything the chatbot is allowed to talk about is embedded here. Nothing else is available to it.

| Source | Indexed when | Link the bot gives |
|---|---|---|
| Doctors | not deleted | `/doctors/{id}` |
| Hospitals | active, not deleted | `/hospitals/{slug}` |
| Departments | not deleted | `/hospitals/{slug}` |
| Treatments | not deleted | `/treatments/{slug}` |
| **Hotels** | active, not deleted | `/hotels/{slug}` |
| **Apartments** | active, not deleted | `/apartments/{slug}` |
| **Restaurants** | active, not deleted | `/restaurants/{slug}` |
| **Medical packages** | active, not deleted | `/packages/{slug}` |
| Admin knowledge documents | active, not deleted | — |
| Platform facts + website sections | always | `/hotels`, `/doctors`, `/contact`, … |

Accommodation and dining records are indexed with their **distance to the nearest hospital**, medical
amenities, and price, so a patient asking "where can I stay near the hospital?" gets ranked, relevant
results rather than a generic list.

> **The knowledge base is an in-memory singleton built once per process.** A hotel, apartment,
> restaurant, or package added through the admin panel will **not** be recommended until
> `POST /api/v1/ai/refresh-knowledge` runs (or the app restarts). Call it after bulk content changes.
> With multiple workers, each worker holds its own copy — restart or refresh them all.

### How the chatbot is kept to website content

Three layers, in order:

1. **Retrieval.** Every answer is grounded in the documents retrieved for that message. The system
   prompt states that names, prices, ratings, and links may come *only* from the retrieved block, that
   URLs must never be guessed or constructed, and that a missing match must be admitted rather than
   filled in with a plausible example.
2. **Scope gate.** If the best match in the whole knowledge base scores below `RAG_SCOPE_THRESHOLD`,
   the question is treated as off-topic. The assistant is switched to a restricted prompt that only
   permits a one-line redirect, and the response comes back with `in_scope: false`. Greetings and small
   talk land here too and get a friendly "here's what I can help with" reply.
3. **Refusal rules.** The main prompt lists what is in scope and what is not, and instructs the
   assistant to refuse out-of-scope requests even when the user insists, role-plays, claims to be
   staff, or says the rules changed, and never to reveal its instructions.

Tuning knobs in `.env`:

| Setting | Default | Effect |
|---|---|---|
| `RAG_TOP_K` | 8 | How many documents are fed as context. Raise for more variety across service types. |
| `RAG_SIMILARITY_THRESHOLD` | 0.3 | Minimum score to be quoted as a result. Raise to cut weak matches. |
| `RAG_SCOPE_THRESHOLD` | 0.15 | Below this, the question is off-topic. **Raise to make the bot stricter**, lower if it wrongly refuses real questions. |

Layers 1 and 3 are prompt-level and therefore strong but not absolute; layer 2 is deterministic code.
If you need a hard guarantee on a specific topic, add it to the scope gate rather than the prompt.

---

## Admin Knowledge Documents — `/api/v1/admin/knowledge`

These endpoints let admins add custom documents to the RAG chatbot's knowledge base.

### 11. POST `/admin/knowledge` — Create Knowledge Document (Admin)

#### Input (Request Body)

```json
{
  "title": "Visa Requirements for Medical Tourism in India",
  "category": "travel",
  "content": "International patients traveling to India for medical treatment can apply for a Medical Visa (M-Visa). Requirements: 1) Passport valid for at least 6 months, 2) Letter from the Indian hospital confirming treatment, 3) Medical records supporting the need for treatment, 4) Proof of sufficient funds. Processing time: 5-7 business days. The M-Visa allows multiple entries for up to 1 year and can be extended.",
  "summary": "Guide to obtaining an Indian Medical Visa for treatment",
  "tags": ["visa", "travel", "india", "medical tourism"],
  "source_url": "https://indianvisaonline.gov.in/medical",
  "is_active": true,
  "sort_order": 0,
  "metadata_extra": null
}
```

| Field           | Type           | Required | Description                                              |
|-----------------|----------------|----------|----------------------------------------------------------|
| `title`         | string (≤300)  | ✅       | Document title                                           |
| `category`      | string (≤50)   | ❌       | `general`, `treatment`, `policy`, `faq`, `procedure`, `pricing`, `travel`, `aftercare` |
| `content`       | string (≥10)   | ✅       | Full document content — fed to the RAG chatbot           |
| `summary`       | string         | ❌       | Short summary for admin list view                        |
| `tags`          | string[]       | ❌       | Searchable tags                                          |
| `source_url`    | string (≤500)  | ❌       | Reference URL                                            |
| `is_active`     | boolean        | ❌       | Default `true`. Set `false` to exclude from RAG          |
| `sort_order`    | integer        | ❌       | Display ordering (lower = first)                         |
| `metadata_extra`| object         | ❌       | Any extra metadata                                       |

#### Output (201 Created)

```json
{
  "id": "c1d2e3f4-a5b6-7890-cdef-1234567890ab",
  "title": "Visa Requirements for Medical Tourism in India",
  "category": "travel",
  "content": "International patients traveling to India for medical treatment...",
  "summary": "Guide to obtaining an Indian Medical Visa for treatment",
  "tags": ["visa", "travel", "india", "medical tourism"],
  "source_url": "https://indianvisaonline.gov.in/medical",
  "is_active": true,
  "sort_order": 0,
  "metadata_extra": null,
  "created_at": "2026-04-17T12:00:00Z",
  "updated_at": "2026-04-17T12:00:00Z",
  "created_by": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
}
```

### 12. GET `/admin/knowledge` — List Knowledge Documents (Admin)

#### Input (Query Parameters)

```
GET /api/v1/admin/knowledge?page=1&page_size=20&category=travel&active_only=true&search=visa
```

| Param        | Type       | Default | Description                  |
|--------------|------------|---------|------------------------------|
| `page`       | int (≥1)   | 1       | Page number                  |
| `page_size`  | int (1-100)| 20      | Results per page             |
| `category`   | string     | —       | Filter by category           |
| `active_only`| boolean    | false   | Only active documents        |
| `search`     | string     | —       | Search in title and content  |

#### Output (200 OK)

```json
{
  "items": [
    {
      "id": "c1d2e3f4-a5b6-7890-cdef-1234567890ab",
      "title": "Visa Requirements for Medical Tourism in India",
      "category": "travel",
      "summary": "Guide to obtaining an Indian Medical Visa for treatment",
      "tags": ["visa", "travel", "india", "medical tourism"],
      "is_active": true,
      "sort_order": 0,
      "created_at": "2026-04-17T12:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

### 13. GET `/admin/knowledge/categories` — List Categories (Admin)

```
GET /api/v1/admin/knowledge/categories
```

#### Output (200 OK)

```json
["aftercare", "faq", "policy", "pricing", "travel", "treatment"]
```

### 14. GET `/admin/knowledge/{doc_id}` — Get One Document (Admin)

```
GET /api/v1/admin/knowledge/c1d2e3f4-a5b6-7890-cdef-1234567890ab
```

#### Output (200 OK)

Same as POST create response above.

### 15. PUT `/admin/knowledge/{doc_id}` — Update Document (Admin)

#### Input (Request Body — all fields optional)

```json
{
  "title": "Updated: Visa Requirements for Medical Tourism",
  "is_active": false
}
```

#### Output (200 OK)

Full updated document (same shape as create response).

### 16. DELETE `/admin/knowledge/{doc_id}` — Delete Document (Admin)

```
DELETE /api/v1/admin/knowledge/c1d2e3f4-a5b6-7890-cdef-1234567890ab
```

#### Output (204 No Content)

No response body.

---

## cURL Examples

### Chat (New Conversation)

```bash
curl -X POST http://localhost:8000/api/v1/ai/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}'
```

### Chat (Continue Conversation)

```bash
curl -X POST http://localhost:8000/api/v1/ai/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "I need a knee replacement", "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}'
```

### Analyze Report

```bash
curl -X POST http://localhost:8000/api/v1/ai/analyze-report \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"report_text": "Diagnosis: Grade IV osteoarthritis right knee..."}'
```

### List Conversations (Sidebar)

```bash
curl http://localhost:8000/api/v1/ai/conversations?page=1&page_size=20 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Search Conversations

```bash
curl "http://localhost:8000/api/v1/ai/conversations?search=knee" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Get Conversation Messages

```bash
curl http://localhost:8000/api/v1/ai/conversations/CONVERSATION_UUID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Rename Conversation

```bash
curl -X PATCH "http://localhost:8000/api/v1/ai/conversations/CONVERSATION_UUID?title=My%20Knee%20Chat" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Delete One Conversation

```bash
curl -X DELETE http://localhost:8000/api/v1/ai/conversations/CONVERSATION_UUID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Clear All Conversations

```bash
curl -X DELETE http://localhost:8000/api/v1/ai/conversations \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Submit Feedback

```bash
curl -X POST http://localhost:8000/api/v1/ai/feedback \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"log_id": "LOG_UUID", "is_helpful": true, "feedback": "Great suggestion!"}'
```

### Upload Report (Image)

```bash
curl -X POST http://localhost:8000/api/v1/ai/upload-report \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/path/to/knee-xray.jpg" \
  -F "message=What does this X-ray show?"
```

### Upload Report (PDF)

```bash
curl -X POST http://localhost:8000/api/v1/ai/upload-report \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/path/to/blood-report.pdf" \
  -F "session_id=a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

### Rebuild Knowledge Base (Admin)

```bash
curl -X POST http://localhost:8000/api/v1/ai/refresh-knowledge \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

### Create Knowledge Document (Admin)

```bash
curl -X POST http://localhost:8000/api/v1/admin/knowledge \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Post-Surgery Care Guide",
    "category": "aftercare",
    "content": "After your surgery at Flora Medical partner hospitals...",
    "tags": ["aftercare", "recovery", "post-surgery"]
  }'
```

---

## Frontend Integration Flow

```
1. Page Load
   └─ GET /ai/conversations              → populate sidebar chat list

2. Click "New Chat"
   └─ POST /ai/chat {message, session_id: null}
      └─ Returns: response, session_id, doctor_suggestions, follow_up_questions
      └─ Store session_id for subsequent messages

3. Send Follow-up Message
   └─ POST /ai/chat {message, session_id: "stored_id"}
      └─ Returns: response + updated suggestions + follow_up_questions

4. Click Follow-up Question Chip
   └─ POST /ai/chat {message: "clicked question text", session_id: "stored_id"}

5. Click "View Profile" on Doctor Card
   └─ Navigate to /doctors/{doctor_id}

6. Click "Book →" on Doctor Card
   └─ Navigate to /doctors/{doctor_id}/book or /appointments/new?doctor_id={id}

7. Search Chats (sidebar search)
   └─ GET /ai/conversations?search=query

8. Delete Chat
   └─ DELETE /ai/conversations/{id}

9. Clear All Chats
   └─ DELETE /ai/conversations

10. Thumbs Up/Down on AI Response
    └─ POST /ai/feedback {log_id, is_helpful}

11. Upload Report File (📎 button — image or PDF)
    └─ POST /ai/upload-report (multipart/form-data: file + optional message)
    └─ Display report_analysis + recommended_doctors cards
    └─ Optionally feed analysis summary into /ai/chat for follow-up conversation

12. Paste Report Text (no file)
    └─ POST /ai/analyze-report {report_text}
    └─ OR POST /ai/chat {message: "analyze this", report_text: "..."}
```
