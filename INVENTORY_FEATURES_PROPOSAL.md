# Inventory Management — What Admin and Managers Are Missing

An audit of how inventory works today across hotels, apartments, restaurants, and doctor
scheduling, and what is worth building for each audience.

Findings were traced through the code, not inferred from naming.

---

## Summary

The data model for inventory is **already good**. `RoomAvailability` is a proper per-date rate and
inventory calendar; `Room` carries `total_rooms`; menu items, thalis, and dining passes all have
availability flags. Very little of it is reachable.

Three of the findings below are defects rather than missing features, and two of those change what
customers can book. Worth reading §1 before deciding what to build.

| # | Finding | Type |
|---|---|---|
| 1 | `RoomAvailability` is never written by anything | Gap |
| 2 | A room *type* behaves as a single unit — `total_rooms` is ignored | **Defect** |
| 3 | `GET /hotels/{id}/rooms/{id}/availability` always returns `true` | **Defect** |
| 4 | Managers have almost no endpoints despite having roles | Gap |
| 5 | Apartments have no availability calendar | Gap |
| 6 | Menu items have no stock, only an on/off flag | Gap |
| 7 | No inventory dashboard or alerts anywhere | Gap |

---

## 1. Defects to fix first

### 1.1 One booking blocks an entire room type

`Room` models a room *type* — "Deluxe Double" with `total_rooms: 10`. But the conflict check in
[booking_service.py:1044-1056](app/services/booking_service.py#L1044-L1056) looks for *any*
overlapping booking on that `room_id` and rejects:

```python
conflict_query = select(Booking.id).where(
    Booking.hotel_room_id == room_id,
    Booking.status.in_(OCCUPIED_BOOKING_STATUSES),
    Booking.check_in_date < check_out,
    Booking.check_out_date > check_in,
)
...
raise ValueError("The room is already booked for the selected dates")
```

`total_rooms` is never consulted, and neither is `RoomAvailability.available_rooms`. **A hotel with
ten deluxe rooms can sell exactly one per night.** Every other request is refused as "already
booked".

Fix: count overlapping bookings and compare against the per-date allowance
(`RoomAvailability.available_rooms` where a row exists, otherwise `Room.total_rooms`).

This is the single highest-value change in this document — it is lost revenue on every property with
more than one room of a type.

### 1.2 A public availability endpoint always says "available"

Two endpoints answer the same question, and one is a stub:

| Endpoint | Backed by | Behaviour |
|---|---|---|
| `GET /bookings/rooms/{room_id}/availability` | `BookingService.check_room_availability` | Correct |
| `GET /hotels/{hotel_id}/rooms/{room_id}/availability` | `HotelService.check_availability` | **Always `true`** |

[hotel_service.py:148-152](app/services/hotel_service.py#L148-L152) is explicit about it:

```python
"""Check room availability for dates. (Placeholder implementation)"""
# In a real implementation, we would check the RoomAvailability table
# against the requested date range.
return True
```

Any UI calling the hotel-scoped route shows rooms as bookable when they are not, and the customer
only discovers otherwise at checkout. Fix: delegate to `BookingService`, or delete the endpoint and
point callers at the working one.

### 1.3 `RoomAvailability` is read but never written

The table supports per-date `available_rooms`, `price`, `is_blocked`, and `notes`. `booking_service`
reads `is_blocked` when validating a booking. **Nothing in the codebase ever creates or updates a
row.**

So today no one can:

- Block dates for maintenance, refurbishment, or a private event
- Set a weekend, seasonal, or peak rate — `RoomAvailability.price` is dead
- Reduce inventory for a date without deactivating the whole room type

The calendar is fully built and completely unmanaged. Most of §2 is just exposing it.

---

## 2. For admins

### 2.1 Rate and availability calendar — the big one

```
GET    /admin/hotels/{hotel_id}/rooms/{room_id}/calendar?from=&to=
PUT    /admin/hotels/{hotel_id}/rooms/{room_id}/calendar        bulk upsert a date range
POST   /admin/hotels/{hotel_id}/rooms/{room_id}/block           block dates + reason
DELETE /admin/hotels/{hotel_id}/rooms/{room_id}/block           unblock
```

Bulk upsert matters: nobody sets 90 dates one at a time. Accept a range plus a weekday mask —
"1 Jun to 31 Aug, Fri+Sat, price 6500, 8 rooms available".

Renders as a month grid: price, remaining inventory, and blocked days per cell. **Effort: M.**

### 2.2 Inventory dashboard

```
GET /admin/inventory/summary          rooms/apartments/menu items, active vs blocked
GET /admin/inventory/occupancy        occupancy % by property and date range
GET /admin/inventory/alerts           the things needing attention
```

`/alerts` is the one that earns its place. Concrete, actionable conditions:

- Rooms with no availability rows for the next 30 days (will fall back to defaults silently)
- Properties fully booked for 7+ consecutive days (raise the rate)
- Room types with `total_rooms: 0` or no price set
- Menu items marked available at a restaurant that is inactive
- Dining passes past `available_until` still on sale

`/admin/dashboard/hotels/occupancy` and `.../availablerooms` already exist but return bare counts
with no drill-down. **Effort: M.**

### 2.3 Bulk operations

Admins managing many properties need to act on more than one row:

```
POST /admin/inventory/bulk/pricing       apply a % change across selected rooms
POST /admin/inventory/bulk/availability  block or open a date range across properties
POST /admin/inventory/bulk/toggle        activate/deactivate menu items in bulk
```

**Effort: M.** Guard it with a dry-run flag that reports what *would* change — a mistyped bulk price
change across a whole city is expensive.

### 2.4 Apartment availability calendar

Apartments only have `is_available` (a boolean on the whole unit) and an overlapping-booking check.
No blocking, no seasonal rates, no minimum-stay enforcement, though `price_per_night`,
`price_per_week`, and `price_per_month` all exist.

Reuse the `RoomAvailability` shape as `ApartmentAvailability`, or generalise both onto one
polymorphic table. Add `minimum_nights` — long-stay apartments near hospitals are exactly where that
matters. **Effort: M–L** (new table + migration).

### 2.5 Menu stock

`MenuItem.is_available` is a permanent on/off switch. Restaurants need a daily one:

- `daily_quantity` and `sold_today`, reset each service
- `available_from` / `available_until` times, so breakfast items disappear at 11am
- An auto "sold out" state that clears overnight

**Effort: M** (schema + booking-time decrement).

---

## 3. For managers — the biggest gap

The platform has `hotel_manager`, `apartment_manager`, and `restaurant_manager` roles, dependency
guards for each (`RequireHotelManager`, …), and `assign-manager` endpoints on hotels, apartments, and
restaurants. Managers are assigned to properties.

**They then have almost nothing to use.** Every manager-reachable endpoint in the entire codebase:

| Endpoint | Access |
|---|---|
| `GET /admin/hotels` | `RequireHotelManager` |
| `GET /admin/apartments` | `RequireApartmentManager` |
| `GET /admin/restaurants` | `RequireRestaurantManager` |
| `GET /admin/bookings/` and `/report/dashboard` | `RequireAdminOrManager` |

Three list endpoints and the booking report. Everything else — rooms, menus, pricing, availability,
photos, orders — is `RequireAdmin`. `admin_hotel.py` is admin-only on all 13 routes;
`admin_restaurant.py` is 28 admin-only against 1 manager route.

A hotel manager cannot add a room, change a price, block a date, or upload a photo for the hotel they
were assigned to. Every routine change goes through your admin team.

### 3.1 Manager self-service — `/manager/*`

Scoped to the properties they are assigned, enforced server-side from `manager_id`:

```
GET   /manager/me/properties                 what I manage
GET   /manager/me/dashboard                  today's arrivals, departures, occupancy, revenue

# Hotel / apartment managers
GET   /manager/rooms                         my rooms
POST  /manager/rooms                         add a room type
PUT   /manager/rooms/{id}                    edit incl. price
GET   /manager/rooms/{id}/calendar
PUT   /manager/rooms/{id}/calendar           set rates and inventory
POST  /manager/rooms/{id}/block              block dates
POST  /manager/rooms/{id}/images

# Restaurant managers
GET   /manager/menu
POST  /manager/menu                          add an item
PUT   /manager/menu/{id}                     edit, mark sold out
PUT   /manager/menu/{id}/availability        today's stock
GET   /manager/orders                        incoming orders
PUT   /manager/orders/{id}/status

# All managers
GET   /manager/bookings                      bookings at my properties
POST  /manager/bookings/{id}/confirm
POST  /manager/bookings/{id}/cancel
GET   /manager/reviews                       reviews of my property
POST  /manager/reviews/{id}/respond
```

**Effort: L**, and the highest-value work in this document after the room-count defect. It converts
three roles that currently exist on paper into a working self-service portal, and takes routine
inventory work off the admin team.

**Build the scoping helper first.** One dependency that resolves the calling user to the property ids
they manage, and every endpoint filters through it. Get that wrong once and a manager sees another
property's bookings and revenue — so it belongs in a single tested place, not repeated per route.

### 3.2 Manager notifications

Managers currently learn about a booking only by looking. Worth wiring:

- New booking at my property
- Cancellation, especially inside the free window
- New review, particularly below 3 stars
- Low inventory warning for the coming week

The notification infrastructure and broadcast endpoint already exist — this is mostly triggering.
**Effort: S.**

---

## 4. Suggested order

**Phase 1 — correctness (≈2–3 days)**
1. Room-count fix so `total_rooms` is honoured (§1.1) — this is revenue you are refusing today
2. Fix or remove the always-true availability endpoint (§1.2)
3. Availability calendar write endpoints (§2.1, which resolves §1.3)

**Phase 2 — the manager portal (≈1 week)**
4. Property-scoping dependency, tested in isolation
5. Manager rooms, calendar, and menu endpoints
6. Manager bookings and reviews
7. Manager notifications

**Phase 3 — depth (≈1 week)**
8. Inventory dashboard and alerts
9. Bulk pricing and availability operations
10. Apartment availability calendar
11. Menu daily stock

Phase 1 pays for itself immediately. Phase 2 is what makes the platform scale past a team that
manually edits every property.

---

## 5. What already works

Worth stating, so the above is not read as "inventory is broken":

- Room, apartment, restaurant, menu, thali, dining pass, and package CRUD for admins
- Booking conflict detection against blocked dates and existing bookings (correct, aside from the
  room-count issue)
- Dining passes with token counts, duration, and validity windows — the most complete inventory
  model in the codebase
- Doctor availability with weekly schedules, slot duration, max appointments, and break times
- Occupancy and room count tiles on the admin dashboard
- Manager assignment to properties

The gap is not the model. It is that the calendar has no write path and managers have no doors.
