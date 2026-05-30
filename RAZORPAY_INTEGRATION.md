# Razorpay Payment Gateway Integration

## Overview

This document explains how to set up and use the **Razorpay payment gateway** in the Flora Medical Tourism Platform. Razorpay has replaced Stripe as the primary payment gateway, though Stripe endpoints remain available for backward compatibility.

---

## Environment Configuration

### 1. Add Razorpay Credentials to `.env`

```bash
# Razorpay Configuration
RAZORPAY_KEY_ID=your_razorpay_key_id
RAZORPAY_KEY_SECRET=your_razorpay_key_secret
RAZORPAY_WEBHOOK_SECRET=your_razorpay_webhook_secret
RAZORPAY_CURRENCY=INR  # or USD, EUR, etc. (Default: INR)

# Optional: Keep Stripe for backward compatibility
STRIPE_SECRET_KEY=your_stripe_secret_key
STRIPE_PUBLISHABLE_KEY=your_stripe_publishable_key
STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret
```

### 2. Get Your Credentials from Razorpay Dashboard

1. Go to [Razorpay Dashboard](https://dashboard.razorpay.com)
2. Login with your account
3. Navigate to **Settings → API Keys**
4. Copy your **Key ID** and **Key Secret**
5. For webhooks, go to **Settings → Webhooks** and create a new webhook

---

## API Endpoints

### Razorpay Flow Diagram

```
Frontend                Backend                Razorpay
   |                       |                        |
   |--1. Create Order----->|                        |
   |<--Order Details-------|                        |
   |                       |---2. Create Order----->|
   |                       |<--Order Created--------|
   |                       |                        |
   |--3. Show Payment------>|  (Display in SDK)     |
   |    Modal w/ SDK        |                        |
   |                        |                        |
   |---4. User Pays-------->|                        |
   |   (in Razorpay modal)  |---Webhook Event------>|
   |                        |<--200 OK--------------|
   |                        |                        |
   |--5. Verify Payment---->|                        |
   |<--Payment Verified-----|                        |
```

---

## Step-by-Step Implementation Guide

### Backend: Create Order

**Endpoint:** `POST /api/v1/payments/razorpay/order`

**Request:**
```json
{
  "booking_id": "550e8400-e29b-41d4-a716-446655440000",
  "description": "Consultation Booking"
}
```

**Response:**
```json
{
  "payment_id": "550e8400-e29b-41d4-a716-446655440001",
  "reference_number": "PAY-20240124-ABC123",
  "order_id": "order_30003052581",
  "amount": 5000,
  "amount_paise": 500000,
  "currency": "INR",
  "key_id": "rzp_test_abcd1234",
  "user_name": "John Doe",
  "user_email": "john@example.com",
  "description": "Consultation Booking"
}
```

### Frontend: Initialize Razorpay SDK

```html
<!-- Include Razorpay SDK -->
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
```

```javascript
// After receiving order from backend
async function initiatePayment(orderResponse) {
  const options = {
    key: orderResponse.key_id,              // Key ID from backend
    amount: orderResponse.amount_paise,     // Amount in paise (smallest unit)
    currency: orderResponse.currency,       // "INR"
    name: "Flora Medical Tourism",
    description: orderResponse.description,
    order_id: orderResponse.order_id,       // Order ID from backend
    prefill: {
      name: orderResponse.user_name,
      email: orderResponse.user_email,
      contact: userPhone,                    // Phone number from user
    },
    notes: {
      payment_id: orderResponse.payment_id,
      booking_id: orderResponse.booking_id,
    },
    theme: {
      color: "#3399cc",
    },
    handler: async function (response) {
      // Payment successful, verify on backend
      await verifyPayment({
        payment_id: orderResponse.payment_id,
        order_id: orderResponse.order_id,
        razorpay_payment_id: response.razorpay_payment_id,
        razorpay_signature: response.razorpay_signature,
      });
    },
    modal: {
      ondismiss: function () {
        console.log("Payment modal closed");
      },
    },
  };

  const rzp = new Razorpay(options);
  rzp.open();
}
```

### Backend: Verify Payment

**Endpoint:** `POST /api/v1/payments/razorpay/verify`

**Request:**
```json
{
  "payment_id": "550e8400-e29b-41d4-a716-446655440001",
  "order_id": "order_30003052581",
  "razorpay_payment_id": "pay_30003052581",
  "razorpay_signature": "9ef4dffbfd84f1318f6739a3ce19f9d85851857ae648f114332d8401e0949a3d"
}
```

**Response:**
```json
{
  "payment_id": "550e8400-e29b-41d4-a716-446655440001",
  "status": "completed",
  "razorpay_payment_id": "pay_30003052581"
}
```

---

## Webhook Integration

### Razorpay Webhook Events

Razorpay sends webhooks for various payment events. Configure in dashboard: **Settings → Webhooks**

**Webhook URL:** `https://your-domain.com/api/v1/payments/razorpay/webhook`

**Webhook Secret:** Use the secret from dashboard settings

### Handled Events

| Event | Status | Action |
|-------|--------|--------|
| `payment.authorized` | Success | Mark payment as COMPLETED |
| `payment.failed` | Failed | Mark payment as FAILED |
| `refund.created` | Refunded | Update refund status |
| `refund.failed` | Failed | Log refund failure |

### Example Webhook Payload

```json
{
  "event": "payment.authorized",
  "payload": {
    "payment": {
      "id": "pay_30003052581",
      "entity": "payment",
      "amount": 500000,
      "currency": "INR",
      "status": "authorized",
      "order_id": "order_30003052581",
      "email": "john@example.com",
      "contact": "+919876543210"
    }
  }
}
```

---

## Amount Handling

### Critical: Paise vs Rupees

Razorpay (like Stripe) works with the **smallest currency unit**:

- **INR (Indian Rupee)**: 1 rupee = 100 **paise**
- **USD**: 1 dollar = 100 **cents**
- **EUR**: 1 euro = 100 **cents**

**Always multiply amounts by 100 before sending to Razorpay:**

```python
# In app/services/razorpay_service.py
amount = booking.total_price        # Example: 150.50 (rupees/dollars)
amount_paise = int(round(amount * 100))  # Convert to: 15050 (paise/cents)

# Send amount_paise to Razorpay API
requests.post(
    "https://api.razorpay.com/v1/orders",
    json={
        "amount": amount_paise,  # 15050, not 150.50
        "currency": "INR",
    }
)
```

### Fee Calculation

```python
amount = 150.50  # Booking amount in rupees/dollars

# Processing fee: 2.9%
processing_fee = amount * 0.029  # = 4.36

# Platform fee: 1%
platform_fee = amount * 0.01      # = 1.51

# Net amount received
net_amount = amount - processing_fee - platform_fee  # = 144.63
```

---

## Refund Handling

### Full Refund

```bash
POST /api/v1/payments/{payment_id}/refund
{
  "reason": "Appointment cancelled by patient"
}
```

### Partial Refund

```bash
POST /api/v1/payments/{payment_id}/refund
{
  "amount": 100.00,
  "reason": "Partial refund for cancellation"
}
```

### Backend: Refund Flow

1. User/Admin initiates refund via `/payments/{payment_id}/refund`
2. Service verifies payment exists and is completed
3. Calls Razorpay Refund API
4. Updates payment status to `REFUNDED` or `PARTIALLY_REFUNDED`
5. Logs transaction in `payment_transactions` table

---

## Testing Razorpay Integration

### 1. Get Test Credentials

From Razorpay Dashboard (Test Mode):
- Key ID: `rzp_test_xxxxxx`
- Key Secret: `xxxxxxxxxxxxxx`

### 2. Use Test Payment Methods

| Card Type | Card Number | CVV | Expiry |
|-----------|------------|-----|--------|
| Visa | 4111 1111 1111 1111 | Any 3 digits | Any future date |
| Mastercard | 5555 5555 5555 4444 | Any 3 digits | Any future date |

### 3. Test with cURL

```bash
# Create an order
curl -X POST https://api.razorpay.com/v1/orders \
  -H "Authorization: Basic $(echo -n 'key_id:key_secret' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 50000,
    "currency": "INR",
    "receipt": "receipt_123"
  }'

# Response
{
  "id": "order_30003052581",
  "entity": "order",
  "amount": 50000,
  "amount_paid": 0,
  "amount_due": 50000,
  "currency": "INR",
  "receipt": "receipt_123",
  "status": "created"
}
```

---

## Switching from Stripe to Razorpay

### Key Differences

| Feature | Stripe | Razorpay |
|---------|--------|----------|
| Primary Market | Global (USD/EUR) | India (INR) |
| Integration | Checkout Sessions | Orders API |
| Main Payment Methods | Cards mostly | Cards, UPI, Netbanking, Wallets |
| Smallest Unit | Cents | Paise (INR) |
| Webhook Auth | HMAC SHA-256 | HMAC SHA-256 |
| Fees | ~2.9% + $0.30 | ~2% + no fixed fee |

### Backward Compatibility

Both Stripe and Razorpay endpoints are available:

- **Stripe:** `POST /api/v1/payments/stripe/checkout`
- **Razorpay:** `POST /api/v1/payments/razorpay/order`

To fully switch, update your frontend to use Razorpay endpoints. Stripe endpoints remain for legacy support.

---

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| Invalid signature | Webhook signature mismatch | Verify RAZORPAY_WEBHOOK_SECRET is correct |
| Order not found | Order ID doesn't exist in Razorpay | Check order_id is correct |
| Payment not found | Payment not yet created | Ensure order exists before verifying |
| Invalid amount | Amount format incorrect | Amount should be in paise (multiply by 100) |

### Debug Logs

Check logs for Razorpay errors:

```python
# In app/services/razorpay_service.py
logger.error("razorpay_order_creation_failed", error=str(e))
logger.error("razorpay_payment_failed", payment_id=str(payment.id), reason=error_description)
```

---

## File Changes Summary

### New Files
- `app/services/razorpay_service.py` - Razorpay API integration

### Modified Files
- `app/core/config.py` - Added Razorpay config variables
- `app/api/v1/payments.py` - Added Razorpay endpoints
- `requirements.txt` - Added `requests` and `razorpay` packages

### Unchanged (Backward Compatible)
- `app/models/payment.py` - No schema changes needed
- `app/schemas/payment.py` - Works for both gateways
- `app/services/payment_service.py` - Generic payment logic

---

## Deployment Checklist

- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Set `RAZORPAY_KEY_ID` in production `.env`
- [ ] Set `RAZORPAY_KEY_SECRET` in production `.env`
- [ ] Set `RAZORPAY_WEBHOOK_SECRET` in production `.env`
- [ ] Configure webhook URL in Razorpay dashboard
- [ ] Test with sample orders in test mode
- [ ] Update frontend to use `/api/v1/payments/razorpay/*` endpoints
- [ ] Run migrations (no DB schema changes required)
- [ ] Monitor logs for webhook events

---

## Support

For issues or questions:
1. Check [Razorpay API Docs](https://razorpay.com/docs/api/)
2. Review logs in `app/core/logging.py`
3. Test webhook signature verification in isolation
