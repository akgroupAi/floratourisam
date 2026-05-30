# Razorpay Integration - Quick Reference

## TL;DR: Stripe → Razorpay Migration

### In 30 Seconds

Replace your **Stripe Checkout** with **Razorpay Orders**:

```javascript
// BEFORE (Stripe)
const response = await fetch('/api/v1/payments/stripe/checkout', {
  method: 'POST',
  body: JSON.stringify({ booking_id: bookingId })
});
const { checkout_url } = await response.json();
window.location.href = checkout_url;

// AFTER (Razorpay)
const response = await fetch('/api/v1/payments/razorpay/order', {
  method: 'POST',
  body: JSON.stringify({ booking_id: bookingId })
});
const orderData = await response.json();

const rzp = new Razorpay({
  key: orderData.key_id,
  amount: orderData.amount_paise,
  currency: orderData.currency,
  order_id: orderData.order_id,
  handler: verifyPayment,
});
rzp.open();
```

---

## API Endpoints Comparison

### Create Payment

| Stripe | Razorpay |
|--------|----------|
| `POST /payments/stripe/checkout` | `POST /payments/razorpay/order` |
| Returns: `checkout_url` | Returns: `key_id`, `order_id`, `amount_paise` |
| Frontend: Redirect to URL | Frontend: Open Razorpay Modal |

### Verify Payment

| Stripe | Razorpay |
|--------|----------|
| Webhook only | `POST /payments/razorpay/verify` + Webhook |
| (Session verified via event) | (Verify immediately after payment) |

### Refund Payment

| Stripe | Razorpay |
|--------|----------|
| `POST /payments/{id}/refund` | `POST /payments/{id}/refund` |
| Same endpoint for both | Same endpoint for both |

---

## Environment Variables

### Add to `.env`:

```bash
RAZORPAY_KEY_ID=rzp_test_xxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxx
RAZORPAY_WEBHOOK_SECRET=whsec_xxxxx
RAZORPAY_CURRENCY=INR
```

### Where to Get These:

1. Go to [Razorpay Dashboard](https://dashboard.razorpay.com)
2. **Settings** → **API Keys** → Copy Key ID and Key Secret
3. **Settings** → **Webhooks** → Create webhook at `https://yourdomain.com/api/v1/payments/razorpay/webhook`
4. Copy webhook secret from webhook details

---

## Amount Handling

### IMPORTANT: Always Multiply by 100!

Razorpay works in **paise** (for INR) or **cents** (for USD/EUR):

```javascript
// WRONG ❌
amount: 150.50  // This is 1 paisa!

// CORRECT ✅
amount: 15050   // This is 150.50 rupees
```

The backend returns `amount_paise` already calculated. Use that directly:

```javascript
const options = {
  amount: orderData.amount_paise,  // Already in paise
  // ...
};
```

---

## Frontend Implementation

### Step 1: Include Razorpay SDK

```html
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
```

### Step 2: Create Order

```javascript
async function createOrder(bookingId) {
  const res = await fetch('/api/v1/payments/razorpay/order', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ booking_id: bookingId })
  });
  
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail);
  }
  
  return res.json();
}
```

### Step 3: Open Payment Modal

```javascript
async function initiatePayment(bookingId, userPhone) {
  try {
    const orderData = await createOrder(bookingId);
    
    const options = {
      key: orderData.key_id,
      amount: orderData.amount_paise,
      currency: orderData.currency,
      order_id: orderData.order_id,
      name: 'Flora Medical Tourism',
      description: orderData.description,
      prefill: {
        name: orderData.user_name,
        email: orderData.user_email,
        contact: userPhone,
      },
      handler: (response) => verifyPayment(orderData, response),
      theme: { color: '#3399cc' },
    };
    
    const rzp = new Razorpay(options);
    rzp.open();
  } catch (error) {
    alert('Error: ' + error.message);
  }
}
```

### Step 4: Verify Payment

```javascript
async function verifyPayment(orderData, paymentResponse) {
  const verifyRes = await fetch('/api/v1/payments/razorpay/verify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      payment_id: orderData.payment_id,
      order_id: orderData.order_id,
      razorpay_payment_id: paymentResponse.razorpay_payment_id,
      razorpay_signature: paymentResponse.razorpay_signature,
    })
  });
  
  if (!verifyRes.ok) {
    alert('Payment verification failed!');
    return;
  }
  
  const result = await verifyRes.json();
  alert('Payment successful! ID: ' + result.razorpay_payment_id);
  window.location.href = '/bookings/' + orderData.booking_id;
}
```

---

## Complete Flow Example

```
User clicks "Pay Now"
         ↓
   createOrder(bookingId)
         ↓
   POST /api/v1/payments/razorpay/order
         ↓
   Returns: {
     payment_id: "uuid",
     order_id: "order_123",
     key_id: "rzp_test_xxx",
     amount_paise: 500000,
     currency: "INR"
   }
         ↓
   Open Razorpay Modal with order_id
         ↓
   User enters card details in modal
   (Razorpay handles everything)
         ↓
   Payment succeeds
         ↓
   Handler called with response:
   {
     razorpay_payment_id: "pay_123",
     razorpay_signature: "hex_signature"
   }
         ↓
   verifyPayment() sends to backend
         ↓
   POST /api/v1/payments/razorpay/verify
         ↓
   Signature verified ✓
   Payment marked as COMPLETED
         ↓
   Return success
         ↓
   Redirect to booking details page
```

---

## Testing

### Test Cards

Use in Razorpay **Test Mode**:

```
Card: 4111 1111 1111 1111
CVV: 123
Expiry: 12/25
OTP: Any 6 digits

Card: 5555 5555 5555 4444
CVV: 123
Expiry: 12/25
OTP: Any 6 digits
```

### Local Testing

```bash
# 1. Set test credentials in .env
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...

# 2. Create order
curl -X POST http://localhost:8000/api/v1/payments/razorpay/order \
  -H "Content-Type: application/json" \
  -d '{"booking_id": "550e8400-e29b-41d4-a716-446655440000"}'

# 3. In browser: Use test card from table above
```

---

## Troubleshooting

### "Razorpay is not configured"
- [ ] Check `RAZORPAY_KEY_ID` is set in `.env`
- [ ] Check `RAZORPAY_KEY_SECRET` is set in `.env`
- [ ] Restart server after changing `.env`

### "Order not found in Razorpay"
- [ ] Ensure booking exists and has valid `total_price`
- [ ] Check amount is positive

### "Invalid signature"
- [ ] Verify `RAZORPAY_WEBHOOK_SECRET` matches dashboard
- [ ] Ensure webhook URL is publicly accessible
- [ ] Check webhook is set to "Active" in dashboard

### Payment marked as failed
- [ ] Check logs: `logger.error("razorpay_payment_failed", ...)`
- [ ] Verify test card is used in test mode
- [ ] Check OTP entry in payment modal

### Webhook not received
- [ ] Configure URL in **Settings → Webhooks**
- [ ] Webhook secret must match `RAZORPAY_WEBHOOK_SECRET`
- [ ] Endpoint must return `{"status": "ok"}` (status 200)
- [ ] Use `ngrok` or similar for local testing with tunneling

---

## Code Files Modified

1. **app/core/config.py** - Added Razorpay config
2. **app/services/razorpay_service.py** - New Razorpay service
3. **app/api/v1/payments.py** - New endpoints for Razorpay
4. **requirements.txt** - Added `requests` and `razorpay` packages

---

## Key Differences: Stripe vs Razorpay

| Aspect | Stripe | Razorpay |
|--------|--------|----------|
| **Flow** | Redirect to checkout URL | Open modal, verify on return |
| **Currencies** | USD, EUR, GBP, ... | **INR primary**, others via conversion |
| **Payment Methods** | Mostly cards | Cards, UPI, Wallets, Netbanking |
| **Fees** | ~2.9% + $0.30 | ~2% per transaction |
| **Min Webhook Code** | None | Must verify signature |
| **Integration Effort** | Medium (redirect) | Low (modal) |
| **Ideal for** | Global customers | India-focused |

---

## Next Steps

1. **Backend**: Update `.env` with Razorpay credentials ✅
2. **Frontend**: Update payment initiation code (see example above)
3. **Test**: Use test credentials and test cards
4. **Deploy**: Move credentials to production `.env`
5. **Monitor**: Watch logs for webhook events

---

## Support Resources

- [Razorpay API Docs](https://razorpay.com/docs/api/)
- [Razorpay Dashboard](https://dashboard.razorpay.com)
- [Local Webhook Testing](https://razorpay.com/docs/webhooks/test-integration/) (use ngrok)
- Backend Logs: Check `app/core/logging.py` output
