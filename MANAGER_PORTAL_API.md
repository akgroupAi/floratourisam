# Manager Portal & Inventory Operations — API

Phases 2 and 3 of [INVENTORY_FEATURES_PROPOSAL.md](INVENTORY_FEATURES_PROPOSAL.md). Phase 1 (room
counting, availability fixes, calendars) is in [ROOM_CALENDAR_API.md](ROOM_CALENDAR_API.md).

Base URL: `/api/v1`

---

## Contents

1. [Property scoping — read this first](#1-property-scoping--read-this-first)
2. [Manager portal](#2-manager-portal)
3. [Menu daily stock](#3-menu-daily-stock)
4. [Inventory dashboard & alerts](#4-inventory-dashboard--alerts)
5. [Bulk operations](#5-bulk-operations)
6. [Manager notifications](#6-manager-notifications)
7. [Deployment](#7-deployment)

---

## 1. Property scoping — read this first

Every `/manager/*` endpoint resolves the caller through `ManagerScope`
([manager_scope.py](app/core/manager_scope.py)). This is the security boundary of the portal:

| Caller | Sees |
|---|---|
| `super_admin`, `admin` | Everything, unscoped |
| `hotel_manager` | Only hotels where `manager_id` is them |
| `apartment_manager` | Only their apartments |
| `restaurant_manager` | Only their restaurants |
| Anything else | `403` at the dependency, before any handler runs |

Two deliberate choices:

- **Refusals are `403`, not `404`.** A `404` would leak whether an id exists; `403` says only "not
  yours".
- **A manager with no properties gets a filter that matches nothing**, never an unfiltered query.
  That is the dangerous failure mode and it is tested explicitly.

Roles do not bleed: a hotel manager has no apartment ids at all, so `assert_apartment` refuses even
for an apartment that exists.

20 tests cover this in isolation ([test_manager_scope.py](tests/test_manager_scope.py)) rather than
only through the endpoints.

---

## 2. Manager portal

16 endpoints under `/manager`. Before this, managers could reach three list endpoints across the
whole platform — adding a room or changing a price required an admin.

### Properties and dashboard

```
GET /manager/me/properties     hotels, apartments, restaurants I manage
GET /manager/me/dashboard      today at my properties
```

```json
{
  "date": "2026-08-12",
  "arrivals_today": 6, "departures_today": 4, "in_house": 23,
  "pending_bookings": 3, "unpaid_bookings": 2, "cancellations_last_7d": 1,
  "revenue_today": 48500.0, "revenue_this_month": 1284000.0,
  "property_count": 2
}
```

### Rooms and calendars

```
GET /manager/rooms?hotel_id=              my room types
GET /manager/rooms/{room_id}
GET /manager/rooms/{room_id}/calendar?start_date=&end_date=
PUT /manager/rooms/{room_id}/calendar     rates, inventory, blocks
GET /manager/apartments/{id}/calendar
PUT /manager/apartments/{id}/calendar     rates, minimum stay, blocks
```

Same request and response shapes as the admin calendar endpoints — they share the service methods,
so behaviour cannot drift between the two portals.

### Bookings

```
GET  /manager/bookings          filters: status, booking_type, from_date, to_date, search
GET  /manager/bookings/{id}
POST /manager/bookings/{id}/confirm
POST /manager/bookings/{id}/cancel     { "cancellation_reason": "..." }
```

Confirm only accepts `pending` bookings and says so if not. Cancel goes through the same service the
guest-facing path uses, so refund handling is identical.

A booking at another manager's property returns "not found" — deliberately the same message as one
that does not exist, so the endpoint cannot be used to probe for ids.

### Reviews

```
GET  /manager/reviews?unanswered_only=true&max_rating=3
POST /manager/reviews/{id}/respond      { "response_text": "..." }
```

`unanswered_only=true` with `max_rating=3` is the queue that matters — unhappy guests nobody has
replied to.

---

## 3. Menu daily stock

`MenuItem.is_available` is a permanent on/off switch. Three new columns give restaurants a
per-service one: `daily_quantity`, `sold_today`, `stock_date`.

```
GET /manager/menu?restaurant_id=&sold_out_only=true
PUT /manager/menu/{item_id}/stock
```

| Body | Effect |
|---|---|
| `{"daily_quantity": 20}` | 20 available today |
| `{"sold_today": 20}` | Sold out, if the limit is 20 |
| `{"reset": true}` | Restocked — counter back to zero |
| `{"unlimited": true}` | No daily limit |
| `{"is_available": false}` | Off the menu entirely, not just today |

**The counter resets itself.** `sold_today` only counts against `stock_date`; on any other day the
item is treated as fully restocked. No nightly job to run or forget — the date comparison *is* the
reset.

`daily_quantity: null` means unlimited, `0` means sold out. Those are different, and the API keeps
them distinct.

---

## 4. Inventory dashboard & alerts

```
GET /admin/inventory/summary
GET /admin/inventory/occupancy?start_date=&end_date=
GET /admin/inventory/alerts
```

**Occupancy** is room-nights: capacity is `total_rooms × nights`, so it reflects real units rather
than treating a room type as one. The per-hotel breakdown is sorted worst-first — the properties
needing attention are at the top.

**Alerts** are concrete problems, not statistics. Each is something someone can act on today:

| Severity | Alert |
|---|---|
| high | Room on sale with `total_rooms = 0` |
| high | Room on sale with no price |
| high | Active apartment with no pricing at all — it cannot be booked |
| medium | Room with no calendar entries for the next 30 days |
| medium | Menu item available at an inactive restaurant |
| low | Menu item sold out today |

An empty list is the healthy state. Sorted high-severity first.

---

## 5. Bulk operations

```
POST /admin/inventory/bulk/pricing
POST /admin/inventory/bulk/availability
```

**Both default to a dry run.** The response lists every room with its current and new price and
changes nothing until you send `dry_run: false`. A mistyped percentage across a city is expensive to
undo, so applying it has to be deliberate.

```json
{
  "start_date": "2026-12-20", "end_date": "2027-01-05",
  "city": "Ahmedabad", "percent_change": 15,
  "dry_run": true
}
```

Target by `hotel_ids`, `room_ids`, or `city`. **Sending none of them is rejected** — the API will not
touch every room on the platform because a filter was omitted.

Pricing takes exactly one of `percent_change` or `set_price`; sending both or neither is a `400`. A
`percent_change` below `-100` is refused, since it would produce a negative price.

---

## 6. Manager notifications

Managers previously learned about a booking only by going to look. Three triggers now fire:

| Event | Notification |
|---|---|
| Booking confirmed after payment | "New booking" with reference and amount |
| Booking cancelled | "Booking cancelled" with the reason |
| New review | "New review", or **"Negative review"** at 3 stars or below |

Each resolves the property to its `manager_id` and pushes through the existing notification system,
so it appears in the manager's feed and over WebSocket.

**All three are best-effort.** A notification failure is logged and swallowed — it must never roll
back the booking that triggered it.

---

## 7. Deployment

Two migrations, both additive:

```bash
alembic upgrade y9z0a1b2c3d4
```

| Revision | Change |
|---|---|
| `x8y9z0a1b2c3` | `apartment_availability` table + `apartments.minimum_nights` |
| `y9z0a1b2c3d4` | `menu_items.daily_quantity`, `sold_today`, `stock_date` |

Remember this repo has three migration heads from earlier branching, so `alembic upgrade head` fails
— name the revision. See [DEPLOYMENT.md](DEPLOYMENT.md).

**Nothing changes for existing data.** New menu columns default to unlimited, and
`apartments.minimum_nights` defaults to 1, which is the current behaviour.

**Assign managers to properties.** The portal is only useful once `manager_id` is set on hotels,
apartments, and restaurants — via the existing `POST /admin/{type}/{id}/assign-manager` endpoints. A
manager with no assignments sees an empty portal, correctly.

---

## Source

| Concern | File |
|---|---|
| Property scoping | [manager_scope.py](app/core/manager_scope.py) |
| Manager service | [manager_service.py](app/services/manager_service.py) |
| Manager endpoints | [manager.py](app/api/v1/manager.py) |
| Inventory service | [inventory_service.py](app/services/inventory_service.py) |
| Inventory endpoints | [admin_inventory.py](app/api/v1/admin_inventory.py) |
| Manager notifications | [manager_notify.py](app/utils/manager_notify.py) |
| Schemas | [manager.py](app/schemas/manager.py) · [inventory.py](app/schemas/inventory.py) |
| Tests | [test_manager_scope.py](tests/test_manager_scope.py) — 20 · [test_inventory_ops.py](tests/test_inventory_ops.py) — 21 |
