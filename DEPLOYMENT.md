# Deployment Runbook

Commit and push from your machine, then pull, migrate, and restart on the server.

Repo: `git@github.com:akgroupAi/floratourisam.git` · Branch: `development`

---

## 1. Local — commit and push

```bash
cd "c:/Users/Parth Kher/Desktop/floratourisam"

# See exactly what is going in
git status --short

# Run the tests before committing
python -m pytest tests/ -q
```

The 16 pre-existing errors are expected — those fixtures use SQLite, which cannot compile the
Postgres `JSONB`/`ARRAY` columns. What matters is that the **passed** count does not drop and
nothing says `FAILED`.

```bash
git add -A
git commit -m "add 5% platform fee to payable bookings

Charged to the customer on top of the booking subtotal and applied through a
single helper so a quote, a booking, and the Razorpay charge cannot disagree.

- New app/utils/pricing.py; rate configurable via PLATFORM_FEE_PERCENT (default 5)
- Applied to hotel, apartment, restaurant pre-order, dining pass, package, and
  consultation bookings, plus the price-preview endpoint
- New bookings.platform_fee column, exposed on booking and price responses
- Payment records now read the real fee off the booking instead of a notional 1%,
  which was double-counting
- Free bookings attract no fee; a discount reduces the fee with the subtotal
- Existing bookings are not back-filled: their totals stay as quoted

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"

git push origin development
```

---

## 2. Server — pull, migrate, restart

### 2.1 Connect and locate the app

```bash
ssh <user>@floramedcare.com
cd /path/to/floratourisam        # wherever the app is deployed
```

Find how the app runs, if you do not already know:

```bash
systemctl list-units --type=service | grep -iE "flora|uvicorn|gunicorn|fastapi"
# or
pm2 list
# or
docker compose ps
```

### 2.2 Back up the database first

This deploy adds a column. Take a backup before running the migration — it is the difference
between a five-minute rollback and a bad afternoon.

```bash
pg_dump "$DATABASE_URL" -Fc -f ~/backup-$(date +%F-%H%M).dump
ls -lh ~/backup-*.dump
```

### 2.3 Pull the code

```bash
git fetch origin
git log --oneline HEAD..origin/development     # what you are about to take
git pull origin development
```

### 2.4 Install any new dependencies

```bash
source venv/bin/activate          # or however the venv is activated
pip install -r requirements.txt
```

### 2.5 Run the migration

**Do not use `alembic upgrade head`.** This repo has three migration heads from earlier branching,
so `head` is ambiguous and the command will fail. Target the revision explicitly:

```bash
alembic current                   # where you are now
alembic upgrade w7x8y9z0a1b2      # adds bookings.platform_fee
alembic current                   # confirm it moved
```

Verify the column landed:

```bash
psql "$DATABASE_URL" -c "\d bookings" | grep platform_fee
```

Expected: `platform_fee | double precision | not null default 0`

### 2.6 Restart

```bash
sudo systemctl restart <service-name>
sudo systemctl status <service-name> --no-pager
sudo journalctl -u <service-name> -n 50 --no-pager      # check for startup errors
```

For other setups: `pm2 restart <name>` · `docker compose up -d --build`

### 2.7 Rebuild the AI knowledge base

The chatbot's index is an in-memory snapshot per worker process, so it is empty after a restart
until rebuilt. **With multiple workers, run this several times** — each call hits whichever worker
answers.

```bash
curl -X POST https://floramedcare.com/apis/api/v1/ai/refresh-knowledge \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## 3. Verify

```bash
# App is up
curl -s https://floramedcare.com/apis/health

# Admin endpoints respond
curl -s "https://floramedcare.com/apis/api/v1/admin/payments/stats" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Knowledge base rebuilt
curl -s https://floramedcare.com/apis/api/v1/admin/ai/knowledge-status \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Check the platform fee is being applied.** Quote a hotel booking and confirm `platform_fee` is 5%
of the subtotal and that `total_price` includes it:

```bash
curl -s -X POST https://floramedcare.com/apis/api/v1/bookings/calculate-price \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"booking_type":"hotel","room_id":"<room-uuid>",
       "check_in_date":"2026-09-01","check_out_date":"2026-09-03","guest_count":2}'
```

Then make one real test booking end to end and confirm the Razorpay amount matches the quoted
`total_price`. Do not skip this — it is the only check that proves the customer is charged what
they were shown.

---

## 4. Rollback

**Code only** (the new column is harmless if left in place):

```bash
git reset --hard <previous-commit-sha>
sudo systemctl restart <service-name>
```

**Code and schema:**

```bash
alembic downgrade o0p1q2r3s4t5     # drops bookings.platform_fee
git reset --hard <previous-commit-sha>
sudo systemctl restart <service-name>
```

**Turn the fee off without deploying anything.** Set the rate to zero in `.env` and restart — the
code path stays in place but charges nothing:

```bash
echo "PLATFORM_FEE_PERCENT=0" >> .env
sudo systemctl restart <service-name>
```

That is the fastest lever if the fee turns out to be wrong in production.

---

## 5. Things that bite

- **`alembic upgrade head` fails.** Three heads exist (`e5f6a7b8c9d0` from 2024-01,
  `m7n8o9p0q1r2` from 2026-04, and the live chain). Always name the revision. The two stale heads
  are worth cleaning up in a separate change — do not run `upgrade heads` blindly, it will try to
  apply dead branches.
- **Existing bookings are not back-filled.** Their `platform_fee` is 0 and `total_price` is
  unchanged, deliberately: those were quoted and often already paid without a fee. Only bookings
  created after this deploy carry it.
- **Prices go up 5% for customers.** Confirm the frontend renders `platform_fee` as its own line on
  the booking summary and checkout. A total that silently jumps at payment time generates refund
  requests.
- **`page_size` is capped at 100** on every admin endpoint. Anything higher returns `422`.
- **The AI knowledge base is stale until refreshed** after every restart and after bulk content
  changes. `GET /admin/ai/knowledge-status` reports what the responding worker has indexed.

---

## Quick reference

```bash
# Local
python -m pytest tests/ -q && git add -A && git commit && git push origin development

# Server
cd /path/to/floratourisam
pg_dump "$DATABASE_URL" -Fc -f ~/backup-$(date +%F-%H%M).dump
git pull origin development
source venv/bin/activate && pip install -r requirements.txt
alembic upgrade w7x8y9z0a1b2
sudo systemctl restart <service-name>
curl -s https://floramedcare.com/apis/health
```
