# Razorpay 400 Error - Root Cause Analysis & Fix

## Problem Summary

Server logs show: `"error": "400 Client Error: Bad Request for url: https://api.razorpay.com/v1/orders"`

When apartment bookings trigger payment order creation, Razorpay API returns 400 Bad Request.

---

## Diagnostic Findings

✅ **PASSED**: Razorpay credentials are valid  
✅ **PASSED**: API authentication works correctly  
✅ **PASSED**: Basic order creation (500 INR) succeeds  

This means the problem is **NOT** with credentials or the API itself.

---

## Likely Root Causes (in order of probability)

### 1. **Invalid Booking Amount** (MOST LIKELY)
**Cause**: `booking.total_price` is NULL, zero, or negative  
**Why**: Razorpay requires minimum amount >= 1 paise

**Check on Server**:
```sql
SELECT id, booking_type, total_price, currency, created_at 
FROM bookings 
WHERE booking_type = 'APARTMENT' 
  AND total_price IS NULL OR total_price <= 0
ORDER BY created_at DESC LIMIT 5;
```

**Fix**: Ensure apartment bookings always have a valid total_price > 0

---

### 2. **Invalid Currency Format**
**Cause**: `booking.currency` is NULL or not a valid 3-letter code  
**Why**: Razorpay expects uppercase 3-letter codes (INR, USD, EUR, etc.)

**Check**:
```sql
SELECT DISTINCT currency FROM bookings WHERE booking_type = 'APARTMENT';
```

**Fix**: Should show 'INR' or NULL (which defaults to INR from config). If anything else, it's invalid.

---

### 3. **Receipt Field Too Long or Invalid Characters**
**Cause**: Receipt field exceeds 40 characters or contains special characters  
**Why**: Razorpay has strict validation on receipt format

**Current Format**: `order_{booking_id}` (usually ~44 characters including UUID)  

**Fix**: Truncate or use shorter reference:
```python
receipt = f"order_{str(booking_id)[:8]}"  # Only first 8 chars of UUID
```

---

### 4. **Booking Already Marked as Paid**
**Cause**: `booking.is_paid = True` when trying to create order  
**Why**: Logic prevents creating orders for already-paid bookings

**Check**:
```sql
SELECT * FROM bookings WHERE booking_type = 'APARTMENT' AND is_paid = true;
```

---

## Immediate Actions to Take on Server

### Step 1: Enable Enhanced Logging
Already added in latest code. Logs now include:
- `amount_paise`: Exact amount being sent to Razorpay
- `currency`: Currency code being used
- `error_response`: Actual Razorpay error details (most important!)
- `status_code`: HTTP status

Restart the server:
```bash
sudo systemctl restart floratourism
```

### Step 2: Reproduce the Error
Create a new apartment booking and try to pay. Check logs:
```bash
sudo journalctl -u floratourism -f
```

Look for the `razorpay_order_creation_failed` error with enhanced details.

### Step 3: Check Booking Data
Once you see the enhanced error response, you'll see exactly what Razorpay rejected. Common responses:

**If you see `"invalid_field_value"` for amount:**
- Booking total_price is invalid → Fix booking calculation

**If you see `"invalid_field"` for currency:**
- Currency is invalid → Update booking currency field

**If you see `"invalid_base64"` or `"invalid_field"` for receipt:**
- Receipt format is wrong → Use shorter reference

---

## Updated Error Handling Features

The latest code now logs:

```python
logger.error(
    "razorpay_order_creation_failed",
    amount_paise=amount_paise,  # ← Now visible
    currency=currency,           # ← Now visible
    booking_id=str(booking_id),
    error=str(e),
    error_response=error_response,  # ← ACTUAL RAZORPAY ERROR
    status_code=status_code      # ← HTTP status
)
```

**This will show you exactly why Razorpay is rejecting the request!**

---

## Testing on Server

Run the diagnostic script on the server:
```bash
cd /home/ubuntu/floratourisam

# Test Razorpay credentials and basic connectivity
python test_razorpay_credentials.py

# Expected output should show:
# ✅ Configuration: PASS
# ✅ Authentication: PASS
# ✅ Order Creation: PASS
```

If any test fails, it indicates a server-side configuration issue.

---

## Quick Fix Checklist

- [ ] Pull latest code with enhanced logging: `git pull origin development`
- [ ] Restart server: `sudo systemctl restart floratourism`
- [ ] Reproduce the error: Create a test apartment booking
- [ ] Check logs: `sudo journalctl -u floratourism -f | grep razorpay`
- [ ] Look at `error_response` field in logs for actual Razorpay error
- [ ] Based on error_response, fix the booking data or configuration
- [ ] Re-test payment creation

---

## Prevention for Future

Add validation in booking creation:
```python
# In apartment booking service
if not booking.total_price or booking.total_price <= 0:
    raise ValueError("Booking must have a valid price > 0")

if not booking.currency or booking.currency.upper() not in ["INR", "USD", "EUR", "GBP"]:
    raise ValueError("Booking must have a valid currency")
```

---

## Support

If the enhanced logs still don't show the issue:

1. Enable SQL query logging:
   ```python
   # In app/core/config.py
   DATABASE_ECHO=True  # Shows all DB queries
   ```

2. Check if booking has both:
   - `total_price` is a valid number > 0
   - `currency` is 'INR' or another valid code

3. Verify .env has valid Razorpay credentials
