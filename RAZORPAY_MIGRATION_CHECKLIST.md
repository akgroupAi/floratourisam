# Razorpay Migration Checklist

## Pre-Migration (Planning Phase)

- [ ] **Get Razorpay Account**
  - [ ] Sign up at [razorpay.com](https://razorpay.com)
  - [ ] Verify business details
  - [ ] Get approval for live mode (if needed)

- [ ] **Gather Credentials**
  - [ ] Copy Key ID from API Keys page
  - [ ] Copy Key Secret from API Keys page
  - [ ] Note webhook secret for later

## Development Phase

### Backend Setup

- [ ] **Update Requirements**
  - [ ] `pip install -r requirements.txt` (includes `requests` and `razorpay`)

- [ ] **Configure Environment**
  - [ ] Add to `.env`:
    ```
    RAZORPAY_KEY_ID=rzp_test_xxxxxxx
    RAZORPAY_KEY_SECRET=your_secret_key
    RAZORPAY_WEBHOOK_SECRET=whsec_xxxxx
    RAZORPAY_CURRENCY=INR
    ```

- [ ] **Code Changes Done** ✅
  - [x] Created `app/services/razorpay_service.py`
  - [x] Updated `app/core/config.py`
  - [x] Updated `app/api/v1/payments.py`
  - [x] Updated `requirements.txt`

### Frontend Setup

- [ ] **Include Razorpay SDK**
  ```html
  <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
  ```

- [ ] **Update Payment Flow**
  - [ ] Replace Stripe checkout calls with Razorpay order calls
  - [ ] Update order data mapping to Razorpay SDK
  - [ ] Add verification call after payment
  - [ ] Add error handling for payment failures

- [ ] **Test Components**
  - [ ] Payment button/link
  - [ ] Order creation API call
  - [ ] Razorpay modal display
  - [ ] Payment verification
  - [ ] Error messages

### Testing Phase

- [ ] **Local Testing**
  - [ ] Start dev server: `uvicorn app.main:app --reload`
  - [ ] Install ngrok: `pip install pyngrok` (for webhook testing)
  - [ ] Set ngrok tunnel: `ngrok http 8000`
  - [ ] Note public URL from ngrok

- [ ] **Test API Endpoints**
  - [ ] `POST /api/v1/payments/razorpay/order` (with test booking)
  - [ ] Verify response has `order_id`, `key_id`, `amount_paise`
  - [ ] `POST /api/v1/payments/razorpay/verify` (with test data)
  - [ ] `POST /api/v1/payments/{id}/refund` (for created payments)

- [ ] **Test Payment Flow**
  - [ ] Create order via API
  - [ ] Open payment modal
  - [ ] Use test card: `4111 1111 1111 1111`
  - [ ] Use any 3-digit CVV
  - [ ] Use any future expiry
  - [ ] Enter any 6-digit OTP
  - [ ] Verify payment is marked as COMPLETED in DB

- [ ] **Test Webhooks (Local)**
  - [ ] Configure ngrok URL in Razorpay dashboard
  - [ ] Set webhook to: `{ngrok_url}/api/v1/payments/razorpay/webhook`
  - [ ] Trigger test webhook from dashboard
  - [ ] Verify webhook event is processed
  - [ ] Check payment status updated in DB

- [ ] **Test Refunds**
  - [ ] Create and complete a payment
  - [ ] Call refund endpoint with full amount
  - [ ] Verify payment status changes to REFUNDED
  - [ ] Test partial refund with specific amount

- [ ] **Test Error Cases**
  - [ ] Missing Razorpay credentials (should fail gracefully)
  - [ ] Invalid booking ID
  - [ ] Already paid booking
  - [ ] Invalid payment signature
  - [ ] Non-existent payment for refund

## Pre-Production Phase

- [ ] **Code Review**
  - [ ] Review all changes in pull request
  - [ ] Check error handling is comprehensive
  - [ ] Verify logging is in place
  - [ ] Ensure no hardcoded values

- [ ] **Security Review**
  - [ ] Verify signature verification is correct
  - [ ] Check no secrets in logs
  - [ ] Ensure DB queries use parameterized statements
  - [ ] Verify authorization checks on endpoints

- [ ] **Documentation**
  - [ ] Review RAZORPAY_INTEGRATION.md
  - [ ] Review RAZORPAY_QUICK_REFERENCE.md
  - [ ] Update team on new endpoints
  - [ ] Share credentials securely with team

- [ ] **Database**
  - [ ] No migrations needed (schema already supports JSONB)
  - [ ] Verify existing payments still work
  - [ ] Check payment_transactions table has entries

## Production Phase

### Pre-Deployment

- [ ] **Switch to Live Credentials**
  - [ ] Get live Key ID from Razorpay dashboard
  - [ ] Get live Key Secret from Razorpay dashboard
  - [ ] Create webhook with live URL

- [ ] **Production Environment**
  - [ ] Add credentials to production `.env`
  - [ ] Do NOT commit credentials to git
  - [ ] Use environment variable management (e.g., AWS Secrets Manager)

- [ ] **Configure Webhooks**
  - [ ] Login to Razorpay dashboard
  - [ ] Go to **Settings → Webhooks**
  - [ ] Create webhook with production URL
  - [ ] Set events:
    - [ ] `payment.authorized`
    - [ ] `payment.failed`
    - [ ] `refund.created`
    - [ ] `refund.failed`
  - [ ] Copy webhook secret to production `.env`

- [ ] **Test Production Setup**
  - [ ] Create test order in production
  - [ ] Process payment with test card
  - [ ] Verify webhook is received (check logs)
  - [ ] Verify payment status is updated correctly

### Deployment

- [ ] **Deploy Code**
  ```bash
  git pull
  pip install -r requirements.txt
  python -m alembic upgrade head  # No changes, but ensure DB is current
  systemctl restart your_app_service
  ```

- [ ] **Verify Deployment**
  - [ ] Health check endpoint responds
  - [ ] API logs show no errors
  - [ ] Database connections are working
  - [ ] Webhooks are being received

### Post-Deployment

- [ ] **Monitor Logs**
  - [ ] Check for any Razorpay errors
  - [ ] Monitor webhook processing
  - [ ] Watch for failed payments
  - [ ] Monitor refund requests

- [ ] **Customer Communication**
  - [ ] Update payment page with Razorpay info
  - [ ] Update help/FAQ if needed
  - [ ] Notify support team of new process
  - [ ] Create runbook for troubleshooting

## Fallback Plan

If issues arise with Razorpay:

- [ ] **Immediate**: Keep Stripe endpoints active for fallback
- [ ] **Option 1**: Route new payments through Stripe temporarily
- [ ] **Option 2**: Contact Razorpay support
- [ ] **Option 3**: Rollback code changes and use Stripe only
- [ ] **Recovery**: Once fixed, migrate to Razorpay

## Success Criteria

- ✅ All payments process successfully
- ✅ Webhooks are received and processed
- ✅ Refunds work without errors
- ✅ No payment data loss
- ✅ Zero failed transactions (related to payment gateway)
- ✅ Customers receive confirmation emails
- ✅ Support team handles payment issues

## Timeline Estimate

| Phase | Duration | Notes |
|-------|----------|-------|
| Development | 1-2 hours | Code already implemented ✅ |
| Testing | 2-4 hours | Frontend integration needed |
| UAT | 4-8 hours | Full payment flow testing |
| Deployment | 30 minutes | Deploy and verify |
| Monitoring | Ongoing | First 24-48 hours critical |

---

## Quick Commands Reference

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Start Dev Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Local Webhook Testing (ngrok)
```bash
pip install pyngrok
python -c "from pyngrok import ngrok; print(ngrok.connect(8000))"
```

### Create Test Order (curl)
```bash
curl -X POST http://localhost:8000/api/v1/payments/razorpay/order \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"booking_id": "YOUR_UUID"}'
```

### Check Logs
```bash
# Monitor real-time logs
tail -f app.log

# Search for Razorpay errors
grep -i razorpay app.log
```

---

## Support Contacts

- **Razorpay Support**: [support@razorpay.com](mailto:support@razorpay.com)
- **API Docs**: [razorpay.com/docs/api](https://razorpay.com/docs/api/)
- **Dashboard**: [dashboard.razorpay.com](https://dashboard.razorpay.com)
- **Team Slack**: #payments channel

---

## Sign-Off

- [ ] Development Lead: __________ Date: __________
- [ ] QA Lead: __________ Date: __________
- [ ] DevOps Lead: __________ Date: __________
- [ ] Product Manager: __________ Date: __________
