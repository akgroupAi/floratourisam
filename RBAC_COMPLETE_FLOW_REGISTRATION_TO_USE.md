# Complete RBAC System: Registration to Flow Explanation

## 📌 Complete Journey: From Registration to Daily Use

---

## 🚀 PART 1: MANAGER REGISTRATION (Step-by-Step)

### **Step 1: Hotel Owner Requests Manager**

```
WHAT HAPPENS:
Hotel Owner sends request to Flora Support

Email Template:
┌─────────────────────────────────────────────────────┐
│ To: support@floratourism.com                         │
│ Subject: Add Manager for My Hotel                    │
│                                                      │
│ Hi Flora Support,                                    │
│                                                      │
│ I need to add a manager for my hotel.               │
│ Manager Name: John Smith                            │
│ Manager Email: john@myhotel.com                     │
│ Hotel Name: Grand Plaza Hotel                       │
│ Permissions Needed: Bookings, Rooms, Pricing        │
│                                                      │
│ Thanks,                                              │
│ Hotel Owner                                          │
└─────────────────────────────────────────────────────┘

STATUS: REQUEST_RECEIVED ⏳
```

---

### **Step 2: Flora Admin Verifies Request**

```
WHAT HAPPENS:
Flora Admin logs into Admin Dashboard
Goes to: RBAC Admin → User Assignments

CHECKS:
├─ Is hotel "Grand Plaza" in database? YES ✓
├─ Is email valid? YES ✓
├─ Is role "hotel_manager" available? YES ✓
├─ Does user already exist? NO ✓
└─ All checks passed? YES ✓

DECISION: APPROVED ✅

STATUS: VERIFIED_AND_APPROVED ✅
```

---

### **Step 3: Flora Admin Creates User Account**

```
WHAT HAPPENS:
Flora Admin clicks: "+ Assign User"

FORM FILLED:
├─ Email: john@myhotel.com
├─ Full Name: John Smith
├─ Role: hotel_manager (dropdown)
└─ Click: "Send Invite"

BACKEND PROCESSING:
1. Check email not already used
2. Create user record in database:
   {
     user_id: "john-uuid-12345",
     email: "john@myhotel.com",
     full_name: "John Smith",
     role: "hotel_manager",
     is_active: true,
     password: null,  // Password set on first login
     created_at: "2026-04-25T10:00:00Z",
     created_by: "admin-uuid"
   }
3. Create audit log entry:
   {
     action: "CREATE_USER",
     actor: "admin-uuid",
     target: "john-uuid-12345",
     metadata: {role: "hotel_manager"}
   }
4. Send invite email
5. Return success message

RESPONSE:
Status: 201 Created
{
  "message": "User account created for john@myhotel.com",
  "user_id": "john-uuid-12345",
  "role": "hotel_manager"
}

DATABASE STATE:
┌─────────────────────────────────┐
│ users table                      │
├─────────────────────────────────┤
│ id: john-uuid-12345              │
│ email: john@myhotel.com          │
│ role: hotel_manager              │
│ is_active: true                  │
│ password_hash: null              │
└─────────────────────────────────┘

STATUS: ACCOUNT_CREATED ✅
```

---

### **Step 4: Flora Admin Assigns Hotel to Manager**

```
WHAT HAPPENS:
Flora Admin goes to: RBAC Admin → Entity Assignments → Hotels

FINDS HOTEL:
├─ Hotel: Grand Plaza Hotel
├─ Current Manager: NULL (unassigned)
├─ Click: "Assign Manager"
└─ Dialog opens

SELECTS MANAGER:
├─ Dropdown shows all hotel_manager users
├─ Selects: John Smith
├─ Click: "Confirm"

BACKEND PROCESSING:
1. Verify hotel exists
2. Verify user exists and has hotel_manager role
3. Update hotel record:
   {
     hotel_id: "grand-plaza-uuid",
     manager_id: "john-uuid-12345"  // Changed from NULL
   }
4. Create audit log:
   {
     action: "ASSIGN_MANAGER",
     actor: "admin-uuid",
     target_type: "hotel",
     target_id: "grand-plaza-uuid",
     metadata: {
       manager_id: "john-uuid-12345",
       manager_name: "John Smith"
     }
   }
5. Return success

RESPONSE:
Status: 200 OK
{
  "message": "Manager assigned to Grand Plaza Hotel",
  "hotel_id": "grand-plaza-uuid",
  "manager_id": "john-uuid-12345"
}

DATABASE STATE:
┌─────────────────────────────────┐
│ hotels table                     │
├─────────────────────────────────┤
│ id: grand-plaza-uuid             │
│ name: Grand Plaza Hotel          │
│ city: New York                   │
│ manager_id: john-uuid-12345 ✓    │
└─────────────────────────────────┘

STATUS: HOTEL_ASSIGNED ✅
```

---

### **Step 5: Invite Email Sent to Manager**

```
WHAT EMAIL JOHN RECEIVES:

FROM: support@floratourism.com
TO: john@myhotel.com
SUBJECT: Welcome to Flora - Hotel Manager Invitation

BODY:
┌─────────────────────────────────────────────────────┐
│ Hi John,                                             │
│                                                      │
│ Welcome to Flora Tourism Platform! 🎉               │
│                                                      │
│ You've been invited to manage:                       │
│ 🏨 Grand Plaza Hotel (New York)                     │
│                                                      │
│ Set Your Password:                                   │
│ Click this link to set your password:               │
│ https://flora.com/auth/set-password?token=xyz...   │
│                                                      │
│ ⏰ This link expires in 24 hours                    │
│                                                      │
│ Once activated, you can:                            │
│ ✓ View all guest bookings                          │
│ ✓ Manage room availability                         │
│ ✓ Update room pricing                              │
│ ✓ Check in/out guests                              │
│ ✓ View team activity                               │
│                                                      │
│ Questions? Contact: support@floratourism.com        │
│                                                      │
│ Welcome aboard! 🚀                                  │
│ Flora Support Team                                   │
└─────────────────────────────────────────────────────┘

EMAIL STATUS: SENT ✅
LINK VALID: 24 hours ⏳
```

---

### **Step 6: John Receives & Clicks Link**

```
WHAT HAPPENS:
John checks email
Clicks link: https://flora.com/auth/set-password?token=xyz...

BACKEND PROCESSING:
1. Extract token from URL
2. Verify token is valid and not expired
3. Query database for user associated with token
4. Show password setup form

JOHN SEES:
┌─────────────────────────────────────────────────────┐
│ Set Your Password                                    │
│                                                      │
│ Email: john@myhotel.com                             │
│ New Password: [•••••••]                             │
│ Confirm Password: [•••••••]                         │
│                                                      │
│ [Create Account]                                    │
└─────────────────────────────────────────────────────┘

JOHN ENTERS:
├─ New Password: SecurePass123!
├─ Confirm Password: SecurePass123!
├─ Click: "Create Account"

BACKEND PROCESSES:
1. Validate password strength
2. Hash password: Hash(SecurePass123!) = $2b$12$...xyz
3. Update user record:
   {
     user_id: "john-uuid-12345",
     password_hash: "$2b$12$...xyz",  // Changed from null
     is_active: true
   }
4. Invalidate token (can't use same link twice)
5. Create audit log:
   {
     action: "ACCOUNT_ACTIVATED",
     actor: "john-uuid-12345",
     metadata: {
       email: "john@myhotel.com",
       timestamp: "2026-04-25T10:15:00Z"
     }
   }

RESPONSE:
Status: 200 OK
{
  "message": "Account activated successfully",
  "redirect": "/auth/login"
}

JOHN SEES:
"Account created! Redirecting to login..."

STATUS: ACCOUNT_ACTIVATED ✅
```

---

### **Step 7: John Logs In**

```
WHAT HAPPENS:
John goes to: dashboard.floratourism.com/login

LOGIN FORM:
┌─────────────────────────────────────────────────────┐
│ Flora Dashboard - Login                              │
│                                                      │
│ Email: [john@myhotel.com]                           │
│ Password: [•••••••]                                 │
│                                                      │
│ [Login]                                             │
└─────────────────────────────────────────────────────┘

JOHN ENTERS CREDENTIALS:
├─ Email: john@myhotel.com
├─ Password: SecurePass123!
└─ Click: [Login]

BACKEND PROCESSING:

1️⃣ AUTHENTICATION:
   - Query: SELECT * FROM users WHERE email = 'john@myhotel.com'
   - Result: Found user record
   - Compare: Hash(SecurePass123!) == stored_hash? YES ✓
   - Status: AUTHENTICATED ✓

2️⃣ ROLE LOOKUP:
   - User role: hotel_manager
   - Find hotel assignment: manager_id = john-uuid
   - Hotel: Grand Plaza Hotel
   - Status: ROLE_VERIFIED ✓

3️⃣ JWT TOKEN GENERATION:
   - Create token with payload:
   {
     user_id: "john-uuid-12345",
     email: "john@myhotel.com",
     role: "hotel_manager",
     hotel_id: "grand-plaza-uuid",
     permissions: {
       hotels: {can_read: true, can_update: true},
       bookings: {can_read: true, can_update: true},
       rooms: {can_read: true, can_update: true}
     },
     iat: 1703079600,
     exp: 1703081400  // 30 min expiry
   }
   - Sign with SECRET_KEY
   - Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

4️⃣ RESPONSE:
   Status: 200 OK
   {
     "token": "eyJhbGciOiJIUzI1NiIs...",
     "user": {
       "id": "john-uuid-12345",
       "email": "john@myhotel.com",
       "role": "hotel_manager",
       "hotel_id": "grand-plaza-uuid",
       "full_name": "John Smith"
     },
     "expires_in": 1800
   }

5️⃣ AUDIT LOG:
   {
     action: "LOGIN_SUCCESS",
     actor: "john-uuid-12345",
     metadata: {
       email: "john@myhotel.com",
       ip_address: "192.168.1.100",
       timestamp: "2026-04-25T10:20:00Z"
     }
   }

FRONTEND STORES TOKEN:
├─ localStorage.setItem('token', 'eyJhbGciOiJIUzI1NiIs...')
├─ localStorage.setItem('user', JSON.stringify({...}))
└─ Redirects to: /dashboard

STATUS: LOGGED_IN ✅
```

---

## 🔄 PART 2: COMPLETE RBAC FLOW (Daily Use)

### **Step 8: Dashboard Loads (GET Hotels)**

```
WHAT HAPPENS:
John's browser loads: /dashboard

REACT COMPONENT:
useEffect(() => {
  fetchHotels();
}, []);

FRONTEND CODE:
const fetchHotels = async () => {
  const token = localStorage.getItem('token');
  const response = await fetch('/api/v1/admin/hotels', {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });
  const data = await response.json();
  setHotels(data.items);
};

REQUEST SENT:
GET /api/v1/admin/hotels
Headers: {
  Authorization: Bearer eyJhbGciOiJIUzI1NiIs...,
  Content-Type: application/json
}

===== BACKEND RECEIVES REQUEST =====

1️⃣ EXTRACT & VALIDATE TOKEN:
   - Extract from header: Authorization: Bearer eyJhbGc...
   - Verify signature with SECRET_KEY? YES ✓
   - Check expiration? NOT expired ✓
   - Decode token:
   {
     user_id: "john-uuid-12345",
     email: "john@myhotel.com",
     role: "hotel_manager",
     hotel_id: "grand-plaza-uuid",
     ...
   }

2️⃣ USER AUTHENTICATION CHECK:
   - Is token valid? YES ✓
   - Is user_id in database? YES ✓
   - Is user active? YES ✓
   - Status: AUTHENTICATED ✓

3️⃣ PERMISSION CHECK (RBAC):
   - Endpoint: GET /api/v1/admin/hotels
   - Is endpoint protected? YES (requires RequireAdmin)
   - User role: hotel_manager
   - Check: Does hotel_manager have access? 
     - Query roles permissions:
       SELECT permissions FROM roles WHERE name = 'hotel_manager'
       Result: {hotels: {can_read: true, ...}}
     - Can read hotels? YES ✓
   - Status: PERMISSION_GRANTED ✓

4️⃣ RESOURCE SCOPE CHECK:
   - Is user assigned to specific hotel? 
     - User hotel_id: "grand-plaza-uuid"
     - Filter: ONLY return hotels where manager_id = user_id
   - Status: SCOPE_CHECK_PASSED ✓

5️⃣ DATA QUERY WITH FILTERING:
   Original Query:
   SELECT * FROM hotels

   Applied Filtering:
   SELECT * FROM hotels 
   WHERE manager_id = 'john-uuid-12345'
   ORDER BY name

   Database Results:
   ┌──────────────────────────────────┐
   │ All Hotels in Database:          │
   ├──────────────────────────────────┤
   │ 1. Grand Plaza (manager: john)   │ ✓ MATCHES
   │ 2. Riverside Resort (manager: sarah) │ ✗ FILTERED OUT
   │ 3. Beach House (manager: alex)   │ ✗ FILTERED OUT
   │ 4. Downtown Suites (manager: null) │ ✗ FILTERED OUT
   └──────────────────────────────────┘

   Returned Result:
   [{
     id: "grand-plaza-uuid",
     name: "Grand Plaza Hotel",
     city: "New York",
     manager_id: "john-uuid-12345",
     manager_name: "John Smith"
   }]

6️⃣ AUDIT LOGGING:
   Create log entry:
   {
     id: "audit-uuid-1",
     actor_id: "john-uuid-12345",
     actor_email: "john@myhotel.com",
     action: "GET_HOTELS",
     target_type: "hotel",
     target_id: "grand-plaza-uuid",
     meta_data: {
       query_filter: "manager_id = john-uuid-12345",
       results_count: 1
     },
     description: "John viewed hotels list",
     created_at: "2026-04-25T10:25:00Z",
     status: "success"
   }

7️⃣ RESPONSE TO FRONTEND:
   Status: 200 OK
   {
     "items": [{
       "id": "grand-plaza-uuid",
       "name": "Grand Plaza Hotel",
       "city": "New York",
       "manager_id": "john-uuid-12345"
     }],
     "total": 1,
     "page": 1,
     "page_size": 50
   }

FRONTEND RENDERS:
┌─────────────────────────────────────┐
│ My Hotel                             │
│                                      │
│ 🏨 Grand Plaza Hotel                │
│    New York                          │
│    45 Bookings | 20 Rooms           │
│                                      │
│    [View Bookings] [Manage]         │
└─────────────────────────────────────┘

STATUS: DASHBOARD_LOADED ✅
```

---

### **Step 9: View Bookings (Authorized Access)**

```
WHAT HAPPENS:
John clicks: "View Bookings" on Grand Plaza

FRONTEND REQUEST:
GET /api/v1/admin/hotels/grand-plaza-uuid/bookings
Headers: Authorization: Bearer <token>

BACKEND PROCESSING:

1️⃣ TOKEN VALIDATION:
   - Token valid? YES ✓
   - User authenticated? YES ✓

2️⃣ PERMISSION CHECK:
   - Can user read bookings? YES ✓
   - User role: hotel_manager ✓

3️⃣ RESOURCE SCOPE CHECK:
   - Is grand-plaza assigned to john?
   - Query: SELECT manager_id FROM hotels WHERE id = 'grand-plaza-uuid'
   - Result: manager_id = 'john-uuid-12345'
   - Match john's ID? YES ✓
   - Status: AUTHORIZED ✓

4️⃣ DATA FILTERING:
   Query: SELECT b.* FROM bookings b
          JOIN hotels h ON b.hotel_id = h.id
          WHERE b.hotel_id = 'grand-plaza-uuid'
          AND h.manager_id = 'john-uuid-12345'

   Database:
   ├─ Booking #001 (Grand Plaza, john's) ✓
   ├─ Booking #002 (Grand Plaza, john's) ✓
   ├─ Booking #003 (Riverside, sarah's) ✗
   ├─ Booking #004 (Beach House, alex's) ✗
   └─ ... more bookings ...

   Results: [#001, #002] (only john's hotel bookings)

5️⃣ RESPONSE:
   {
     "items": [
       {booking_id: 001, guest: "Jane Doe", ...},
       {booking_id: 002, guest: "Bob Smith", ...}
     ],
     "total": 2
   }

FRONTEND SHOWS:
John sees: 2 bookings for his hotel ✓

STATUS: BOOKINGS_RETRIEVED ✅
```

---

### **Step 10: Try Unauthorized Access (Security Test)**

```
WHAT HAPPENS:
Hacker tries to access competitor's data using john's token

ATTACKER REQUEST:
GET /api/v1/admin/hotels/riverside-uuid/bookings
Headers: Authorization: Bearer <john's_token>

BACKEND PROCESSING:

1️⃣ TOKEN VALIDATION:
   - Token valid? YES ✓
   - User authenticated? YES ✓

2️⃣ PERMISSION CHECK:
   - Can user read bookings? YES ✓

3️⃣ RESOURCE SCOPE CHECK:
   - Is riverside assigned to john?
   - Query: SELECT manager_id FROM hotels WHERE id = 'riverside-uuid'
   - Result: manager_id = 'sarah-uuid'
   - Match john's ID? NO ✗
   - Status: UNAUTHORIZED ✗

4️⃣ SECURITY BLOCK:
   Return Error:
   Status: 403 Forbidden
   {
     "error": "Forbidden",
     "message": "You don't have permission to access this resource"
   }

5️⃣ SECURITY AUDIT LOG:
   Create log entry:
   {
     action: "UNAUTHORIZED_ACCESS_ATTEMPT",
     actor_id: "john-uuid-12345",
     target_id: "riverside-uuid",
     meta_data: {
       attempted_resource: "bookings",
       attempted_hotel: "Riverside Resort",
       result: "BLOCKED"
     },
     severity: "WARNING",
     created_at: "2026-04-25T10:30:00Z"
   }

ATTACKER SEES:
Error: 403 Forbidden
Cannot access data ✗

SARAH'S DATA:
Completely protected ✓
No leakage ✓

SECURITY TEAM:
Can review audit log
See unauthorized attempt
Take action if needed

STATUS: UNAUTHORIZED_ACCESS_BLOCKED ✅
```

---

## 🎯 COMPLETE FLOW DIAGRAM

```
┌────────────────────────────────────────────────────────────┐
│                   COMPLETE RBAC FLOW                        │
└────────────────────────────────────────────────────────────┘

REGISTRATION PHASE:
  Owner Request
      ↓
  Admin Verification
      ↓
  Create Account
      ↓
  Assign Hotel
      ↓
  Send Invite Email
      ↓
  Manager Sets Password
      ↓
  Account Activated
      ↓
  ✓ REGISTRATION COMPLETE

DAILY USE PHASE:
  Manager Logs In
      ↓
  JWT Token Generated
      ↓
  Frontend Stores Token
      ↓
  Dashboard Loads
      ↓
  Request: GET /api/hotels
      ↓
  Backend Validates Token
      ↓
  Backend Checks Role Permission
      ↓
  Backend Checks Resource Scope
      ↓
  Backend Applies Filtering
      ↓
  Backend Creates Audit Log
      ↓
  Frontend Receives Filtered Data
      ↓
  Manager Sees Only Their Hotel
      ↓
  ✓ DATA ACCESS COMPLETE

SECURITY LAYER:
  Unauthorized Access Attempt
      ↓
  Token Valid? But...
      ↓
  Resource Not Assigned? NO
      ↓
  Return 403 Forbidden
      ↓
  Log Security Incident
      ↓
  ✓ SECURITY ENFORCED
```

---

## 📊 Database State After Registration

```
USERS TABLE:
┌────────────────────────────────────────────────────────┐
│ id              │ john-uuid-12345                       │
│ email           │ john@myhotel.com                      │
│ full_name       │ John Smith                            │
│ role            │ hotel_manager                         │
│ password_hash   │ $2b$12$...xyz                         │
│ is_active       │ true                                  │
│ created_at      │ 2026-04-25 10:00:00                   │
│ created_by      │ admin-uuid                            │
└────────────────────────────────────────────────────────┘

HOTELS TABLE:
┌────────────────────────────────────────────────────────┐
│ id              │ grand-plaza-uuid                      │
│ name            │ Grand Plaza Hotel                     │
│ city            │ New York                              │
│ manager_id      │ john-uuid-12345  ← Link to user       │
│ created_at      │ 2026-04-20 09:00:00                   │
└────────────────────────────────────────────────────────┘

ROLES TABLE:
┌────────────────────────────────────────────────────────┐
│ id              │ hotel-manager-uuid                    │
│ name            │ hotel_manager                         │
│ label           │ Hotel Manager                         │
│ permissions     │ {hotels: {read, update}, ...}         │
│ is_system_role  │ false                                 │
└────────────────────────────────────────────────────────┘

RBAC_AUDIT_LOGS TABLE:
┌────────────────────────────────────────────────────────┐
│ action          │ ACCOUNT_ACTIVATED                     │
│ actor_id        │ john-uuid-12345                       │
│ target_type     │ user                                  │
│ created_at      │ 2026-04-25 10:15:00                   │
├────────────────────────────────────────────────────────┤
│ action          │ ASSIGN_MANAGER                        │
│ actor_id        │ admin-uuid                            │
│ target_type     │ hotel                                 │
│ meta_data       │ {manager: john}                       │
│ created_at      │ 2026-04-25 10:05:00                   │
├────────────────────────────────────────────────────────┤
│ action          │ LOGIN_SUCCESS                         │
│ actor_id        │ john-uuid-12345                       │
│ created_at      │ 2026-04-25 10:20:00                   │
├────────────────────────────────────────────────────────┤
│ action          │ GET_HOTELS                            │
│ actor_id        │ john-uuid-12345                       │
│ created_at      │ 2026-04-25 10:25:00                   │
└────────────────────────────────────────────────────────┘
```

---

## ✅ Key Takeaways

| Stage | What Happens | Who Does It |
|-------|-------------|-----------|
| **Request** | Owner asks for manager | Owner |
| **Verify** | Admin checks details | Flora Admin |
| **Create** | System creates account | Backend |
| **Assign** | System links hotel | Backend |
| **Invite** | Email sent to manager | System |
| **Activate** | Manager sets password | Manager |
| **Login** | Manager logs in | Manager |
| **Authenticate** | Token generated | Backend |
| **Check Permission** | Role verified | Backend |
| **Check Scope** | Resource assigned? | Backend |
| **Filter Data** | Only their data returned | Backend |
| **Log Action** | Action recorded | Backend |
| **Display** | Manager sees their hotel | Frontend |

**Total Time**: 5-10 minutes from request to working dashboard!

---

## 🔐 Security Guarantees

✅ **Authentication**: Token must be valid  
✅ **Authorization**: Role must have permission  
✅ **Scope**: User must be assigned to resource  
✅ **Filtering**: Data filtered automatically  
✅ **Logging**: Every action logged  
✅ **No Bypass**: Backend enforces at every layer  

**Result**: Complete security from registration to daily use! 🎉

