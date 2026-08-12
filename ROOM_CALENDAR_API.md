  # Rate & Availability Calendar — API

  Phase 1 of [INVENTORY_FEATURES_PROPOSAL.md](INVENTORY_FEATURES_PROPOSAL.md), covering **hotel rooms
  and apartments**: the room-count fix, the availability-endpoint fixes, and the calendar write path.

  Hotels are §1–3, apartments §4. They differ in one way that shapes everything else: a hotel `Room`
  is a room *type* with many units, an apartment is a single unit.

  Base URL: `/api/v1` · Admin endpoints require role `admin` or `super_admin`.

  ---

  ## 1. What changed in booking availability

  ### 1.1 A room type is now counted, not toggled

  A `Room` row is a room **type** — "Deluxe Double" with `total_rooms: 10` — not a single unit. The
  old conflict check rejected a booking if *any* overlapping booking existed on that room, so a hotel
  with ten deluxe rooms could sell **one per night**. Everything else was refused as "already booked".

  Availability is now a count per night:

  ```
  capacity(night) = RoomAvailability.available_rooms  (where a calendar row exists)
                    otherwise Room.total_rooms

  available = capacity(night) - bookings covering that night   >= requested quantity
  ```

  Checked for **every night** in the range, so a stay is refused only if a night in it is genuinely
  full — and the error names the date:

  ```json
  { "detail": "Only 0 room(s) left on 2026-09-02" }
  ```

  A checkout day does not consume a night, so a booking ending on the 3rd leaves the 3rd sellable.

  > **Behaviour change:** properties with `total_rooms > 1` will now accept bookings they previously
  > refused. That is the fix. Confirm `total_rooms` is set correctly on every room type before
  > deploying — a type left at a default of 1 keeps the old single-unit behaviour, and one set too
  > high will oversell.

  ### 1.2 The availability endpoint no longer always says "yes"

  `GET /hotels/{hotel_id}/rooms/{room_id}/availability` was backed by a placeholder that returned
  `true` unconditionally, so the UI showed rooms as bookable when they were not. It now delegates to
  the same check the booking flow uses, and takes proper `date` query parameters.

  ```
  GET /api/v1/hotels/{hotel_id}/rooms/{room_id}/availability?check_in=2026-09-01&check_out=2026-09-03
  ```

  ```json
  {
    "room_id": "…", "check_in": "2026-09-01", "check_out": "2026-09-03",
    "nights": 2, "available": true
  }
  ```

  `GET /bookings/rooms/{room_id}/availability` was already correct and is unchanged. Both now give the
  same answer.

  ---

  ## 2. The calendar

  `RoomAvailability` supported per-date price, inventory, blocking, and notes, but **nothing ever wrote
  to it**. These three endpoints are that write path.

  ### `GET /admin/hotels/{hotel_id}/rooms/{room_id}/calendar`

  | Param | Type | Notes |
  |---|---|---|
  | `start_date` | date | First night |
  | `end_date` | date | **Exclusive** — the first night *not* included |

  Max range 400 nights.

  ```json
  [
    {
      "date": "2026-09-01",
      "price": 6500.0,
      "available_rooms": 8,
      "booked_rooms": 3,
      "remaining_rooms": 5,
      "is_blocked": false,
      "notes": "Peak season",
      "has_override": true
    },
    {
      "date": "2026-09-02",
      "price": 5000.0,
      "available_rooms": 10,
      "booked_rooms": 0,
      "remaining_rooms": 10,
      "is_blocked": false,
      "notes": null,
      "has_override": false
    }
  ]
  ```

  `has_override: false` means that night has no calendar row and is falling back to the room's
  `price_per_night` and `total_rooms`. Render those cells differently — an admin should be able to see
  at a glance which dates they have actually priced.

  ### `PUT /admin/hotels/{hotel_id}/rooms/{room_id}/calendar`

  Bulk upsert. **Only the fields you send are changed**; the rest keep their current value, or take the
  room's defaults on a new row.

  ```json
  {
    "start_date": "2026-06-01",
    "end_date": "2026-09-01",
    "price": 6500,
    "available_rooms": 8,
    "weekdays": [4, 5]
  }
  ```

  That sets a Friday/Saturday rate across the whole summer in one call. `weekdays` is 0=Monday …
  6=Sunday; omit it to apply to every night.

  ```json
  { "room_id": "…", "days_updated": 26, "start_date": "2026-06-01", "end_date": "2026-09-01" }
  ```

  **Block dates** — maintenance, refurbishment, a private event:

  ```json
  { "start_date": "2026-07-10", "end_date": "2026-07-15",
    "is_blocked": true, "notes": "Bathroom refurbishment" }
  ```

  Send `"is_blocked": false` to put them back on sale.

  ### `DELETE /admin/hotels/{hotel_id}/rooms/{room_id}/calendar?start_date=&end_date=`

  Removes the overrides so those nights revert to the room's defaults. Soft delete — rows are retained.

  ```json
  { "message": "Cleared 26 calendar day(s)" }
  ```

  ---

  ## 3. Things to know

  **`available_rooms` defaults to 0 at the database level.** Creating a row just to set a price would
  otherwise silently take the room off sale. The service guards against this: a new row created without
  an explicit `available_rooms` inherits the room's `total_rooms`. Worth remembering if you ever insert
  rows by hand.

  **`end_date` is exclusive throughout.** 1–3 June is two nights, the 1st and the 2nd. This matches how
  `check_in`/`check_out` already work, so the calendar and a booking agree on what a night is.

  **Overrides can raise capacity, not just lower it.** Setting `available_rooms` above `total_rooms` is
  allowed — useful when a hotel releases held-back inventory for a date. Nothing clamps it, so it will
  oversell if set wrong.

  **Blocking beats capacity.** A blocked night is refused regardless of how many units are free.

  ---

  ## 4. Apartments

  An apartment is a **single unit** — there is no `total_rooms` equivalent, so one overlapping booking
  correctly takes the whole unit. The room-count fix in §1.1 does not apply here.

  ### 4.1 Three implementations that disagreed

  "Is this apartment available" was answered in three places using **two different status rules**:

  | Endpoint | Old rule | Did an unpaid `pending` booking block? |
  |---|---|---|
  | `GET /apartments/{id}/availability` | `notin_([cancelled])` | Yes |
  | `GET /stays/{id}/availability` | `notin_([cancelled])` | Yes |
  | `GET /bookings/apartments/{id}/availability` and the booking path | `in_(confirmed, in_progress, completed)` | No |

  So the two customer-facing endpoints showed an apartment as unavailable while the booking path would
  accept it — an abandoned unpaid booking suppressed a sellable unit indefinitely.

  All three now delegate to `BookingService.check_apartment_availability`. The rule is the one the
  booking path already enforced, matching hotels: **a pending booking does not hold the unit.**

  > If you want pending bookings to hold inventory, that is a deliberate feature — it needs an expiry
  > so an abandoned checkout releases the dates. Worth doing, but it is not a one-line change.

  ### 4.2 Blocking, seasonal rates, and minimum stay

  New `apartment_availability` table (migration `x8y9z0a1b2c3`), plus `apartments.minimum_nights`
  defaulting to 1.

  ```
  GET    /admin/apartments/{apartment_id}/calendar?start_date=&end_date=
  PUT    /admin/apartments/{apartment_id}/calendar
  DELETE /admin/apartments/{apartment_id}/calendar?start_date=&end_date=
  ```

  Read returns one row per night:

  ```json
  {
    "date": "2026-12-24",
    "price": 4500.0,
    "minimum_nights": 7,
    "is_blocked": false,
    "is_booked": true,
    "notes": "Festive period",
    "has_override": true
  }
  ```

  Write is the same bulk upsert shape as rooms, with `minimum_nights` instead of `available_rooms`:

  ```json
  {"start_date": "2026-12-20", "end_date": "2027-01-05",
   "price": 4500, "minimum_nights": 7, "notes": "Festive period"}
  ```

  ### 4.3 Minimum stay

  Enforced at booking time, not just displayed. The rule comes from the **arrival night** — that is
  what a guest is quoted when they pick a check-in date. A calendar row can raise it for peak dates;
  otherwise the apartment's own `minimum_nights` applies.

  ```json
  { "detail": "This apartment requires a minimum stay of 7 night(s)" }
  ```

  ### 4.4 How calendar prices interact with the tiered rates

  Apartments have `price_per_night`, `price_per_week`, and `price_per_month`, picked automatically by
  stay length. Calendar prices are used **only when every night of the stay has one**. Partial
  coverage falls back to the tiered rate.

  That rule matters: without it, pricing three nights of a thirty-night stay would silently produce a
  three-night total. And a month-long stay still gets the monthly rate rather than needing thirty
  individual overrides.

  ---

  ## 5. Not yet built

  From the proposal, still open:

  - Menu daily stock — `is_available` is a permanent flag, not a per-service quantity
  - The `/manager/*` portal — managers still cannot reach any of this
  - Inventory dashboard and alerts
  - Bulk operations across multiple properties

  The calendar endpoints above are admin-only. When the manager portal lands they should be exposed
  under `/manager/rooms/{id}/calendar` with property scoping, sharing the same service methods.

  ---

  ## 6. Source

  | Concern | File |
  |---|---|
  | Availability counting | [booking_service.py](app/services/booking_service.py) (`_room_night_capacity`, `_room_night_occupancy`, `_assert_room_available`) |
  | Calendar read/write | [booking_service.py](app/services/booking_service.py) (`get_room_calendar`, `set_room_calendar`, `clear_room_calendar`) |
  | Admin endpoints | [admin_hotel.py](app/api/v1/admin_hotel.py) |
  | Public availability | [hotels.py](app/api/v1/hotels.py) · [hotel_service.py](app/services/hotel_service.py) |
  | Schemas | [hotel.py](app/schemas/hotel.py) |
  | Apartment availability | [booking_service.py](app/services/booking_service.py) (`_assert_apartment_available`, `_apartment_base_price`) |
  | Apartment calendar | [booking_service.py](app/services/booking_service.py) (`get/set/clear_apartment_calendar`) · [admin_apartment.py](app/api/v1/admin_apartment.py) |
  | Apartment model | [apartment.py](app/models/apartment.py) (`ApartmentAvailability`) |
  | Migration | `alembic/versions/x8y9z0a1b2c3_add_apartment_availability.py` |
  | Tests | [test_room_availability.py](tests/test_room_availability.py) — 17 · [test_apartment_availability.py](tests/test_apartment_availability.py) — 20 |
