# How to Register Managers in Flora RBAC System

## 📝 Manager Registration Guide

A **Manager** is a staff member with access to manage a specific property (hotel, apartment, or restaurant).

---

## 🎯 Two Ways to Register Managers

### **Method 1: Flora Admin Creates Manager Account (For Hotel Owners)**

This is the **easiest way** for hotel owners.

#### Step-by-Step:

**Step 1: Hotel Owner Requests Manager**
```
Hotel Owner contacts Flora Support:
Email: support@floratourism.com
Subject: "Add manager for my hotel"

Message:
"Hi, I need to add a manager for my hotel.
Manager email: john@myhotel.com
Manager name: John Smith
Hotel: Grand Plaza Hotel
Permissions: Can manage bookings and rooms"
```

**Step 2: Flora Admin Receives Request**
```
Flora Admin logs into Admin Dashboard
Goes to: RBAC Admin → User Assignments
```

**Step 3: Flora Admin Creates Account**
```
Click: "+ Assign User"
Enter:
  • Email: john@myhotel.com
  • Full Name: John Smith
  • Role: hotel_manager (dropdown)
Click: "Send Invite"
```

**Step 4: Flora Admin Assigns Hotel**
```
Go to: RBAC Admin → Entity Assignments → Hotels
Find: Grand Plaza Hotel
Click: "Assign Manager"
Select: John Smith
Click: "Confirm"
```

**Step 5: Manager Receives Email**
```
John receives email:
┌─────────────────────────────────────┐
│ Welcome to Flora!                   │
│                                      │
│ You've been invited as:              │
│ Hotel Manager - Grand Plaza Hotel   │
│                                      │
│ Click to set password: [LINK]       │
│ Token expires in: 24 hours          │
└─────────────────────────────────────┘
```

**Step 6: Manager Sets Up Account**
```
John clicks link
Sets password
Confirms email
Logs in to dashboard
Sees: Grand Plaza Hotel only ✓
```

---

### **Method 2: Using API (For Developers/Automated Setup)**

If you want to integrate manager registration programmatically:

#### API Endpoint 1: Create User Role
```bash
POST /api/v1/admin/rbac/user-roles
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "email": "john@myhotel.com",
  "role_id": "hotel-manager-role-uuid",
  "full_name": "John Smith"
}
```

**Response:**
```json
{
  "message": "Role assigned to john@myhotel.com"
}
```

#### API Endpoint 2: Assign Hotel to Manager
```bash
PATCH /api/v1/admin/hotels/{hotel_id}/manager
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "manager_user_id": "john-user-uuid"
}
```

**Response:**
```json
{
  "message": "Hotel manager updated"
}
```

---

## 🏨 Complete Manager Registration Workflow

### **Scenario: Grand Plaza Hotel Owner Adds Receptionist**

#### **Day 1 - Owner Requests**
```
Owner: "I need a receptionist"
Contacts: Flora Admin
Email: "Add receptionist to Grand Plaza Hotel
       Name: Maria Lopez
       Email: maria@grandplaza.com"
```

#### **Day 1 - Flora Admin Sets Up (5 minutes)**
```
Admin Dashboard → RBAC Admin

Step 1: Create user with role
├─ Email: maria@grandplaza.com
├─ Name: Maria Lopez
├─ Role: hotel_manager
└─ Click: "Send Invite"

Step 2: Assign to hotel
├─ Go to: Hotels → Grand Plaza
├─ Click: "Assign Manager"
├─ Select: Maria Lopez
└─ Click: "Confirm"

Step 3: Verify
├─ Audit Log shows: "Maria Lopez assigned to Grand Plaza"
└─ Maria receives invite email
```

#### **Day 1 - Maria Receives Email**
```
From: support@floratourism.com
Subject: "Welcome to Flora - Hotel Manager Invitation"

Body:
"Hi Maria,

You've been invited to manage Grand Plaza Hotel!

Set your password: [SECURE LINK - expires 24h]

Once activated:
✓ You can view all bookings
✓ You can check in guests
✓ You can update room status
✓ You see only Grand Plaza Hotel

Questions? Contact: support@floratourism.com

Welcome aboard! 🎉"
```

#### **Day 1 - Maria Sets Up Account (5 minutes)**
```
1. Clicks link in email
2. Creates password
3. Confirms account
4. Logs in to dashboard

Sees:
├─ Grand Plaza Hotel (only this)
├─ Today's bookings: 12 guests
├─ Rooms status
├─ Check-in/out times
└─ Team (just her + owner)
```

#### **Day 2 - Maria Works**
```
8:00 AM - Guest calls
Maria: Finds booking → Updates check-in time
System: Sends confirmation to guest

10:00 AM - Owner reviews changes
Owner clicks: Audit Log
Sees: "Maria Lopez updated booking #234 at 08:15"

5:00 PM - Owner checks activity
Owner: "Maria checked in 8 guests today, great work!"
```

---

## 👥 Manager Types & Registration

### **1. Hotel Manager**
```
What they see:
├─ Assigned hotel(s)
├─ All bookings
├─ Rooms & pricing
├─ Guest info
└─ Team members

Registration:
Role: hotel_manager
Assigned to: Hotel entity
Time: 5 minutes
```

**Example API:**
```bash
POST /api/v1/admin/rbac/user-roles
{
  "email": "manager@hotelname.com",
  "role_id": "hotel-manager-uuid",
  "full_name": "Hotel Manager Name"
}
```

### **2. Apartment Manager**
```
What they see:
├─ Assigned apartment(s)
├─ All bookings
├─ Units & pricing
├─ Guest info
└─ Team members

Registration:
Role: apartment_manager
Assigned to: Apartment entity
Time: 5 minutes
```

**Example API:**
```bash
POST /api/v1/admin/rbac/user-roles
{
  "email": "manager@apartments.com",
  "role_id": "apartment-manager-uuid",
  "full_name": "Apartment Manager Name"
}
```

### **3. Restaurant Manager**
```
What they see:
├─ Assigned restaurant(s)
├─ All bookings
├─ Menu & pricing
├─ Customer info
└─ Team members

Registration:
Role: restaurant_manager
Assigned to: Restaurant entity
Time: 5 minutes
```

**Example API:**
```bash
POST /api/v1/admin/rbac/user-roles
{
  "email": "manager@restaurant.com",
  "role_id": "restaurant-manager-uuid",
  "full_name": "Restaurant Manager Name"
}
```

---

## 🔑 Getting Role IDs for API Registration

### **Step 1: Get All Available Roles**
```bash
GET /api/v1/admin/rbac/roles?page=1&page_size=50
Authorization: Bearer <admin_token>

Response:
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "hotel_manager",
      "label": "Hotel Manager",
      "is_system_role": false
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "name": "apartment_manager",
      "label": "Apartment Manager",
      "is_system_role": false
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440002",
      "name": "restaurant_manager",
      "label": "Restaurant Manager",
      "is_system_role": false
    }
  ]
}
```

### **Step 2: Use the ID in Registration**
```bash
POST /api/v1/admin/rbac/user-roles
{
  "email": "newmanager@hotel.com",
  "role_id": "550e8400-e29b-41d4-a716-446655440000",  # Use the ID from above
  "full_name": "New Manager"
}
```

---

## 📋 Registration Checklist

### **For Flora Admins**

- [ ] **Receive request** from hotel owner
- [ ] **Verify email** is correct
- [ ] **Get hotel/apt/restaurant ID** (assigned property)
- [ ] **Create user with role** via API or dashboard
  ```bash
  POST /api/v1/admin/rbac/user-roles
  {
    "email": "manager@property.com",
    "role_id": "<manager-role-uuid>",
    "full_name": "Manager Name"
  }
  ```
- [ ] **Assign property** to manager
  ```bash
  PATCH /api/v1/admin/hotels/{hotel_id}/manager
  {
    "manager_user_id": "<manager-uuid>"
  }
  ```
- [ ] **Verify in audit log** - Check manager was assigned
- [ ] **Send confirmation** to property owner
- [ ] **Document in records** - Who assigned, when

### **For Property Owners**

- [ ] **Contact Flora Support** with manager details
- [ ] **Wait for invite email** (usually same day)
- [ ] **Share invite link** with manager (if needed)
- [ ] **Manager sets password** (24 hour window)
- [ ] **Verify manager can access** dashboard
- [ ] **Check audit log** - Confirm manager was added

---

## 🔄 Manager Registration Flow (Visual)

```
┌─────────────────────────────────────────────────────────────┐
│ MANAGER REGISTRATION FLOW                                    │
└─────────────────────────────────────────────────────────────┘

1. Hotel Owner Requests
   │
   ├─→ Contact: support@floratourism.com
   ├─→ Email: Manager name + hotel + permissions needed
   └─→ Status: PENDING

2. Flora Admin Verifies
   │
   ├─→ Check: Valid email
   ├─→ Check: Hotel exists
   └─→ Status: VERIFIED

3. Create Manager Account
   │
   ├─→ POST /api/v1/admin/rbac/user-roles
   ├─→ Role: hotel_manager (or apt/rest)
   └─→ Status: ACCOUNT_CREATED

4. Assign Property
   │
   ├─→ PATCH /api/v1/admin/hotels/{id}/manager
   ├─→ Set: manager_user_id
   └─→ Status: ASSIGNED

5. Send Invite Email
   │
   ├─→ Email: Welcome + password setup link
   ├─→ Link valid: 24 hours
   └─→ Status: INVITE_SENT

6. Manager Sets Password
   │
   ├─→ Click: Email link
   ├─→ Enter: New password
   └─→ Status: PASSWORD_SET

7. Manager Logs In
   │
   ├─→ Email: manager@hotel.com
   ├─→ Password: [set in step 6]
   └─→ Status: LOGGED_IN

8. Access Verified
   │
   ├─→ Sees: Only assigned property
   ├─→ Dashboard loads successfully
   └─→ Status: ACTIVE ✓

Total time: 5-10 minutes
```

---

## 🛠️ Bulk Manager Registration (For Multiple Properties)

### **CSV Upload Method** (Planned Feature)

```csv
email,property_name,property_type,manager_name,permissions
john@grandplaza.com,Grand Plaza Hotel,hotel,John Smith,bookings,rooms,pricing
maria@riverside.com,Riverside Resort,hotel,Maria Lopez,bookings,rooms
alex@apt.com,Downtown Apartments,apartment,Alex Johnson,bookings,units
```

**Process:**
1. Flora Admin uploads CSV
2. System validates emails
3. System creates accounts
4. System assigns properties
5. System sends invites
6. Report: 3 managers registered ✓

*Status: Coming soon in v2.0*

---

## ❓ FAQs About Manager Registration

### Q: How long does registration take?
**A:** Usually 5-10 minutes. Flora Admin creates account and assigns property. Manager gets email instantly.

### Q: Do managers need tech knowledge?
**A:** No! They just click email link, set password, and log in. Simple!

### Q: Can I register multiple managers for one hotel?
**A:** Yes! Each can have different permissions (owner, receptionist, housekeeper, etc.)

### Q: What if manager forgets password?
**A:** They click "Forgot Password" on login page. Reset link sent via email.

### Q: Can manager be assigned to multiple properties?
**A:** Yes! If you own 3 hotels, same manager can see all 3.

### Q: How do I remove a manager?
**A:** Contact Flora Admin → They disable account → Manager loses access instantly.

### Q: Can I change manager's permissions after registration?
**A:** Yes! Go to RBAC Admin → Update role → Manager's access updates instantly.

### Q: Is manager data backed up?
**A:** Yes! All manager data encrypted and backed up daily.

### Q: How many managers can I have?
**A:** Unlimited! Add as many as you need.

### Q: What if manager email is wrong?
**A:** Contact Flora Admin → They create new account → Disable old one. 10 minutes fix.

---

## 📞 Get Help with Manager Registration

**Issues?**
- Email: support@floratourism.com
- Phone: 1-800-FLORA-NOW
- Chat: Dashboard help icon

**Common Problems:**
- Manager didn't receive email → Check spam folder or resend
- Can't set password → Link expired, request new one
- Wrong property assigned → Contact admin to reassign
- Manager can't log in → Verify email/password, reset if needed

---

## ✅ Summary

**To register a manager:**

1. **Easiest**: Owner contacts Flora Support
2. **Quickest**: Flora Admin uses dashboard
3. **Automated**: Developers use API endpoints

**Manager gets access in:** 5-10 minutes  
**Manager sees:** Only their assigned property  
**All changes logged:** Complete audit trail  

**Result**: Your team can start working immediately! 🚀

