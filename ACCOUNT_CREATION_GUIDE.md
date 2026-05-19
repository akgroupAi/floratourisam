# How to Create Accounts: Owner & Manager Guide

## 📌 Two Types of Account Creation

### **Account Type 1: HOTEL OWNER** 
```
Who: Person who owns the hotel business
Access: Can see/manage all their hotels
Can: Add staff, manage everything
```

### **Account Type 2: MANAGER/STAFF**
```
Who: Staff member assigned to specific hotel
Access: Can see ONLY assigned hotel
Can: Manage bookings, rooms (based on permissions)
Cannot: See other hotels or business settings
```

---

## 🏢 PATH 1: HOTEL OWNER CREATES ACCOUNT

### **Option A: Self-Signup (Easiest)**

#### **Step 1: Go to Flora Website**

```
Open browser → floratourism.com

SEES:
┌─────────────────────────────────────┐
│ Flora Tourism Management Platform   │
│                                      │
│ 🏨 Welcome to Flora                 │
│                                      │
│ [Login] [Sign Up for Hotel] [+]    │
│                                      │
│ For Hotel Owners:                   │
│ Manage all your properties in one   │
│ place with Flora                    │
│                                      │
│ [Get Started] ← Click here          │
└─────────────────────────────────────┘
```

#### **Step 2: Click "Sign Up for Hotel"**

```
Browser goes to: floratourism.com/register-hotel

FORM APPEARS:
┌────────────────────────────────────────┐
│ Create Hotel Owner Account             │
│                                        │
│ First Name: [John          ]          │
│ Last Name:  [Smith         ]          │
│ Email:      [john@email.com]          │
│ Password:   [••••••••     ]           │
│ Confirm:    [••••••••     ]           │
│                                        │
│ Hotel Name: [Grand Plaza Hotel]       │
│ City:       [New York     ]           │
│ Country:    [United States]           │
│ Hotel Type: [Luxury Hotel ▼]         │
│                                        │
│ ☑ I accept Terms & Conditions        │
│                                        │
│ [Create Account]                      │
└────────────────────────────────────────┘
```

#### **Step 3: Fill in Information**

```
Owner enters:
├─ Name: John Smith
├─ Email: john@grandplaza.com
├─ Password: SecurePassword123!
├─ Hotel Name: Grand Plaza Hotel
├─ City: New York
├─ Country: United States
└─ Hotel Type: Luxury Hotel
```

#### **Step 4: Backend Processes Signup**

```
WHAT HAPPENS:

1. VALIDATION:
   ├─ Is email format valid? YES ✓
   ├─ Is password strong? YES ✓ (min 8 chars, numbers, symbols)
   ├─ Email already used? NO ✓
   ├─ Hotel name valid? YES ✓
   └─ All fields filled? YES ✓

2. CREATE ACCOUNT:
   ├─ Hash password
   ├─ Create user record:
   │  {
   │    user_id: "owner-uuid-001",
   │    email: "john@grandplaza.com",
   │    full_name: "John Smith",
   │    role: "hotel_owner",  ← Owner role
   │    password_hash: "$2b$12$...xyz",
   │    is_active: true,
   │    created_at: "2026-04-25T14:30:00Z"
   │  }
   ├─ Create hotel record:
   │  {
   │    hotel_id: "hotel-uuid-001",
   │    name: "Grand Plaza Hotel",
   │    city: "New York",
   │    country: "United States",
   │    type: "Luxury Hotel",
   │    owner_id: "owner-uuid-001",  ← Link to owner
   │    manager_id: null,  ← Can assign manager later
   │    created_at: "2026-04-25T14:30:00Z"
   │  }
   └─ Create audit log entry

3. SEND CONFIRMATION EMAIL:
   {
     to: john@grandplaza.com,
     subject: "Welcome to Flora - Account Verified",
     body: "Your account is ready! Verify your email: [LINK]"
   }

4. RETURN SUCCESS:
   Status: 201 Created
   {
     "message": "Account created successfully!",
     "user_id": "owner-uuid-001",
     "hotel_id": "hotel-uuid-001",
     "redirect": "/auth/login"
   }
```

#### **Step 5: Owner Verifies Email**

```
Owner receives email:
┌────────────────────────────────────┐
│ From: noreply@floratourism.com     │
│ Subject: Verify Your Email         │
│                                    │
│ Hi John,                           │
│                                    │
│ Click to verify:                   │
│ [Verify Email]                     │
│ https://flora.com/verify?token=xyz │
│                                    │
│ Link expires: 24 hours             │
└────────────────────────────────────┘

Owner clicks: [Verify Email]

Backend processes:
├─ Extract token
├─ Check token valid? YES ✓
├─ Mark email verified
└─ Return: "Email verified!"

Status: EMAIL_VERIFIED ✅
```

#### **Step 6: Owner Logs In**

```
Owner goes to: floratourism.com/login

FORM:
┌────────────────────────────────────┐
│ Owner Login                         │
│                                    │
│ Email: [john@grandplaza.com]       │
│ Password: [••••••••]               │
│                                    │
│ [Login]                            │
└────────────────────────────────────┘

Backend verifies:
├─ Email exists? YES ✓
├─ Password matches? YES ✓
├─ Email verified? YES ✓
├─ Account active? YES ✓
└─ Generate JWT token

Owner receives token
Frontend stores token
Redirects to: /dashboard

Owner sees:
┌────────────────────────────────────┐
│ Dashboard                          │
│                                    │
│ 🏨 Grand Plaza Hotel               │
│ Location: New York                 │
│ Status: Active                     │
│ Rooms: 0 (not added yet)           │
│ Bookings: 0                        │
│                                    │
│ [Manage Hotel] [Add Staff]        │
└────────────────────────────────────┘

STATUS: OWNER_LOGGED_IN ✅
```

---

### **Option B: Admin Creates Owner Account**

```
If owner doesn't want to sign up themselves:

PROCESS:
1. Owner calls Flora Support: "Create account for me"
2. Flora Admin goes to: Admin Dashboard → Users → Create
3. Admin creates account with details:
   ├─ Email: john@grandplaza.com
   ├─ Name: John Smith
   ├─ Role: hotel_owner
   └─ Hotel: Grand Plaza
4. Admin sends temporary password via email
5. Owner receives email with password
6. Owner logs in & changes password
7. Owner can now manage hotel

TIME: 10-15 minutes
```

---

## 👥 PATH 2: MANAGER/STAFF CREATES ACCOUNT

### **Important: Managers DON'T create their own accounts!**

```
Why?
├─ Must be linked to specific hotel
├─ Must have correct permissions
├─ Must be assigned by owner/admin
└─ Direct signup would bypass security
```

### **How Manager Gets Account: 3 Steps**

#### **Step 1: Owner Requests Manager**

```
Hotel Owner does ONE of these:

Option A: In Dashboard
├─ Click: "Add Staff Member"
├─ Enter: Manager email
├─ Select: Manager role
└─ Click: "Send Invite"

Option B: Contact Flora Support
├─ Email: support@floratourism.com
├─ Subject: "Add manager for my hotel"
├─ Message: "Add maria@myhotel.com as receptionist"

Option C: Flora Admin Interface
├─ Owner contacts admin
├─ Admin creates account manually
└─ Admin assigns to owner's hotel
```

#### **Step 2: Flora System Creates Account**

```
When owner clicks "Send Invite":

BACKEND PROCESSES:

1. VERIFY:
   ├─ Manager email valid? YES ✓
   ├─ Owner has permission to add staff? YES ✓
   ├─ Hotel exists? YES ✓
   └─ Email not already used? YES ✓

2. CREATE ACCOUNT:
   {
     user_id: "manager-uuid-002",
     email: "maria@myhotel.com",
     full_name: "Maria Lopez",  ← From owner's input
     role: "hotel_manager",
     hotel_id: "hotel-uuid-001",  ← Assigned to Grand Plaza
     password_hash: null,  ← NOT set yet
     status: "pending_activation",
     invited_by: "owner-uuid-001",
     invited_at: "2026-04-25T14:35:00Z"
   }

3. SEND INVITE EMAIL:
   {
     to: maria@myhotel.com,
     subject: "You're invited to manage Grand Plaza Hotel",
     body: "Set your password: [LINK]"
   }

4. AUDIT LOG:
   {
     action: "MANAGER_INVITED",
     actor: "owner-uuid-001",
     target: "maria@myhotel.com",
     metadata: {
       hotel: "Grand Plaza Hotel",
       role: "hotel_manager"
     }
   }
```

#### **Step 3: Manager Activates Account**

```
Maria receives email:
┌────────────────────────────────────┐
│ From: support@floratourism.com     │
│ Subject: Welcome to Flora!         │
│                                    │
│ Hi Maria,                          │
│                                    │
│ You've been invited to manage:     │
│ 🏨 Grand Plaza Hotel               │
│                                    │
│ Set your password:                 │
│ [Create Account]                   │
│ https://flora.com/activate?t=xyz   │
│                                    │
│ Link expires: 24 hours             │
└────────────────────────────────────┘

Maria clicks: [Create Account]

FORM APPEARS:
┌────────────────────────────────────┐
│ Set Your Password                  │
│                                    │
│ Email: maria@myhotel.com           │
│                                    │
│ New Password: [••••••••]          │
│ Confirm: [••••••••]               │
│                                    │
│ [Activate Account]                 │
└────────────────────────────────────┘

Maria enters password:
├─ Password: Maria@SecurePass123!
├─ Confirm: Maria@SecurePass123!
└─ Click: [Activate Account]

BACKEND PROCESSES:
1. Validate password strength
2. Hash password
3. Update user:
   ├─ password_hash: "$2b$12$...abc"
   ├─ status: "active"
   └─ activated_at: "2026-04-25T14:40:00Z"
4. Send confirmation email
5. Create audit log: "Manager activated"

RESPONSE:
Status: 200 OK
{
  "message": "Account activated!",
  "redirect": "/auth/login"
}

Maria sees:
"Your account is ready! 
 Redirecting to login..."

STATUS: MANAGER_ACTIVATED ✅
```

#### **Step 4: Manager Logs In & Works**

```
Maria logs in:
├─ Email: maria@myhotel.com
├─ Password: Maria@SecurePass123!
└─ Click: [Login]

Backend:
├─ Verify email ✓
├─ Verify password ✓
├─ Generate JWT token with:
│  ├─ role: hotel_manager
│  ├─ hotel_id: hotel-uuid-001
│  └─ permissions: {bookings: read/update, rooms: read}
└─ Send to frontend

Maria sees Dashboard:
┌────────────────────────────────────┐
│ 🏨 Grand Plaza Hotel               │
│                                    │
│ Your Assigned Hotel                │
│ Location: New York                 │
│ Bookings: 45                       │
│ Rooms: 20                          │
│                                    │
│ [View Bookings] [Manage Rooms]    │
│ [Check In/Out] [View Reports]     │
│                                    │
│ ✗ CANNOT Access:                   │
│ ├─ Other hotels                    │
│ ├─ Financial reports              │
│ ├─ Hotel settings                  │
│ └─ Add staff                       │
└────────────────────────────────────┘

STATUS: MANAGER_LOGGED_IN ✅
```

---

## 🔄 Complete Account Creation Comparison

| Aspect | Owner | Manager |
|--------|-------|---------|
| **Who Creates** | Owner (self) or Admin | Owner or Admin |
| **Password Set** | During signup | Via activation link |
| **Email Verification** | Yes | Yes |
| **Role Assigned** | hotel_owner | hotel_manager |
| **Hotel Link** | Owner owns it | Owner assigns it |
| **Account Time** | 10 min | 5 min |
| **First Action** | View dashboard | Wait for invite |
| **Can Add Staff** | YES | NO |
| **Can See Reports** | YES (all hotels) | NO (only assigned) |

---

## 📋 Step-by-Step Comparison

### **OWNER ACCOUNT CREATION:**
```
1. Visit floratourism.com/register-hotel
2. Fill form: Name, email, password, hotel details
3. Submit
4. Check email verification link
5. Click link to verify
6. Go to login page
7. Login with email/password
8. Dashboard loads with hotel
9. Ready to manage!

TIME: 10 minutes
```

### **MANAGER ACCOUNT CREATION:**
```
1. Owner clicks "Add Staff" in dashboard
2. Enters manager email
3. Selects role
4. Owner sends invite
5. Manager checks email
6. Manager clicks activation link
7. Manager sets password
8. Manager goes to login
9. Manager logs in
10. Dashboard loads with assigned hotel
11. Manager ready to work!

TIME: 5-10 minutes (manager's part: 5 min)
```

---

## 🎯 Account Types & Permissions

### **Hotel Owner Account**
```
Login: john@grandplaza.com
Role: hotel_owner

Can Access:
✓ All their hotels
✓ All bookings for their hotels
✓ Financial reports
✓ Staff management
✓ Hotel settings
✓ Add more staff
✓ View audit logs

Dashboard shows:
├─ All their properties
├─ Combined statistics
├─ Team members
└─ Business analytics
```

### **Hotel Manager Account**
```
Login: maria@myhotel.com
Role: hotel_manager

Can Access:
✓ ONLY assigned hotel
✓ ONLY assigned hotel's bookings
✓ Room management for assigned hotel
✓ Check-in/out functionality
✓ Guest management
✓ View bookings/reservations

CANNOT Access:
✗ Other hotels
✗ Financial reports
✗ Hotel settings
✗ Add staff
✗ Modify pricing
✗ View other managers

Dashboard shows:
├─ ONLY their assigned hotel
├─ Today's bookings
├─ Room status
└─ Guest details
```

### **Receptionist Account** (Staff Role)
```
Same as Manager but with LIMITED permissions:

Can Access:
✓ Check-in/out
✓ View bookings
✓ Answer phone
✗ CANNOT modify prices
✗ CANNOT add rooms
✗ CANNOT delete bookings
```

---

## 📝 Complete Account Creation Flowchart

```
┌─────────────────────────────────────────────────────┐
│ SOMEONE WANTS ACCOUNT                               │
└─────────────────────────────────────────────────────┘

Is it a Hotel Owner?
├─ YES → Go to /register-hotel
│         Self-signup flow
│         10 minutes
│
└─ NO (It's a Manager/Staff)
   │
   ├─ Owner goes to dashboard
   ├─ Click "Add Staff"
   ├─ Enter email
   ├─ Send invite
   │
   └─ Manager receives email
      ├─ Click link
      ├─ Set password
      ├─ Account activated
      └─ 5 minutes
      
Result:
├─ Owner: Full dashboard with all features
└─ Manager: Limited dashboard for assigned hotel only

Both secured by:
├─ Token validation
├─ Role checking
├─ Permission verification
├─ Data filtering
└─ Audit logging
```

---

## ✅ Key Differences

| Feature | Owner | Manager |
|---------|-------|---------|
| Self-signup | YES | NO |
| Needs invite | NO | YES |
| Can add staff | YES | NO |
| Sees all hotels | YES | NO |
| Can change roles | YES | NO |
| Account time | 10 min | 5 min |
| Password set | During signup | Via email link |
| Email verification | Yes | Yes |
| First login | Immediate | After activation |

---

## 🔐 Security Features During Account Creation

```
✓ Password hashing (bcrypt)
✓ Email verification
✓ Token expiration (24 hours)
✓ No password in email
✓ No account until verified
✓ Audit logging for all creations
✓ GDPR compliant data handling
✓ Rate limiting on signup
✓ CAPTCHA on signup
✓ Email validation
```

---

## 💡 Quick Summary

**Hotel Owner Account:**
- Owner creates it by visiting website
- Takes 10 minutes
- Full access to everything
- Can manage all their hotels & staff

**Manager Account:**
- Owner or Admin creates invite
- Manager receives email with link
- Manager sets password
- Takes 5 minutes
- Limited access to assigned hotel only
- All access logged & monitored

**Result:** Secure, scalable system where owners control staff and staff can only see their assigned work! 🎉

