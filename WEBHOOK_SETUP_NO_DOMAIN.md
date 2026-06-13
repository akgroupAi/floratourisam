
# Razorpay Webhook Setup Without Domain

## 🎯 Quick Answer: YES! Multiple Ways

---

## ⭐ **Best Option: Cloudflare Tunnel (Free, No Domain)**

**Why?**
- ✅ Free forever
- ✅ No domain needed
- ✅ Public HTTPS URL automatically
- ✅ Works from anywhere

### Setup (2 minutes)

**Step 1: Install cloudflared**
```bash
# Linux/Ubuntu
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb

# Or use package manager
sudo apt install cloudflared
```

**Step 2: Login**
```bash
cloudflared tunnel login
# Opens browser, click "Authorize"
```

**Step 3: Create Tunnel**
```bash
cloudflared tunnel create flora-api
```

**Step 4: Get URL**
```bash
cloudflared tunnel info flora-api
# Copy the "Tunnel URL" (looks like: abc123xyz.trycloudflare.com)
```

**Step 5: Update .env**
```env
RAZORPAY_WEBHOOK_URL=https://abc123xyz.trycloudflare.com/api/v1/payments/razorpay/webhook
```

**Step 6: Run Tunnel**
```bash
cloudflared tunnel run flora-api --url http://localhost:8000
```

**Keep this terminal open while testing!**

---

## 🔄 **Option 2: localhost.run (Instant, No Setup)**

Fastest option - literally 2 commands:

**Step 1: Run on Server**
```bash
ssh -R 80:localhost:8000 localhost.run
```

You get: `https://xxxxx-xxxxx-xxxxx.localhost.run`

**Step 2: Update .env**
```env
RAZORPAY_WEBHOOK_URL=https://xxxxx-xxxxx-xxxxx.localhost.run/api/v1/payments/razorpay/webhook
```

**Done!** The tunnel auto-starts.

---

## 🌐 **Option 3: ngrok (If You Have Local Machine)**

If ngrok is on your local/dev machine:

```bash
ngrok http 13.201.5.161:8000
```

Get URL like: `https://abc123.ngrok.io`

Update `.env`:
```env
RAZORPAY_WEBHOOK_URL=https://abc123.ngrok.io/api/v1/payments/razorpay/webhook
```

---

## 🚫 **Option 4: Skip Webhook (Development Only)**

**The API works WITHOUT webhooks!**

Just leave it as placeholder:
```env
RAZORPAY_WEBHOOK_URL=http://13.201.5.161:8000/api/v1/payments/razorpay/webhook
RAZORPAY_WEBHOOK_SECRET=your-webhook-secret-from-dashboard
```

**You can still:**
- ✅ Create orders
- ✅ Verify payments
- ✅ Process refunds
- ✅ Test API endpoints

**You cannot:**
- ❌ Test webhook from Razorpay dashboard
- ❌ Get real-time payment notifications

Use this during development, then add webhook later.

---

## 📋 **Comparison Table**

| Option | Setup Time | Permanent? | Domain? | Cost | Best For |
|--------|-----------|-----------|--------|------|----------|
| Cloudflare Tunnel | 5 min | Yes | No | Free | Production-ready testing |
| localhost.run | 1 min | No (temporary) | No | Free | Quick testing |
| ngrok | 2 min | No (24h free) | No | Free/Paid | Local testing |
| Skip Webhook | 0 min | N/A | N/A | Free | Development only |
| Real Domain | 30 min | Yes | Yes | ~$10/yr | Production |

---

## ✅ **My Recommendation**

1. **For Testing Now:** Use **localhost.run** (instant)
2. **For Production Ready:** Use **Cloudflare Tunnel** (free & permanent)
3. **For Eventually:** Get a domain (~$10/year)

---

## 🎬 **Quick Start - Cloudflare Tunnel**

```bash
# Terminal on your server

# 1. Install
sudo apt install cloudflared

# 2. Login (opens browser)
cloudflared tunnel login

# 3. Create
cloudflared tunnel create flora-api

# 4. Get URL
cloudflared tunnel info flora-api
# Copy Tunnel URL

# 5. Update .env with that URL

# 6. Run in background
cloudflared tunnel run flora-api --url http://localhost:8000 &

# 7. Test
curl https://YOUR_TUNNEL_URL/api/v1/payments/razorpay/webhook
# Should return 405 or 403 (that's normal - it's checking auth)
```

---

## 🧪 **Test Webhook is Working**

After setting up tunnel:

```bash
# Get your tunnel URL
WEBHOOK_URL="https://your-tunnel-url/api/v1/payments/razorpay/webhook"

# Test if accessible
curl -v $WEBHOOK_URL

# Should show:
# HTTP/1.1 401 Unauthorized
# (or 403 Forbidden)
# That's GOOD - it means the endpoint exists!
```

---

## 🚀 **Next Steps**

### Immediate (Now)
```bash
# Use localhost.run for quick testing
ssh -R 80:localhost:8000 localhost.run
```

### This Week
```bash
# Switch to Cloudflare Tunnel for permanence
cloudflared tunnel create flora-api
```

### Later (Production)
```bash
# Get a domain ($10/year)
# Point DNS to your server
# Use HTTPS
```

---

## ❓ **FAQ**

**Q: Do I need a domain?**
A: No! Use Cloudflare Tunnel, localhost.run, or ngrok.

**Q: Will the API work without webhook?**
A: Yes! 100%. Webhooks are optional.

**Q: Can I test webhook without domain?**
A: Yes! All 4 methods work.

**Q: Which should I use?**
A: Start with `localhost.run` (instant), upgrade to Cloudflare Tunnel for production.

**Q: Is it free?**
A: All methods mentioned are free!

---

## 📚 **Resources**

- [Cloudflare Tunnel Docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-applications/)
- [localhost.run](https://localhost.run)
- [ngrok](https://ngrok.com)
- [Razorpay Webhooks](https://razorpay.com/docs/webhooks/)

---

## ✨ **You're Set!**

Pick any option above and start testing webhooks without needing a domain! 🎉
