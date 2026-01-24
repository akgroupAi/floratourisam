# Flora Medical - Comprehensive API Documentation

Complete reference for the Medical Tourism Platform API v1.

## Base URL
`http://localhost:8000/api/v1`

## Authentication
Add header to protected requests: `Authorization: Bearer <access_token>`

---

## 🔔 Notifications API

### List Notifications
`GET /notifications`

**Query Params:** `page`, `page_size`, `is_read`

**Response:**
```json
{
  "notifications": [
    {
      "id": "uuid",
      "title": "Appointment Confirmed",
      "message": "Your consultation with Dr. Smith is confirmed.",
      "notification_type": "success",
      "action_url": "/appointments/123",
      "is_read": false,
      "created_at": "2024-03-20T10:00:00Z"
    }
  ],
  "total": 5,
  "unread_count": 2
}
```

### Get Unread Count
`GET /notifications/unread-count`

**Response:** `{"unread_count": 2}`

### Mark Read
`POST /notifications/mark-read`
```json
{
  "notification_ids": ["uuid1", "uuid2"]
}
```

### Mark All Read
`POST /notifications/mark-all-read`

---

## 📅 Events & Calendar API

### List Events
`GET /events`

**Query Params:** `start_date`, `end_date`, `event_type`, `status`

### Calendar View
`GET /events/calendar`

**Query:** `start_date=2024-03-01&end_date=2024-03-31&event_types=consultation,travel`

**Response:**
```json
{
  "start_date": "2024-03-01",
  "end_date": "2024-03-31",
  "events": [
    {
      "id": "uuid",
      "title": "Flight to Delhi",
      "start_time": "2024-03-15T10:00:00Z",
      "end_time": "2024-03-15T14:00:00Z",
      "event_type": "travel",
      "color": "#3b82f6"
    }
  ]
}
```

### Create Event
`POST /events`
```json
{
  "title": "Follow-up Call",
  "event_type": "follow_up",
  "start_time": "2024-03-20T15:00:00Z",
  "end_time": "2024-03-20T15:30:00Z",
  "location_type": "online",
  "reminders": [{"type": "email", "minutes_before": 30}]
}
```

### Reschedule Event
`POST /events/{id}/reschedule`
```json
{
  "new_start_time": "2024-03-21T15:00:00Z"
}
```

---

## 📧 Email System API (Admin)

### List Templates
`GET /email/templates`

### Create Template
`POST /email/templates`
```json
{
  "name": "Welcome Email",
  "slug": "welcome-email",
  "subject": "Welcome to Flora Medical, {{name}}!",
  "body_html": "<h1>Welcome {{name}}</h1><p>Thanks for joining...</p>",
  "category": "auth",
  "variables": ["name", "verify_link"]
}
```

### Send Email
`POST /email/send`
```json
{
  "template_slug": "welcome-email",
  "to_email": "user@example.com",
  "variables": {
    "name": "John",
    "verify_link": "https://..."
  }
}
```

### Email Logs
`GET /email/logs`

---

## ⚙️ Configuration API

### Get Public Configs
`GET /config/public`

**Response:**
```json
{
  "SITE_NAME": "Flora Medical",
  "STRIPE_PUBLIC_KEY": "pk_test_...",
  "SUPPORT_EMAIL": "help@flora.com"
}
```

### List Configs (Admin)
`GET /config`

### Update Config (Admin)
`PUT /config/SITE_NAME`
```json
{
  "value": {"value": "New Site Name"}
}
```

### Bulk Update (Admin)
`POST /config/bulk-update`
```json
{
  "configs": {
    "SITE_NAME": "Flora Medical",
    "MAINTENANCE_MODE": false
  }
}
```

### Init Defaults (Super Admin)
`POST /config/init-defaults`

---

## 📂 Document Management API

### List Documents
`GET /documents`

**Query Params:** `category`, `entity_type`

### Search & stats
`GET /documents/stats`

**Response:**
```json
{
  "total_documents": 10,
  "total_size_bytes": 5242880,
  "documents_by_category": {
    "medical_record": 5,
    "invoice": 2
  }
}
```

### Upload Document
`POST /documents`

**Form Data:**
- `file`: (Binary)
- `category`: `medical_record`
- `title`: `Lab Report`
- `entity_type`: `consultation`
- `entity_id`: `uuid`

### Share Document
`POST /documents/{id}/share`
```json
{
  "shared_with_email": "doctor@hospital.com",
  "permission": "view",
  "expires_at": "2024-03-25T00:00:00Z",
  "password": "optional-secret"
}
```

### Access Shared Doc
`GET /documents/shared/{token}?password=secret`

---

## 🏥 Public Pages & CMS API

### Pages Content
- `GET /pages/home`
- `GET /pages/services`
- `GET /pages/destinations`
- `GET /pages/about`
- `GET /pages/contact`

### Lead Generation
- `POST /leads/quote`
- `POST /leads/contact`
- `POST /leads/newsletter`

---

## 🔐 Core Resources API

### Auth
- `POST /auth/login`
- `POST /auth/register`
- `POST /auth/refresh`

### Users
- `GET /users/me`
- `PUT /users/me`

### Doctors
- `GET /doctors`
- `GET /doctors/{id}`

### Bookings
- `GET /bookings`
- `POST /bookings/hotel`
- `POST /bookings/restaurant`

### Chat
- `WS /chat/ws/{room_id}`
- `POST /ai/chat`
