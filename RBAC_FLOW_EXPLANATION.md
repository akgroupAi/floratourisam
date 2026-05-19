# RBAC System: Current Flow & How It Works

## 🔄 Complete RBAC Flow Overview

Here's how the **entire RBAC system works** from start to finish:

---

## 📊 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FLORA RBAC SYSTEM                             │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ LAYER 1: USER AUTHENTICATION (JWT Token)                                 │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  User Login:                                                             │
│  ├─ Email: john@hotel.com                                               │
│  ├─ Password: ••••••••                                                   │
│  └─ Token Generated: eyJhbGciOiJIUzI1NiIs...                            │
│                                                                           │
│  Token Contains:                                                         │
│  ├─ user_id: uuid                                                        │
│  ├─ email: john@hotel.com                                                │
│  ├─ role: hotel_manager                                                  │
│  └─ permissions: {read, create, update}                                  │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ LAYER 2: REQUEST PROCESSING                                              │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Frontend sends API Request:                                             │
│  ├─ GET /api/v1/admin/hotels                                             │
│  ├─ Headers: Authorization: Bearer <token>                               │
│  └─ Body: (query params, filters, etc.)                                  │
│                                                                           │
│  Backend receives request:                                               │
│  ├─ Step 1: Verify token is valid                                        │
│  ├─ Step 2: Extract user_id & role from token                            │
│  ├─ Step 3: Check if user is authenticated                               │
│  └─ Step 4: Proceed to permission check                                  │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ LAYER 3: PERMISSION CHECKING (RBAC)                                      │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Backend checks RBAC rules:                                              │
│  ├─ Role check: Is user role = hotel_manager?                            │
│  │  └─ If NO → Return 403 Forbidden                                      │
│  ├─ Resource check: Does role have permission for this resource?         │
│  │  └─ Permission matrix: hotels → can_read = true?                      │
│  │     └─ If NO → Return 403 Forbidden                                   │
│  ├─ Scope check: Is user assigned to this specific hotel?                │
│  │  └─ manager_id = user_id?                                             │
│  │     └─ If NO → Return 403 Forbidden                                   │
│  └─ Action allowed? → Proceed to data access                             │
│                                                                           │
│  Example Decision Tree:                                                  │
│  ├─ Token valid? YES ✓                                                   │
│  ├─ User authenticated? YES ✓                                            │
│  ├─ Role is hotel_manager? YES ✓                                         │
│  ├─ Role can read hotels? YES ✓                                          │
│  ├─ Assigned to this hotel? YES ✓                                        │
│  └─ Result: ALLOW REQUEST ✓                                              │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ LAYER 4: DATA ACCESS & FILTERING                                         │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Database Query with Automatic Filtering:                                │
│  ├─ Original query: SELECT * FROM hotels                                 │
│  ├─ Applied filter: WHERE manager_id = 'john-uuid'                       │
│  ├─ Result: Only hotel(s) managed by john                                │
│  │                                                                        │
│  │  Hotels in DB:                                                        │
│  │  ├─ Grand Plaza (manager: john) ✓ RETURNED                            │
│  │  ├─ Riverside (manager: sarah) ✗ FILTERED OUT                         │
│  │  ├─ Beach House (manager: alex) ✗ FILTERED OUT                        │
│  │  └─ Downtown Suites (no manager) ✗ FILTERED OUT                       │
│  │                                                                        │
│  └─ Response returns: [Grand Plaza Hotel only]                           │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ LAYER 5: RESPONSE & LOGGING                                              │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Response sent to frontend:                                              │
│  ├─ Status: 200 OK                                                       │
│  ├─ Data: {hotels: [{id, name, manager, ...}]}                           │
│  └─ Headers: Content-Type: application/json                              │
│                                                                           │
│  Audit Log Entry created:                                                │
│  ├─ actor_id: john-uuid                                                  │
│  ├─ action: view_hotels                                                  │
│  ├─ target_type: hotel                                                   │
│  ├─ timestamp: 2026-04-25 10:30:45 UTC                                   │
│  ├─ meta_data: {resource: hotels, count: 1}                              │
│  └─ status: success                                                      │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 🔐 Step-by-Step Flow: Hotel Manager Views Bookings

### **Scenario: John (Hotel Manager) logs in and views bookings**

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1: USER LOGIN                                                   │
└─────────────────────────────────────────────────────────────────────┘

Frontend (Browser):
  Input: john@myhotel.com + password
  Request: POST /api/v1/auth/login
  Body: {email, password}
         ↓
Backend (Server):
  1. Hash password
  2. Query DB: SELECT * FROM users WHERE email='john@myhotel.com'
  3. Compare hashed passwords
  4. Generate JWT token:
     {
       "user_id": "john-uuid",
       "email": "john@myhotel.com",
       "role": "hotel_manager",
       "hotel_id": "grand-plaza-uuid"
     }
  5. Return token
         ↓
Frontend:
  Receives: {token: "eyJhbGci...", expires_in: 1800}
  Stores token in localStorage
  Redirects to: /dashboard
```

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 2: DASHBOARD LOAD (GET HOTELS)                                 │
└─────────────────────────────────────────────────────────────────────┘

Frontend (Browser):
  Page loads: /dashboard
  React component: useEffect(() => { fetchHotels() })
  Request: GET /api/v1/admin/hotels
  Headers: 
    Authorization: Bearer eyJhbGci...
    Content-Type: application/json
         ↓
Backend - REQUEST HANDLER:
  1. Extract token from Authorization header
  2. Verify token signature (valid? yes ✓)
  3. Decode token:
     {
       user_id: "john-uuid",
       role: "hotel_manager",
       hotel_id: "grand-plaza-uuid"
     }
         ↓
Backend - PERMISSION CHECK:
  1. Is endpoint protected? YES (requires RequireAdmin)
  2. Is user authenticated? YES ✓
  3. User role = hotel_manager?
     - Check: Does user have @RequireAdmin dependency?
     - NO... Wait, let me check RequireHotelManager
     - Is user admin? NO, but is hotel_manager? YES ✓
  4. Can hotel_manager read hotels?
     - Query: SELECT permissions FROM roles 
       WHERE name = 'hotel_manager'
     - Check: hotels → can_read = TRUE? YES ✓
         ↓
Backend - DATA ACCESS:
  Original Query:
    SELECT * FROM hotels
  
  Modified Query (with filter):
    SELECT * FROM hotels 
    WHERE manager_id = 'john-uuid'
    
  Database Results:
    ├─ Grand Plaza Hotel (manager_id: john-uuid) ✓
    ├─ Riverside Resort (manager_id: sarah-uuid) ✗ FILTERED
    ├─ Beach House (manager_id: alex-uuid) ✗ FILTERED
    └─ Downtown Suites (manager_id: NULL) ✗ FILTERED
    
  Final Result: [Grand Plaza Hotel]
         ↓
Backend - AUDIT LOGGING:
  Create audit log entry:
  {
    actor_id: "john-uuid",
    action: "GET /api/v1/admin/hotels",
    target_type: "hotel",
    target_id: "grand-plaza-uuid",
    meta_data: {
      count: 1,
      filter: "manager_id = john-uuid"
    },
    status: "success",
    created_at: "2026-04-25T10:30:45Z"
  }
         ↓
Backend - RESPONSE:
  Status: 200 OK
  Body:
  {
    "items": [
      {
        "id": "grand-plaza-uuid",
        "name": "Grand Plaza Hotel",
        "city": "New York",
        "manager_id": "john-uuid",
        "manager_name": "John Smith"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 50
  }
         ↓
Frontend:
  Receives response
  Renders: Hotel card with "Grand Plaza Hotel"
  John sees: Only his hotel ✓
```

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 3: VIEW BOOKINGS FOR HOTEL                                     │
└─────────────────────────────────────────────────────────────────────┘

Frontend (Browser):
  John clicks: Grand Plaza Hotel
  Request: GET /api/v1/admin/hotels/{hotel_id}/bookings
  Headers: Authorization: Bearer <token>
         ↓
Backend - PERMISSION CHECK:
  1. Is user authenticated? YES ✓
  2. Is user a hotel_manager? YES ✓
  3. Can hotel_manager read bookings? YES ✓
  4. Is this hotel assigned to user?
     - Query: SELECT manager_id FROM hotels WHERE id = {hotel_id}
     - Result: manager_id = 'john-uuid'
     - Match? YES ✓
         ↓
Backend - DATA ACCESS:
  Query:
    SELECT b.* FROM bookings b
    JOIN hotels h ON b.hotel_id = h.id
    WHERE b.hotel_id = '{hotel_id}' 
    AND h.manager_id = 'john-uuid'
    
  Results:
    Booking #123: John's hotel ✓
    Booking #124: John's hotel ✓
    Booking #125: John's hotel ✓
    (Other hotel bookings: automatically excluded)
         ↓
Backend - AUDIT LOG:
  {
    actor_id: "john-uuid",
    action: "GET /api/v1/admin/hotels/{id}/bookings",
    target_type: "booking",
    meta_data: {
      hotel_id: "grand-plaza-uuid",
      count: 3
    },
    status: "success"
  }
         ↓
Frontend:
  John sees: 3 bookings for his hotel
  Can't see: Bookings from other hotels
```

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 4: ATTEMPT UNAUTHORIZED ACCESS (SECURITY TEST)                 │
└─────────────────────────────────────────────────────────────────────┘

Frontend (Attacker/Hacker):
  Notices URL: /api/v1/admin/hotels/grand-plaza-uuid/bookings
  
  Tries: /api/v1/admin/hotels/competitor-hotel-uuid/bookings
  Request: GET /api/v1/admin/hotels/competitor-hotel-uuid/bookings
  Headers: Authorization: Bearer john-token
         ↓
Backend - PERMISSION CHECK:
  1. Is user authenticated? YES ✓
  2. Can user read bookings? YES ✓
  3. Is competitor-hotel assigned to john?
     - Query: SELECT manager_id FROM hotels 
       WHERE id = 'competitor-hotel-uuid'
     - Result: manager_id = 'sarah-uuid'
     - Match? NO ✗
         ↓
Backend - SECURITY BLOCK:
  ❌ ACCESS DENIED
  Status: 403 Forbidden
  Message: "You don't have permission to access this resource"
         ↓
Backend - AUDIT LOG (SECURITY EVENT):
  {
    actor_id: "john-uuid",
    action: "UNAUTHORIZED_ACCESS_ATTEMPT",
    target_type: "booking",
    target_id: "competitor-hotel-uuid",
    meta_data: {
      attempt: "Cross-hotel access",
      result: "BLOCKED"
    },
    status: "unauthorized",
    severity: "WARNING"
  }
         ↓
Frontend:
  Receives: 403 error
  Shows: "Access denied"
  John: Can't see competitor's data ✓
  System: Logged attempt for security review
```

---

## 🏢 Complete Flow: Hotel Owner Management Journey

### **Day 1: Owner Requests Manager**

```
1. OWNER REQUEST
   └─ Email to support@floratourism.com
      "Add manager for my hotel
       Email: maria@myhotel.com
       Hotel: Grand Plaza
       Permissions: bookings, rooms"

2. FLORA ADMIN RECEIVES REQUEST
   └─ Checks RBAC Admin Dashboard
      Verifies: Hotel exists, email valid

3. FLORA ADMIN CREATES MANAGER ACCOUNT
   └─ API Call: POST /api/v1/admin/rbac/user-roles
      Body: {
        email: maria@myhotel.com,
        role_id: hotel-manager-uuid,
        full_name: Maria Lopez
      }
      Response: Account created ✓
      
4. FLORA ADMIN ASSIGNS HOTEL
   └─ API Call: PATCH /api/v1/admin/hotels/{grand-plaza-id}/manager
      Body: {
        manager_user_id: maria-uuid
      }
      Response: Manager assigned ✓
      
5. AUDIT LOG ENTRIES CREATED
   └─ Entry 1: "Created user role for maria@myhotel.com"
      Entry 2: "Assigned maria to Grand Plaza Hotel"
      Both entries: actor_id = flora-admin-uuid

6. MARIA RECEIVES INVITATION EMAIL
   └─ From: support@floratourism.com
      Subject: "Welcome to Flora - Hotel Manager"
      Link: Set password [expires 24h]
      
7. MARIA SETS UP ACCOUNT
   └─ Clicks link
      Creates password
      Confirms email
      
8. MARIA LOGS IN
   └─ POST /api/v1/auth/login
      JWT token generated with role: hotel_manager
      
9. MARIA VIEWS DASHBOARD
   └─ GET /api/v1/admin/hotels
      Backend filters: WHERE manager_id = maria-uuid
      Result: Only Grand Plaza Hotel shown
      
10. AUDIT LOG: LOGIN & DASHBOARD VIEW
    └─ Login: actor_id = maria, action = LOGIN_SUCCESS
       Dashboard: actor_id = maria, action = GET_HOTELS, count = 1
```

---

## 🔄 Complete RBAC Flow Summary

### **5 Key Layers:**

```
┌─ LAYER 1: AUTHENTICATION ─────────────────────────────┐
│ User logs in → Token generated → Token stored in app   │
└───────────────────────────────────────────────────────┘
                        ↓
┌─ LAYER 2: REQUEST VALIDATION ─────────────────────────┐
│ Check token is valid → Extract user info → Verify JWT  │
└───────────────────────────────────────────────────────┘
                        ↓
┌─ LAYER 3: PERMISSION CHECK (RBAC) ────────────────────┐
│ Check role → Check resource permission → Check scope   │
└───────────────────────────────────────────────────────┘
                        ↓
┌─ LAYER 4: DATA FILTERING ─────────────────────────────┐
│ Apply WHERE clause → Filter results → Return safe data │
└───────────────────────────────────────────────────────┘
                        ↓
┌─ LAYER 5: LOGGING & RESPONSE ─────────────────────────┐
│ Create audit entry → Send response → Frontend renders  │
└───────────────────────────────────────────────────────┘
```

---

## 📋 Current Endpoints & How They Work

### **GET /api/v1/admin/rbac/roles**
```
Purpose: List all roles
Flow:
  1. Verify admin user ✓
  2. Query: SELECT * FROM roles WHERE is_deleted = FALSE
  3. Count users per role
  4. Return with pagination
  5. Log audit entry
```

### **POST /api/v1/admin/rbac/user-roles**
```
Purpose: Assign role to user
Flow:
  1. Verify admin user ✓
  2. Check user exists
  3. Check role exists
  4. Update user.role field
  5. Create audit log: "Assigned role to user"
  6. Return success message
```

### **PATCH /api/v1/admin/hotels/{id}/manager**
```
Purpose: Assign manager to hotel
Flow:
  1. Verify admin user ✓
  2. Check hotel exists
  3. Check manager exists
  4. Check manager is hotel_manager role
  5. Update hotel.manager_id = user_id
  6. Create audit log: "Assigned manager to hotel"
  7. Return success message
```

### **GET /api/v1/admin/hotels** (Hotel Manager)
```
Purpose: List hotels for this manager
Flow:
  1. Verify user is authenticated ✓
  2. Check role = hotel_manager ✓
  3. Apply filter: WHERE manager_id = current_user_id
  4. Query: SELECT * FROM hotels WHERE manager_id = {user_id}
  5. Return filtered results (only their hotels)
  6. Log audit entry
```

---

## 🛡️ Security Decision Tree

```
Request comes in
    ↓
Is token present?
  ├─ NO → Return 401 Unauthorized
  └─ YES ↓
  
Is token valid?
  ├─ NO → Return 401 Unauthorized
  └─ YES ↓
  
Is endpoint public?
  ├─ YES → Allow ✓
  └─ NO ↓
  
Does user have required role?
  ├─ NO → Return 403 Forbidden
  └─ YES ↓
  
Does role have resource permission?
  ├─ NO → Return 403 Forbidden
  └─ YES ↓
  
Is user assigned to this specific resource?
  ├─ NO → Return 403 Forbidden
  └─ YES ↓
  
Apply data filtering
  ├─ Query with WHERE clause
  └─ Return safe filtered data
  
Log audit entry
  └─ Record action for compliance
```

---

## 📊 Real-Time Example: Competing Hotels Managers

### **Scenario: John (Grand Plaza) vs Sarah (Riverside)**

```
TIME: 10:00 AM

John logs in:
  Token: {user_id: john, role: hotel_manager, hotel_id: grand-plaza}
  Dashboard: Shows Grand Plaza only ✓
  John's bookings visible: 45 bookings
  
Sarah logs in:
  Token: {user_id: sarah, role: hotel_manager, hotel_id: riverside}
  Dashboard: Shows Riverside only ✓
  Sarah's bookings visible: 32 bookings

TIME: 10:05 AM

John tries to access Riverside bookings:
  URL: /api/v1/admin/hotels/riverside-uuid/bookings
  Backend checks: Is riverside assigned to john?
  Result: NO
  Response: 403 Forbidden ✗
  Audit: Recorded unauthorized attempt

Sarah tries to access Grand Plaza bookings:
  URL: /api/v1/admin/hotels/grand-plaza-uuid/bookings
  Backend checks: Is grand-plaza assigned to sarah?
  Result: NO
  Response: 403 Forbidden ✗
  Audit: Recorded unauthorized attempt

TIME: 10:10 AM

Flora Admin views audit logs:
  Entry 1: "John unauthorized access attempt at 10:05"
  Entry 2: "Sarah unauthorized access attempt at 10:05"
  Admin: "All good, both blocked ✓"
```

---

## ✅ Key Points of Current Flow

1. **Authentication First** - Token validated before anything else
2. **Role-Based Check** - Does role have permission?
3. **Scope Check** - Is user assigned to this resource?
4. **Data Filtering** - Backend filters results automatically
5. **Audit Logging** - Every action logged for compliance
6. **Error Handling** - Clear 403 errors for unauthorized access
7. **No Manual Work** - System enforces rules automatically

**Result**: Complete security from user login to data access! 🔐

