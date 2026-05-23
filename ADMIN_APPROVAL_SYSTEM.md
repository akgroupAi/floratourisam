# Admin Approval & Disapproval System 🔐

## ❓ The Question
**"Is there approval/disapproval functionality on the admin side for any user?"**

Answer: **YES!** Flora has a complete admin approval system for all user types.

---

## 📊 Who Can Be Approved/Disapproved?

```
✅ CAN BE APPROVED/DISAPPROVED:
├─ Hotel Owners (Status: PENDING → APPROVED/REJECTED)
├─ Hotel Managers (Status: PENDING → APPROVED/REJECTED)
├─ Apartment Managers
├─ Restaurant Managers
├─ Staff Members
├─ Receptionists
└─ Any user created by owner/admin

❌ CANNOT BE DISAPPROVED:
├─ Super Admin (root access, always approved)
├─ System Admin (cannot be rejected)
└─ Already Active Users (can only be suspended/deactivated)
```

---

## 👨‍💼 WHO IS ADMIN?

```
ADMIN HIERARCHY:

Level 1: SUPER_ADMIN (Root)
└─ Has all permissions
└─ Can approve/disapprove anyone
└─ Can modify other admins
└─ Full system access

Level 2: ADMIN
└─ Can approve/disapprove users
└─ Cannot modify other admins
└─ Cannot change super admin settings
└─ Limited system access

Level 3: MANAGER/STAFF
└─ Cannot approve/disapprove
└─ Can only request changes
└─ No admin dashboard access
```

---

## 🎯 User Status States

```
┌─────────────────────────────────────────────────┐
│ USER LIFECYCLE                                  │
└─────────────────────────────────────────────────┘

OWNER SIGNUP:

    SIGNUP_FORM_FILLED
            ↓
    EMAIL_VERIFICATION_SENT
            ↓
    EMAIL_VERIFIED ✅
            ↓
    KYC_DOCUMENTS_SUBMITTED
            ↓
    DOCUMENTS_PROCESSING (AI Scan)
            ↓
    PENDING_ADMIN_APPROVAL ⏳
            │
            ├─→ APPROVED ✅
            │   └─→ ACTIVE (Full Access)
            │
            ├─→ MORE_INFO_NEEDED ⚠️
            │   └─→ PENDING_ADMIN_APPROVAL (after resubmit)
            │
            └─→ REJECTED ❌
                └─→ INACTIVE (No Access)


MANAGER INVITATION:

    OWNER_SENDS_INVITE
            ↓
    MANAGER_INVITE_EMAIL_SENT
            ↓
    MANAGER_SETS_PASSWORD
            ↓
    PENDING_ADMIN_APPROVAL ⏳
            │
            ├─→ APPROVED ✅
            │   └─→ ACTIVE (Full Access)
            │
            └─→ REJECTED ❌
                └─→ INACTIVE (No Access)
```

---

## 📋 Admin Dashboard: Approval Queue

### **What Admin Sees:**

```
┌────────────────────────────────────────────────────────┐
│ FLORA ADMIN DASHBOARD                                  │
│                                                        │
│ ✓ Home  ✓ Users  ✓ Approvals  ✓ Reports  ✓ Settings  │
│                                                        │
├────────────────────────────────────────────────────────┤
│ PENDING APPROVALS (23)                                 │
│                                                        │
│ Approval Queue:                                        │
│ ┌─────────────────────────────────────────────────┐  │
│ │ 1. John Smith - Hotel Owner                     │  │
│ │    Email: john@grandplaza.com                   │  │
│ │    Hotel: Grand Plaza Hotel                     │  │
│ │    Status: PENDING_APPROVAL                     │  │
│ │    Submitted: 2026-04-25 10:30 AM              │  │
│ │    Documents: ✓ Verified                        │  │
│ │    Fraud Check: ✓ Clear                         │  │
│ │    [VIEW DETAILS] [APPROVE] [REJECT]           │  │
│ └─────────────────────────────────────────────────┘  │
│                                                        │
│ ┌─────────────────────────────────────────────────┐  │
│ │ 2. Maria Lopez - Hotel Manager                  │  │
│ │    Email: maria@myhotel.com                     │  │
│ │    Assigned to: Grand Plaza Hotel               │  │
│ │    Status: PENDING_APPROVAL                     │  │
│ │    Invited: 2026-04-25 11:00 AM                │  │
│ │    Documents: ✓ Verified                        │  │
│ │    [VIEW DETAILS] [APPROVE] [REJECT]           │  │
│ └─────────────────────────────────────────────────┘  │
│                                                        │
│ ┌─────────────────────────────────────────────────┐  │
│ │ 3. Ahmed Khan - Apartment Manager               │  │
│ │    Email: ahmed@apartmentmgmt.com               │  │
│ │    Assigned to: Downtown Residency              │  │
│ │    Status: PENDING_APPROVAL                     │  │
│ │    Documents: ⚠️ NEEDS_VERIFICATION            │  │
│ │    [REQUEST MORE INFO] [APPROVE] [REJECT]      │  │
│ └─────────────────────────────────────────────────┘  │
│                                                        │
│ Total: 23 pending | 5 in this hour | 892 total       │
└────────────────────────────────────────────────────────┘
```

---

## ✅ APPROVAL PROCESS

### **Step 1: Admin Opens Approval Queue**

```
Admin logs in → Admin Dashboard → Pending Approvals

Sees:
├─ Name of person
├─ Email address
├─ User type (Owner/Manager/Staff)
├─ Documents uploaded
├─ Submitted date/time
├─ Verification status
└─ Action buttons [APPROVE] [REJECT] [MORE_INFO]
```

### **Step 2: Admin Reviews User Details**

```
Admin clicks: [VIEW DETAILS]

Details Page Shows:

PERSONAL INFO:
├─ Full Name: John Smith
├─ Email: john@grandplaza.com
├─ Phone: +1-212-555-1234
├─ Date of Birth: 15-03-1975
└─ Nationality: United States

HOTEL INFO:
├─ Hotel Name: Grand Plaza Hotel
├─ City: New York
├─ Address: 123 Fifth Avenue
├─ Registration #: NYC-HRL-2024-001
├─ Tax ID: 12-3456789
└─ Category: 5-Star Luxury

DOCUMENTS UPLOADED:
├─ ✓ Passport (Front)
├─ ✓ Passport (Back)
├─ ✓ Address Proof
├─ ✓ Business Registration
└─ ✓ Hotel License

VERIFICATION STATUS:
├─ Email Verified: ✓ YES
├─ KYC Documents: ✓ PASSED
├─ Facial Recognition: ✓ PASSED (99.2% match)
├─ Fraud Check: ✓ CLEAR
├─ Sanctions Check: ✓ CLEAR
├─ Government Records: ✓ FOUND
└─ Overall Risk: LOW

SUBMISSION INFO:
├─ Submitted: 2026-04-25 10:30 AM
├─ Time in Queue: 3 hours
├─ Previous Submissions: 0 (First time)
└─ Assigned Reviewer: None yet
```

### **Step 3: Admin Makes Decision**

```
Admin has 3 options:

OPTION 1: APPROVE ✅
─────────────────────
Admin clicks: [APPROVE]

Dialog appears:
┌─────────────────────────────────────┐
│ APPROVE USER                        │
│                                     │
│ User: John Smith                    │
│ Email: john@grandplaza.com          │
│                                     │
│ Notes (optional):                   │
│ ┌─────────────────────────────────┐ │
│ │ Documents verified. Hotel       │ │
│ │ registration confirmed.         │ │
│ │ KYC check passed. All clear.    │ │
│ │                                 │ │
│ │                                 │ │
│ └─────────────────────────────────┘ │
│                                     │
│ ☑ Send approval email to user      │
│                                     │
│ [CONFIRM APPROVAL] [CANCEL]        │
└─────────────────────────────────────┘

Admin clicks: [CONFIRM APPROVAL]

BACKEND PROCESSES:
1. Update user status: APPROVED ✅
2. Set user.is_active = true
3. Update user.approved_at = now()
4. Update user.approved_by = admin_id
5. Create audit log entry:
   {
     action: "USER_APPROVED",
     actor: admin_id,
     target_user: john_id,
     timestamp: now(),
     notes: "Documents verified..."
   }
6. Send email to user: "Your account approved!"
7. Commit to database

User receives email:
┌────────────────────────────────────┐
│ From: admin@floratourism.com       │
│ Subject: Account Approved! ✅      │
│                                    │
│ Hi John,                           │
│                                    │
│ Your account has been approved!    │
│                                    │
│ You can now:                       │
│ ├─ Login to your dashboard         │
│ ├─ Manage your hotel               │
│ ├─ Add staff members               │
│ └─ Process bookings                │
│                                    │
│ Login: floratourism.com/login      │
│                                    │
│ Welcome to Flora! 🎉               │
└────────────────────────────────────┘

Status: ✅ APPROVED
User can now access dashboard!


OPTION 2: REQUEST MORE INFO ⚠️
──────────────────────────────
Admin clicks: [REQUEST MORE INFO]

Dialog appears:
┌──────────────────────────────────────┐
│ REQUEST ADDITIONAL INFORMATION       │
│                                      │
│ User: John Smith                     │
│ Email: john@grandplaza.com           │
│                                      │
│ Reason for request:                  │
│ ┌────────────────────────────────────┐│
│ │ Passport expiration date is        ││
│ │ less than 6 months away.           ││
│ │ Please provide renewal document    ││
│ │ or extended validity proof.        ││
│ │                                    ││
│ │                                    ││
│ └────────────────────────────────────┘│
│                                      │
│ Deadline (Days): [7 ▼]              │
│                                      │
│ ☑ Send request email to user        │
│                                      │
│ [SEND REQUEST] [CANCEL]             │
└──────────────────────────────────────┘

Admin clicks: [SEND REQUEST]

BACKEND PROCESSES:
1. Update user status: NEEDS_MORE_INFO ⚠️
2. Create audit log:
   {
     action: "MORE_INFO_REQUESTED",
     actor: admin_id,
     target_user: john_id,
     reason: "Passport expiration...",
     deadline: 2026-05-02
   }
3. Send email with deadline
4. Set deadline timer

User receives email:
┌────────────────────────────────────┐
│ Subject: More Information Needed ⚠️ │
│                                    │
│ Hi John,                           │
│                                    │
│ We need additional information     │
│ to complete your approval:         │
│                                    │
│ Reason:                            │
│ "Passport expiration date is       │
│  less than 6 months away"          │
│                                    │
│ Please upload:                     │
│ - Passport renewal document        │
│ - Or extended validity proof       │
│                                    │
│ Upload here: [LINK]                │
│ Deadline: April 30, 2026           │
│                                    │
│ Contact support if you have q's    │
└────────────────────────────────────┘

User can then:
├─ Log in to portal
├─ Click "My Documents"
├─ Upload new documents
└─ Resubmit for approval

Status: ⏳ NEEDS_MORE_INFO
(Application stays alive, not rejected)


OPTION 3: REJECT ❌
────────────────────
Admin clicks: [REJECT]

Dialog appears:
┌──────────────────────────────────────┐
│ REJECT USER APPLICATION              │
│                                      │
│ User: John Smith                     │
│ Email: john@grandplaza.com           │
│                                      │
│ Rejection Reason: (Required)         │
│ ┌────────────────────────────────────┐│
│ │ Reason for rejection:              ││
│ │ [Select reason ▼]                  ││
│ │ ├─ Documents not clear             ││
│ │ ├─ Fraud flag detected             ││
│ │ ├─ Hotel not registered            ││
│ │ ├─ Information mismatch            ││
│ │ ├─ Legal issues                    ││
│ │ └─ Other                           ││
│ └────────────────────────────────────┘│
│                                      │
│ Additional Notes:                    │
│ ┌────────────────────────────────────┐│
│ │ Passport appears to be forged      ││
│ │ based on AI fraud detection.       ││
│ │ Hotel registration not found in    ││
│ │ government records.                ││
│ │                                    ││
│ │                                    ││
│ └────────────────────────────────────┘│
│                                      │
│ Allow Re-application in (Days):      │
│ [30 ▼] (User can try again after)    │
│                                      │
│ ☑ Send rejection email to user      │
│ ☑ Delete submitted documents        │
│                                      │
│ [CONFIRM REJECTION] [CANCEL]        │
└──────────────────────────────────────┘

Admin clicks: [CONFIRM REJECTION]

BACKEND PROCESSES:
1. Update user status: REJECTED ❌
2. Set user.is_active = false
3. Update user.rejected_at = now()
4. Update user.rejected_by = admin_id
5. Set reapplication_allowed_at = now() + 30 days
6. Create audit log:
   {
     action: "USER_REJECTED",
     actor: admin_id,
     target_user: john_id,
     reason: "Documents appear forged",
     notes: "AI fraud detection flagged...",
     reapply_after: 2026-05-25
   }
7. Optionally delete documents from storage
8. Send rejection email
9. Commit

User receives email:
┌────────────────────────────────────┐
│ Subject: Application Not Approved ❌ │
│                                    │
│ Hi John,                           │
│                                    │
│ Unfortunately, we cannot approve   │
│ your account at this time.         │
│                                    │
│ Reason:                            │
│ "Documents appear to be forged     │
│  based on fraud detection"         │
│                                    │
│ What can you do?                   │
│                                    │
│ Option 1: Appeal                   │
│ └─ Send appeal: [APPEAL_LINK]      │
│                                    │
│ Option 2: Try Again                │
│ └─ Can reapply: May 25, 2026       │
│                                    │
│ Option 3: Contact Support          │
│ └─ Email: support@floratourism.com │
│                                    │
│ We're here to help!                │
└────────────────────────────────────┘

Status: ❌ REJECTED
User cannot access dashboard
Can appeal or reapply after 30 days
```

---

## 🔄 Bulk Approval Actions

### **Admin Can Also:**

```
APPROVE MULTIPLE USERS:
├─ Select checkbox next to multiple users
├─ Click: "Bulk Actions" → "Approve Selected"
├─ Confirm
├─ All selected users approved at once
└─ Each gets approval email

EXAMPLE:
✓ [Checkbox] John Smith - Owner
✓ [Checkbox] Maria Lopez - Manager
✓ [Checkbox] Ahmed Khan - Manager

Click: [Approve Selected (3)] → [CONFIRM]
Result: All 3 approved in 1 action

REJECT MULTIPLE USERS:
├─ Select multiple users
├─ Click: "Bulk Actions" → "Reject Selected"
├─ Enter rejection reason
├─ All rejected
└─ Each gets rejection email

REQUEST INFO FROM MULTIPLE:
├─ Select users
├─ Click: "Request Info From Selected"
├─ Enter requirement
├─ Set deadline
└─ All get request emails
```

---

## 📊 Admin Filters & Search

```
Admin can filter pending approvals by:

├─ Status:
│  ├─ PENDING_APPROVAL (default)
│  ├─ NEEDS_MORE_INFO
│  ├─ APPROVED
│  └─ REJECTED
│
├─ User Type:
│  ├─ Hotel Owner
│  ├─ Hotel Manager
│  ├─ Apartment Manager
│  ├─ Restaurant Manager
│  └─ Staff/Receptionist
│
├─ Risk Level:
│  ├─ LOW (Green)
│  ├─ MEDIUM (Yellow)
│  └─ HIGH (Red)
│
├─ Date Range:
│  ├─ Last 24 hours
│  ├─ Last 7 days
│  ├─ Last 30 days
│  └─ Custom date range
│
├─ Document Status:
│  ├─ All Verified
│  ├─ Pending Verification
│  └─ Verification Failed
│
└─ Search By:
   ├─ Name
   ├─ Email
   ├─ Hotel Name
   └─ Application ID
```

---

## 📈 Approval Statistics

```
Admin Dashboard shows:

APPROVAL METRICS:
├─ Pending Approvals: 23
├─ In Last 24h: 8
├─ Average Response Time: 4.2 hours
├─ Approval Rate: 87% (approve) / 13% (reject)
├─ Average Processing Time: 2.5 days
└─ Oldest Pending: 12 hours

APPROVAL RATE BY TYPE:
├─ Hotel Owners: 85% approved, 15% rejected
├─ Hotel Managers: 92% approved, 8% rejected
├─ Apartment Managers: 88% approved, 12% rejected
└─ Staff: 95% approved, 5% rejected

REJECTION REASONS (Last 30 days):
├─ Documents not clear: 45%
├─ Fraud flags: 25%
├─ Hotel not found: 15%
├─ Info mismatch: 10%
└─ Legal issues: 5%
```

---

## 🔐 Audit Log for Approvals

```
Every approval/disapproval is logged:

AUDIT LOG ENTRY:

{
  id: "audit-uuid-001",
  action: "USER_APPROVED",
  actor_id: "admin-id-123",
  actor_email: "admin@floratourism.com",
  actor_role: "admin",
  target_user_id: "user-id-456",
  target_user_email: "john@grandplaza.com",
  target_user_name: "John Smith",
  target_user_type: "hotel_owner",
  timestamp: "2026-04-25T15:30:00Z",
  notes: "Documents verified, hotel confirmed",
  metadata: {
    fraud_score: 0.05,
    document_verification: "passed",
    government_records: "found",
    manual_review: "approved"
  },
  status: "completed",
  email_sent_to_user: true,
  email_sent_at: "2026-04-25T15:30:15Z"
}
```

Admins can view audit logs:
```
Admin Dashboard → Audit Logs

Filters:
├─ By Action (APPROVED, REJECTED, MORE_INFO_REQUESTED)
├─ By Admin
├─ By User
├─ By Date Range
└─ By Result

Shows:
├─ Who did it (Admin name)
├─ What they did (Action)
├─ To whom (User name)
├─ When (Timestamp)
├─ Why (Notes)
└─ Outcome (Success/Failed)
```

---

## 📧 Email Templates

### **Approval Email:**
```
Subject: Your Account Has Been Approved! ✅

Hi [User Name],

Great news! Your application to Flora Tourism has been approved!

Account Details:
├─ Email: [user_email]
├─ Role: [user_role]
├─ Entity: [hotel/apartment/restaurant name]
└─ Status: ACTIVE ✅

You can now:
✓ Log in to your dashboard
✓ Manage your properties
✓ Add team members
✓ Process bookings
✓ View reports

Login URL: https://floratourism.com/login

Questions? Contact us at support@floratourism.com

Welcome to Flora! 🎉
```

### **Rejection Email:**
```
Subject: Application Review Update

Hi [User Name],

Thank you for your application to Flora Tourism. After careful review,
we are unable to approve your account at this time.

Reason: [reason]

Details:
[admin_notes]

Your Options:

1. Appeal the Decision
   - Provide additional information
   - Click: [appeal_link]

2. Reapply
   - You can reapply on: [date]
   - Make sure to address the concerns

3. Contact Support
   - Email: support@floratourism.com
   - Our team is happy to help

We appreciate you and hope to work together in the future.
```

---

## 🎯 Common Admin Approval Scenarios

### **Scenario 1: First-time Hotel Owner**
```
1. Owner signs up → EMAIL_VERIFICATION
2. Owner uploads KYC docs → DOCUMENTS_PROCESSING
3. System validates documents → PENDING_ADMIN_APPROVAL
4. Admin reviews in queue → All checks green ✓
5. Admin clicks [APPROVE]
6. Owner receives approval email
7. Owner logs in → Full dashboard access
8. Owner manages hotel ✓

Time: 2-3 days
Success Rate: High (most pass KYC)
```

### **Scenario 2: Manager Added by Owner**
```
1. Owner invites manager → INVITE_EMAIL_SENT
2. Manager accepts, sets password → ACCOUNT_CREATED
3. System auto-verifies (owned by owner) → PENDING_ADMIN_APPROVAL
4. Admin reviews quickly → Verification passes
5. Admin clicks [APPROVE]
6. Manager receives approval email
7. Manager logs in → Dashboard with assigned hotel
8. Manager works ✓

Time: 1 day (faster than owner)
Success Rate: Very high (owner vouches)
```

### **Scenario 3: Suspicious Documents**
```
1. Owner signs up → Uploads documents
2. AI fraud detection → RISK_FLAGGED 🚨
3. Documents sent to admin → PENDING_ADMIN_APPROVAL
4. Admin reviews → Passport looks forged
5. Admin clicks [REQUEST MORE INFO]
6. Owner receives email → Needs valid ID
7. Owner uploads new passport → PENDING_ADMIN_APPROVAL
8. Admin reviews → Looks valid now
9. Admin clicks [APPROVE]
10. Owner finally gets access ✓

Time: 5-7 days (back and forth)
Success Rate: ~50% (many don't resubmit)
```

### **Scenario 4: Clear Fraud**
```
1. Owner signs up → Documents appear forged
2. AI detects multiple red flags → HIGH_RISK
3. Admin reviews → Hotel doesn't exist in records
4. Name matches fraud database → CLEAR_FRAUD
5. Admin clicks [REJECT]
6. Reason: "Documents appear forged"
7. Owner receives rejection email
8. Can appeal or reapply in 30 days
9. Account remains inactive ❌

Time: 1 day
Success Rate: 0% (fraud account rejected)
```

---

## ✅ Quick Answer

### **Is there approval/disapproval on admin side?**

**YES! Complete system includes:**

1. **✅ APPROVAL** - Admin approves users
   - Status changes to ACTIVE
   - User gets access to dashboard
   - Approval email sent
   - Audit logged

2. **❌ DISAPPROVAL** - Admin rejects users
   - Status changes to REJECTED
   - User cannot access dashboard
   - Can appeal or reapply after 30 days
   - Rejection email sent
   - Audit logged

3. **⚠️ REQUEST MORE INFO** - Admin asks for clarification
   - Status changes to NEEDS_MORE_INFO
   - User has deadline to resubmit
   - Application stays open
   - Can modify and resubmit
   - Then re-reviewed

4. **📊 BULK ACTIONS** - Admin can approve/reject multiple at once

5. **🔍 AUDIT TRAIL** - Every action logged and traceable

### **Who can approve/disapprove?**

- ✅ Super Admin (full access)
- ✅ Admin (full access)
- ❌ Managers/Staff (no access)

### **How long does it take?**

- Owner signup: 1-3 days
- Manager invitation: 1 day
- Resubmission: 1-2 days

### **Result:**

Controlled, secure system where only Flora admins decide who gets access! ✅
