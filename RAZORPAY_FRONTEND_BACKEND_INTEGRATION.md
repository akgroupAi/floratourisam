# Razorpay Payment System - Frontend & Backend Integration Guide

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Complete Payment Flow](#complete-payment-flow)
4. [API Endpoints](#api-endpoints)
5. [Data Flow](#data-flow)
6. [Frontend Implementation](#frontend-implementation)
7. [Backend Processing](#backend-processing)
8. [Error Handling](#error-handling)
9. [Testing Guide](#testing-guide)
10. [Troubleshooting](#troubleshooting)

---

## System Overview

The Razorpay payment system integrates a **FastAPI backend** with **Razorpay SDK** on the frontend to handle payment processing for medical tourism bookings.

### Key Features
- ✅ Secure payment processing with Razorpay
- ✅ Multi-currency support (INR, USD, EUR, etc.)
- ✅ Order creation with automatic fee calculation
- ✅ Payment verification with HMAC SHA-256 signatures
- ✅ Refund support (full and partial)
- ✅ Transaction logging and audit trail
- ✅ Webhook support for real-time updates

### Technology Stack
- **Backend**: FastAPI + SQLAlchemy 2.0 (async)
- **Database**: PostgreSQL with JSONB support
- **Payment Gateway**: Razorpay API
- **Frontend**: HTML5 + JavaScript (Razorpay SDK)
- **Authentication**: JWT Bearer tokens

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Browser)                        │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  1. User Books Apartment                                 │   │
│  │     - Select dates, guests                              │   │
│  │     - System calculates total_price                     │   │
│  │     - Booking created with status: PENDING              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                       │
│                           ▼                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  2. User Clicks "Pay Now"                                │   │
│  │     - Send booking_id to backend                        │   │
│  │     - Request: POST /api/v1/payments/razorpay/order     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                       │
└───────────────────────────┼───────────────────────────────────────┘
                            │ HTTP Request
                            │ (booking_id, auth token)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI)                           │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  3. Create Razorpay Order Endpoint                       │   │
│  │     - Verify booking exists & calculate fees            │   │
│  │     - Call Razorpay API to create order                 │   │
│  │     - Save Payment record to database                   │   │
│  │     - Return: order_id, key_id, amount, etc.           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                       │
└───────────────────────────┼───────────────────────────────────────┘
                            │ HTTP Response
                            │ (order_id, key_id, amount_paise, etc.)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Browser)                        │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  4. Open Razorpay Checkout Modal                         │   │
│  │     - Use order_id, key_id from response               │   │
│  │     - Razorpay SDK opens payment modal                  │   │
│  │     - User enters card details                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                       │
│                           ▼                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  5. Payment Processing at Razorpay                       │   │
│  │     - User enters OTP/2FA if required                   │   │
│  │     - Payment authorized/declined                       │   │
│  │     - SDK returns: razorpay_payment_id, signature      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                       │
│                           ▼                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  6. Verify Payment                                       │   │
│  │     - Send verification request to backend              │   │
│  │     - Request: POST /api/v1/payments/razorpay/verify    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                       │
└───────────────────────────┼───────────────────────────────────────┘
                            │ HTTP Request
                            │ (payment_id, order_id, razorpay_payment_id, signature)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI)                           │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  7. Verify Payment Endpoint                              │   │
│  │     - Verify HMAC SHA-256 signature                     │   │
│  │     - Mark Payment as COMPLETED                         │   │
│  │     - Mark Booking as paid                              │   │
│  │     - Send confirmation email                           │   │
│  │     - Return: success status                            │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                       │
└───────────────────────────┼───────────────────────────────────────┘
                            │ HTTP Response
                            │ (status: success, payment confirmed)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Browser)                        │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  8. Payment Confirmation                                 │   │
│  │     - Show success message                              │   │
│  │     - Redirect to booking confirmation page             │   │
│  │     - Display booking reference & payment details      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Complete Payment Flow

### Phase 1: Booking Creation (Before Payment)

**Frontend:**
```javascript
// User selects apartment and dates
const bookingData = {
  apartment_id: "uuid-of-apartment",
  check_in_date: "2026-06-15",
  check_out_date: "2026-06-20",
  guests: 2
};

// Call backend to create booking
const bookingResponse = await fetch("/api/v1/bookings/apartment", {
  method: "POST",
  headers: {
    "Authorization": "Bearer " + token,
    "Content-Type": "application/json"
  },
  body: JSON.stringify(bookingData)
});

const booking = await bookingResponse.json();
// Response includes:
// {
//   "id": "booking-uuid",
//   "reference": "APT-20260530-ABC123",
//   "total_price": 150.00,
//   "currency": "USD",
//   "status": "PENDING"
// }
```

**Backend:**
```python
# app/api/v1/bookings.py
@router.post("/apartment")
async def create_apartment_booking(
    data: ApartmentBookingRequest,
    current_user: CurrentUser,
    db: DatabaseSession
):
    """Create apartment booking"""
    service = BookingService(db)
    booking = await service.create_apartment_booking(
        user_id=current_user.id,
        apartment_id=data.apartment_id,
        check_in_date=data.check_in_date,
        check_out_date=data.check_out_date,
        guests=data.guests
    )
    # Calculates: total_price based on nightly_rate × nights
    # Sets: status = PENDING, is_paid = False
    return booking
```

**Database State After Phase 1:**
```
Table: bookings
id                   | booking_type | user_id | total_price | currency | is_paid | status
booking-uuid         | APARTMENT    | user-id | 150.00      | USD      | false   | PENDING
```

---

### Phase 2: Order Creation

**Frontend:**
```javascript
// User clicks "Proceed to Payment"
const orderRequest = {
  booking_id: booking.id
};

const orderResponse = await fetch("/api/v1/payments/razorpay/order", {
  method: "POST",
  headers: {
    "Authorization": "Bearer " + token,
    "Content-Type": "application/json"
  },
  body: JSON.stringify(orderRequest)
});

const orderData = await orderResponse.json();
// Response includes EVERYTHING needed for checkout:
// {
//   "payment_id": "payment-uuid",
//   "order_id": "order_SvZLidgPYGFjD9",
//   "key_id": "rzp_test_SvYnusY18eShJP",
//   "amount": 150.00,
//   "amount_paise": 15000,
//   "currency": "USD",
//   "user_name": "John Doe",
//   "user_email": "john@example.com",
//   "checkout_method": "razorpay_sdk"
// }
```

**Backend:**
```python
# app/services/razorpay_service.py
async def create_order(
    self,
    user_id: UUID,
    booking_id: UUID,
    description: Optional[str] = None,
) -> dict:
    """
    1. Fetch booking from database
    2. Validate booking exists and not already paid
    3. Calculate fees: 2.9% processing + 1% platform = 3.9% total
    4. Convert amount to paise (multiply by 100)
    5. Call Razorpay API to create order
    6. Save Payment record to database
    7. Log transaction
    8. Return order details for frontend
    """
    
    # Fetch booking
    booking = await self._get_booking(booking_id)
    if not booking:
        raise ValueError("Booking not found")
    
    # Calculate amount in paise (INR/USD smallest unit)
    amount = round(booking.total_price, 2)
    amount_paise = int(round(amount * 100))  # 150.00 USD → 15000 paise
    currency = (booking.currency or "INR").upper()
    
    # Call Razorpay API
    response = requests.post(
        "https://api.razorpay.com/v1/orders",
        auth=(self.key_id, self.key_secret),
        json={
            "amount": amount_paise,
            "currency": currency,
            "receipt": f"ord_{booking_id[:34]}",  # Must be ≤ 40 chars
            "notes": {
                "booking_id": str(booking_id),
                "user_id": str(user_id)
            }
        }
    )
    order_data = response.json()
    
    # Save Payment record
    payment = Payment(
        user_id=user_id,
        booking_id=booking_id,
        gateway="razorpay",
        gateway_transaction_id=order_data.get("id"),  # Razorpay Order ID
        gateway_response=order_data,
        amount=amount,
        currency=currency,
        status="PENDING"
    )
    self.db.add(payment)
    await self.db.commit()
    
    return {
        "payment_id": str(payment.id),
        "order_id": order_data.get("id"),
        "key_id": self.key_id,
        "amount_paise": amount_paise,
        "currency": currency
    }
```

**Database State After Phase 2:**
```
Table: payments
id           | booking_id   | gateway   | amount | currency | status   | gateway_transaction_id
payment-uuid | booking-uuid | razorpay  | 150.00 | USD      | PENDING  | order_SvZLidgPYGFjD9

Table: payment_transactions
id  | payment_id   | transaction_type | amount | status  | gateway_transaction_id
txn1| payment-uuid | order_created    | 150.00 | pending | order_SvZLidgPYGFjD9
```

---

### Phase 3: Payment Processing (User Enters Card Details)

**Frontend:**
```javascript
// Use Razorpay SDK to open payment modal
const options = {
  // From orderData response
  key: orderData.key_id,                  // "rzp_test_SvYnusY18eShJP"
  amount: orderData.amount_paise,         // 15000 (in paise)
  currency: orderData.currency,           // "USD"
  order_id: orderData.order_id,           // "order_SvZLidgPYGFjD9"
  
  // Prefill form with user data
  prefill: {
    name: orderData.user_name,            // "John Doe"
    email: orderData.user_email,          // "john@example.com"
    contact: "9999999999"
  },
  
  // Handler for payment success
  handler: function(response) {
    // This is called after user completes payment
    // response contains:
    // {
    //   razorpay_payment_id: "pay_SvZMXvJGvBXbfj",
    //   razorpay_order_id: "order_SvZLidgPYGFjD9",
    //   razorpay_signature: "9ef4dffbfd84f1318f6739a3ce19f9d85851857ae648f114332d8401e0949a3d"
    // }
    
    verifyPayment(response, orderData.payment_id);
  }
};

// Open modal
var rzp = new Razorpay(options);
rzp.open();
```

**What Happens at Razorpay:**
1. User enters card number (e.g., 4111111111111111 for test)
2. User enters expiry and CVV
3. User enters OTP if required (2FA)
4. Payment is authorized by bank
5. Razorpay generates HMAC SHA-256 signature to verify integrity
6. SDK calls handler() function with payment details

---

### Phase 4: Payment Verification

**Frontend:**
```javascript
async function verifyPayment(razorpayResponse, paymentId) {
  // Send payment details to backend for verification
  const verifyRequest = {
    payment_id: paymentId,                          // From step 2
    order_id: razorpayResponse.razorpay_order_id,  // From SDK response
    razorpay_payment_id: razorpayResponse.razorpay_payment_id,
    razorpay_signature: razorpayResponse.razorpay_signature
  };

  const response = await fetch("/api/v1/payments/razorpay/verify", {
    method: "POST",
    headers: {
      "Authorization": "Bearer " + token,
      "Content-Type": "application/json"
    },
    body: JSON.stringify(verifyRequest)
  });

  const result = await response.json();
  
  if (response.ok) {
    // Payment verified! ✅
    alert("Payment successful! Your booking is confirmed.");
    window.location.href = "/booking/" + bookingId;
  } else {
    // Payment verification failed ❌
    alert("Payment verification failed: " + result.detail);
  }
}
```

**Backend:**
```python
# app/services/razorpay_service.py
async def verify_payment(
    self,
    payment_id: UUID,
    order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> dict:
    """
    1. Fetch Payment record from database
    2. Reconstruct signature using order_id + razorpay_payment_id + secret
    3. Compare with received signature (HMAC SHA-256)
    4. If valid: mark Payment as COMPLETED, mark Booking as paid
    5. If invalid: mark Payment as FAILED, raise error
    """
    
    # Fetch payment
    payment = await self._get_payment(payment_id)
    if not payment:
        raise ValueError("Payment not found")
    
    # Verify HMAC signature
    # This ensures Razorpay's response hasn't been tampered with
    signature_message = f"{order_id}|{razorpay_payment_id}"
    expected_signature = hmac.new(
        key=self.key_secret.encode(),
        msg=signature_message.encode(),
        digestmod=hashlib.sha256
    ).hexdigest()
    
    if expected_signature != razorpay_signature:
        raise ValueError("Invalid payment signature - possible tampering detected!")
    
    # ✅ Signature verified! Payment is genuine
    # Update payment status
    payment.status = PaymentStatus.COMPLETED.value
    payment.gateway_transaction_id = razorpay_payment_id
    payment.completed_at = datetime.now(timezone.utc)
    
    # Mark booking as paid
    booking = await self._get_booking(payment.booking_id)
    booking.is_paid = True
    booking.paid_at = datetime.now(timezone.utc)
    booking.status = BookingStatus.CONFIRMED.value
    
    await self.db.commit()
    
    return {
        "status": "success",
        "payment_id": str(payment.id),
        "booking_reference": booking.reference_number
    }
```

**Database State After Phase 4:**
```
Table: payments
id           | booking_id   | status    | gateway_transaction_id | completed_at
payment-uuid | booking-uuid | COMPLETED | pay_SvZMXvJGvBXbfj     | 2026-05-30 12:04:59

Table: bookings
id           | status      | is_paid | paid_at
booking-uuid | CONFIRMED   | true    | 2026-05-30 12:04:59
```

---

## API Endpoints

### 1. Create Razorpay Order

**Endpoint:** `POST /api/v1/payments/razorpay/order`

**Request:**
```json
{
  "booking_id": "f7c3b8d1-9c5a-4b21-a1d2-3e4f5g6h7i8j",
  "description": "Optional payment description"
}
```

**Response (200 OK):**
```json
{
  "payment_id": "f7c3b8d1-9c5a-4b21-a1d2-3e4f5g6h7i8j",
  "reference_number": "APT-20260530-ABC123",
  "order_id": "order_SvZLidgPYGFjD9",
  "amount": 150.00,
  "amount_paise": 15000,
  "currency": "USD",
  "key_id": "rzp_test_SvYnusY18eShJP",
  "user_name": "John Doe",
  "user_email": "john@example.com",
  "description": "Apartment booking",
  "checkout_method": "razorpay_sdk",
  "integration_hint": "Use order_id and key_id with Razorpay.js SDK to open payment modal"
}
```

**Error Response (400 Bad Request):**
```json
{
  "detail": "Booking not found" 
  // or: "Booking is already paid"
  // or: "Invalid booking amount: 0"
  // or: "Razorpay is not configured"
}
```

**Headers:**
```
Authorization: Bearer {jwt_token}
Content-Type: application/json
```

---

### 2. Verify Razorpay Payment

**Endpoint:** `POST /api/v1/payments/razorpay/verify`

**Request:**
```json
{
  "payment_id": "f7c3b8d1-9c5a-4b21-a1d2-3e4f5g6h7i8j",
  "order_id": "order_SvZLidgPYGFjD9",
  "razorpay_payment_id": "pay_SvZMXvJGvBXbfj",
  "razorpay_signature": "9ef4dffbfd84f1318f6739a3ce19f9d85851857ae648f114332d8401e0949a3d"
}
```

**Response (200 OK):**
```json
{
  "status": "success",
  "payment_id": "f7c3b8d1-9c5a-4b21-a1d2-3e4f5g6h7i8j",
  "order_id": "order_SvZLidgPYGFjD9",
  "razorpay_payment_id": "pay_SvZMXvJGvBXbfj",
  "amount": 150.00,
  "booking_reference": "APT-20260530-ABC123"
}
```

**Error Response (400 Bad Request):**
```json
{
  "detail": "Invalid payment signature - possible tampering detected!"
  // or: "Payment not found"
  // or: "Payment already verified"
}
```

---

### 3. Razorpay Webhook (Server-to-Server)

**Endpoint:** `POST /api/v1/payments/razorpay/webhook`

**When it's called:**
- Razorpay sends webhook events asynchronously
- Used for real-time payment status updates
- Not required for payment to work (verification endpoint is primary)

**Supported Events:**
- `payment.authorized` - Payment authorized by bank
- `payment.failed` - Payment failed
- `refund.created` - Refund initiated
- `refund.failed` - Refund failed

---

### 4. Get Payments List

**Endpoint:** `GET /api/v1/payments`

**Query Parameters:**
- `page` (optional, default: 1)
- `page_size` (optional, default: 20)

**Response:**
```json
{
  "items": [
    {
      "id": "payment-uuid",
      "amount": 150.00,
      "currency": "USD",
      "status": "COMPLETED",
      "gateway": "razorpay",
      "created_at": "2026-05-30T12:04:59Z"
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

---

### 5. Refund Payment

**Endpoint:** `POST /api/v1/payments/{payment_id}/refund`

**Query Parameters:**
- `amount` (optional) - Partial refund amount. If not provided, refunds full amount
- `reason` (optional) - Refund reason

**Response:**
```json
{
  "status": "refunded",
  "payment_id": "payment-uuid",
  "refund_id": "refund_SvZLidgPYGFjD9",
  "refund_amount": 150.00,
  "refund_at": "2026-05-30T12:05:00Z"
}
```

---

## Data Flow

### Request/Response Cycle

```
1. FRONTEND → BACKEND
   POST /api/v1/payments/razorpay/order
   Headers: Authorization: Bearer {token}
   Body: { booking_id: "uuid" }
   
   ↓
   
2. BACKEND PROCESSES
   a) Authenticate user via JWT token
   b) Fetch booking from database
   c) Validate booking (exists, not paid)
   d) Calculate: amount, fees, currency
   e) Call Razorpay API
   f) Save Payment record to database
   g) Log transaction
   
   ↓
   
3. BACKEND → FRONTEND
   Status: 200 OK
   Body: {
     payment_id: "uuid",
     order_id: "order_xxx",
     key_id: "rzp_test_xxx",
     amount_paise: 15000,
     ...
   }
   
   ↓
   
4. FRONTEND OPENS RAZORPAY SDK MODAL
   var options = {
     key: response.key_id,
     amount: response.amount_paise,
     order_id: response.order_id,
     handler: function(paymentResponse) { ... }
   }
   var rzp = new Razorpay(options);
   rzp.open();
   
   ↓
   
5. USER ENTERS CARD & COMPLETES PAYMENT AT RAZORPAY
   (This happens in Razorpay's hosted page, not your server)
   
   ↓
   
6. RAZORPAY → FRONTEND (SDK handler callback)
   handler({
     razorpay_payment_id: "pay_xxx",
     razorpay_order_id: "order_xxx",
     razorpay_signature: "hash_xxx"
   })
   
   ↓
   
7. FRONTEND → BACKEND
   POST /api/v1/payments/razorpay/verify
   Headers: Authorization: Bearer {token}
   Body: {
     payment_id: "uuid",
     order_id: "order_xxx",
     razorpay_payment_id: "pay_xxx",
     razorpay_signature: "hash_xxx"
   }
   
   ↓
   
8. BACKEND VERIFIES SIGNATURE
   signature_message = "{order_id}|{razorpay_payment_id}"
   expected = HMAC-SHA256(signature_message, key_secret)
   if (expected == received_signature) {
     ✅ VALID - Payment is genuine
   } else {
     ❌ INVALID - Possible tampering
   }
   
   ↓
   
9. BACKEND UPDATES DATABASE
   - Payment.status = COMPLETED
   - Payment.gateway_transaction_id = razorpay_payment_id
   - Booking.is_paid = true
   - Booking.status = CONFIRMED
   
   ↓
   
10. BACKEND → FRONTEND
    Status: 200 OK
    Body: {
      status: "success",
      payment_id: "uuid",
      booking_reference: "APT-20260530-ABC123"
    }
    
    ↓
    
11. FRONTEND SHOWS SUCCESS MESSAGE
    alert("Payment successful!");
    redirect to booking confirmation page
```

---

## Frontend Implementation

### Complete Example (Step-by-Step)

```html
<!DOCTYPE html>
<html>
<head>
    <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
</head>
<body>
    <div id="app">
        <h1>Book Your Apartment</h1>
        <button onclick="bookApartment()">Book Now</button>
    </div>

    <script>
        // Configuration
        const API_BASE = "http://13.201.5.161:8000";
        let authToken = localStorage.getItem('auth_token');
        let currentBooking = null;

        // Step 1: User selects apartment and clicks Book
        async function bookApartment() {
            const bookingData = {
                apartment_id: "apartment-uuid",
                check_in_date: "2026-06-15",
                check_out_date: "2026-06-20",
                guests: 2
            };

            const response = await fetch(`${API_BASE}/api/v1/bookings/apartment`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${authToken}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(bookingData)
            });

            currentBooking = await response.json();
            // currentBooking contains: id, total_price, currency, status

            // Step 2: Show payment button
            document.getElementById('app').innerHTML = `
                <h2>Booking Confirmed</h2>
                <p>Total: $${currentBooking.total_price}</p>
                <button onclick="initiatePayment()">Pay Now</button>
            `;
        }

        // Step 2: User clicks "Pay Now"
        async function initiatePayment() {
            // Step 3: Create Razorpay Order
            const orderRequest = {
                booking_id: currentBooking.id
            };

            const response = await fetch(`${API_BASE}/api/v1/payments/razorpay/order`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${authToken}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(orderRequest)
            });

            if (!response.ok) {
                alert('Failed to create order');
                return;
            }

            const orderData = await response.json();
            // orderData contains: order_id, key_id, amount_paise, etc.

            // Step 4: Open Razorpay SDK Modal
            const options = {
                key: orderData.key_id,
                amount: orderData.amount_paise,
                currency: orderData.currency,
                name: 'Flora Medical Tourism',
                description: orderData.description,
                order_id: orderData.order_id,
                
                prefill: {
                    name: orderData.user_name,
                    email: orderData.user_email,
                    contact: '9999999999'
                },
                
                handler: function(response) {
                    // Step 5: Payment completed, verify signature
                    verifyPayment(response, orderData.payment_id);
                },
                
                modal: {
                    ondismiss: function() {
                        alert('Payment cancelled');
                    }
                }
            };

            var rzp = new Razorpay(options);
            rzp.open();
        }

        // Step 5: Verify payment with backend
        async function verifyPayment(paymentResponse, paymentId) {
            const verifyRequest = {
                payment_id: paymentId,
                order_id: paymentResponse.razorpay_order_id,
                razorpay_payment_id: paymentResponse.razorpay_payment_id,
                razorpay_signature: paymentResponse.razorpay_signature
            };

            const response = await fetch(`${API_BASE}/api/v1/payments/razorpay/verify`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${authToken}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(verifyRequest)
            });

            if (response.ok) {
                const result = await response.json();
                alert('✅ Payment successful! Your booking is confirmed.');
                // Redirect to booking details
                window.location.href = `/booking/${result.payment_id}`;
            } else {
                const error = await response.json();
                alert(`❌ Payment verification failed: ${error.detail}`);
            }
        }
    </script>
</body>
</html>
```

---

## Backend Processing

### Service Layer: RazorpayService

**Location:** `app/services/razorpay_service.py`

**Key Methods:**

```python
class RazorpayService:
    def __init__(self, db: AsyncSession):
        """Initialize with database session and Razorpay credentials from config"""
        self.db = db
        self.key_id = settings.RAZORPAY_KEY_ID
        self.key_secret = settings.RAZORPAY_KEY_SECRET
    
    async def create_order(
        self,
        user_id: UUID,
        booking_id: UUID,
        description: Optional[str] = None,
    ) -> dict:
        """
        Create a Razorpay order and save Payment record.
        Returns all data needed for frontend checkout.
        """
        # Validation
        # ↓
        # Razorpay API call
        # ↓
        # Database save
        # ↓
        # Return response
    
    async def verify_payment(
        self,
        payment_id: UUID,
        order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> dict:
        """
        Verify payment signature and update payment/booking status.
        """
        # Signature verification (HMAC SHA-256)
        # ↓
        # Update Payment status
        # ↓
        # Update Booking status
        # ↓
        # Return success response
    
    async def refund_payment(
        self,
        payment_id: UUID,
        amount: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> dict:
        """
        Initiate refund via Razorpay API.
        Supports full and partial refunds.
        """
```

### API Layer: PaymentEndpoints

**Location:** `app/api/v1/payments.py`

```python
@router.post("/razorpay/order", response_model=RazorpayOrderResponse)
async def create_razorpay_order(
    data: RazorpayOrderRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """
    HTTP endpoint that orchestrates order creation.
    
    Flow:
    1. Extract user from JWT token (via CurrentUser dependency)
    2. Extract booking_id from request body
    3. Call RazorpayService.create_order()
    4. Return response with order details
    5. Handle errors with appropriate HTTP status codes
    """

@router.post("/razorpay/verify", response_model=PaymentVerifyResponse)
async def verify_razorpay_payment(
    data: RazorpayPaymentVerifyRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """
    HTTP endpoint that verifies payment signature.
    
    Flow:
    1. Extract user from JWT token
    2. Extract payment details from request
    3. Call RazorpayService.verify_payment()
    4. Return success/failure response
    5. If successful: booking is now marked as paid
    """
```

---

## Error Handling

### Frontend Error Handling

```javascript
// Always wrap API calls in try-catch
async function safeFetch(url, options) {
    try {
        const response = await fetch(url, options);
        
        if (!response.ok) {
            // HTTP error (4xx or 5xx)
            const error = await response.json();
            throw new Error(error.detail || `HTTP ${response.status}`);
        }
        
        return await response.json();
        
    } catch (error) {
        // Network error or parse error
        console.error('API Error:', error);
        alert(`Error: ${error.message}`);
        return null;
    }
}

// Usage
const orderData = await safeFetch(`${API_BASE}/api/v1/payments/razorpay/order`, {
    method: 'POST',
    headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({ booking_id })
});

if (!orderData) {
    // Handle error
    return;
}

// Proceed with payment
```

### Backend Error Handling

```python
# app/services/razorpay_service.py
async def create_order(...):
    try:
        # Validate inputs
        if not booking:
            raise ValueError("Booking not found")
        
        if booking.is_paid:
            raise ValueError("Booking is already paid")
        
        # Razorpay API call
        order_response = requests.post(...)
        order_response.raise_for_status()  # Raise if HTTP error
        order_data = order_response.json()
        
    except requests.RequestException as e:
        # Razorpay API error
        error_response = e.response.json() if e.response else None
        logger.error(
            "razorpay_order_creation_failed",
            error_response=error_response,
            status_code=e.response.status_code if e.response else None
        )
        raise ValueError(f"Failed to create Razorpay order: {str(e)}")
    
    except ValueError as e:
        # Validation error (booking not found, etc.)
        logger.error("order_creation_validation_error", error=str(e))
        raise

# app/api/v1/payments.py
@router.post("/razorpay/order")
async def create_razorpay_order(...):
    service = RazorpayService(db)
    try:
        result = await service.create_order(...)
        return result
    except ValueError as e:
        # Convert service error to HTTP error response
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
```

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `"Booking not found"` | booking_id doesn't exist | Verify booking was created successfully |
| `"Booking is already paid"` | Double payment attempt | Check booking.is_paid before creating order |
| `"Invalid payment signature"` | Tampered payment data | Verify Razorpay credentials are correct |
| `"Razorpay is not configured"` | Missing credentials in .env | Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET |
| `"Invalid currency: XXX"` | Unsupported currency code | Use INR, USD, EUR, GBP, or AED |
| `"Amount too small"` | Amount < 1 paise | Ensure booking amount > 0 |

---

## Testing Guide

### Test Credentials

```
Razorpay Test Account:
- KEY_ID: rzp_test_SvYnusY18eShJP
- KEY_SECRET: SHaCPD0rIovrFoEH7zYpdxjy
- Currency: INR (or USD for international)
```

### Test Cards

| Card | Number | Status |
|------|--------|--------|
| Visa Success | 4111111111111111 | ✅ Always succeeds |
| Visa Failure | 4000000000000002 | ❌ Always fails |
| Any card + wrong OTP | Any | ❌ Fails OTP verification |

### Test Flow (Step-by-Step)

**1. Create Test User**
```bash
curl -X POST http://13.201.5.161:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "Test@123456"
  }'
```

**2. Login**
```bash
curl -X POST http://13.201.5.161:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "Test@123456"
  }'

# Save the token from response
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**3. Create Apartment Booking**
```bash
curl -X POST http://13.201.5.161:8000/api/v1/bookings/apartment \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "apartment_id": "existing-apartment-uuid",
    "check_in_date": "2026-06-15",
    "check_out_date": "2026-06-20",
    "guests": 2
  }'

# Save booking_id from response
BOOKING_ID="booking-uuid"
```

**4. Create Razorpay Order**
```bash
curl -X POST http://13.201.5.161:8000/api/v1/payments/razorpay/order \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "booking_id": "'$BOOKING_ID'"
  }'

# Response includes: order_id, key_id, amount_paise
```

**5. Open in Browser**
- Use the `RAZORPAY_FRONTEND_INTEGRATION.html` file
- Enter the token and booking_id
- Click "Create Order"
- Click "Open Checkout"
- Use test card: 4111111111111111
- Complete payment

**6. Verify Payment**
- Backend automatically verifies on completion
- Check database for updated Payment and Booking status

---

## Troubleshooting

### "400 Client Error: Bad Request"

**Cause:** Receipt field exceeds 40 characters  
**Fix:** Already fixed in v1 - receipt is now `ord_{booking_id[:34]}`

### "Invalid payment signature"

**Cause:** HMAC signature verification failed  
**Solution:**
1. Check RAZORPAY_KEY_SECRET is correct
2. Verify razorpay_signature from SDK is not corrupted
3. Check order_id and razorpay_payment_id are correct format

### "Booking not found"

**Cause:** booking_id doesn't exist in database  
**Solution:**
1. Verify booking was created successfully
2. Use exact UUID from booking creation response
3. Check if booking was soft-deleted

### "Razorpay SDK not opening modal"

**Cause:** Missing SDK script or invalid options  
**Solution:**
```html
<!-- Ensure script is included -->
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>

<!-- Check all required fields -->
{
  key: "rzp_test_xxx",           // ✅ Required
  amount: 15000,                 // ✅ Required, in paise
  currency: "USD",               // ✅ Required
  order_id: "order_xxx",         // ✅ Required
  handler: function(response) {} // ✅ Required
}
```

### "Payment verified but booking not marked as paid"

**Cause:** Transaction was committed but application didn't sync  
**Solution:**
```sql
-- Check database directly
SELECT * FROM bookings WHERE id = 'booking-uuid';
SELECT * FROM payments WHERE booking_id = 'booking-uuid';

-- Both should have is_paid = true and status = COMPLETED
```

---

## Key Takeaways

✅ **Frontend** generates order via `/razorpay/order` endpoint  
✅ **Razorpay SDK** opens payment modal on client side  
✅ **User** enters payment details in Razorpay's hosted modal (secure)  
✅ **Razorpay** processes payment and returns signature  
✅ **Frontend** verifies signature via `/razorpay/verify` endpoint  
✅ **Backend** validates HMAC and updates database  
✅ **Booking** is marked as paid in database  

The entire flow is **secure** because:
- Payment details never touch your server (handled by Razorpay)
- HMAC SHA-256 signature prevents tampering
- JWT token ensures authenticated requests
- Database transactions ensure data consistency

---

**Need help?** Check the interactive test page: `RAZORPAY_FRONTEND_INTEGRATION.html`
