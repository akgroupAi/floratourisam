# Public Site — What's Missing

An audit of the pages and content APIs the public website serves, and what a medical tourism
platform still needs. Findings were traced through the code, not inferred from naming.

---

## Summary

Page coverage is **good** — 30+ public endpoints across home, about, contact, blog, destinations,
doctors, services, FAQ, team, testimonials, hospitality, and the quote form. The CMS is a real page
builder with SEO fields, publishing, and menu placement, so most content gaps are authoring work
rather than engineering.

Four things are genuinely missing, and the first two matter beyond "a page isn't there".

| # | Gap | Type |
|---|---|---|
| 1 | Treatment pages have no public API — but the chatbot links to them | **Broken** |
| 2 | No legal pages: privacy, terms, refund, cookies | **Compliance** |
| 3 | No sitemap or robots.txt despite SEO fields on every model | SEO |
| 4 | No global search — only blog search | Feature |

---

## 1. Treatments: linked everywhere, servable nowhere

`treatments` is a real table with admin CRUD at `/admin/site/treatments`. There are **zero public
endpoints** — no `GET /treatments`, no `/treatments/{slug}`, nothing under `/pages/treatments`.

That would be a plain gap, except three things already point at those pages:

- The **AI chatbot indexes treatments** and hands out `/treatments/{slug}` links
  ([rag_service.py](app/services/rag_service.py))
- The chatbot's site-page map advertises `/treatments` as a browsable section
- `destinations` and `services` pages reference treatments

So the assistant tells a patient "read about Total Knee Replacement here" and the link goes nowhere.
This is the most concrete defect in this document.

**Needed:**

```
GET /api/v1/treatments                    list, filter by category/destination
GET /api/v1/treatments/{slug}             detail: description, cost range, duration, FAQs
GET /api/v1/treatments/{slug}/doctors     doctors who perform it
GET /api/v1/treatments/{slug}/hospitals   where it is offered
GET /api/v1/treatments/categories
```

`/pages/services/{slug}` and `/pages/services/{slug}/doctors` already exist and are a close template
— treatments can follow the same shape. **Effort: S.**

---

## 2. No legal pages — and this one is not just a page

There is no privacy policy, terms of service, cookie policy, refund/cancellation policy, or medical
disclaimer anywhere in the API or the database.

That matters more here than on a typical site, because the platform:

- **Takes payments** through Razorpay — Indian payment aggregator rules require published terms and a
  refund/cancellation policy
- **Handles medical data** — diagnoses, reports, treatment proposals
- **Serves international patients** — GDPR applies to EU visitors regardless of where you host
- **Has a 5% platform fee and an 80% cancellation refund rule** hard-coded in
  [booking_service.py](app/services/booking_service.py), neither of which is disclosed anywhere a
  customer can read

That last point is the sharp one: you are charging a fee and applying a refund policy that exists
only in code.

**The good news:** the CMS already supports this. `CMSPage` has slug, blocks, `meta_title`,
`meta_description`, `og_*`, `canonical_url`, and publishing. So this is **authoring, not
engineering** — create pages at `/cms/pages/privacy-policy`, `terms-of-service`,
`refund-policy`, `cookie-policy`, `medical-disclaimer`.

Two things would help:

- **Seed the pages as drafts** so they exist and are obviously unfinished, rather than 404ing.
  `init_db.py` currently seeds only the superuser.
- **A `/pages/legal` index** listing published policy pages, so the footer can be generated rather
  than hard-coded.

**Effort: S** to seed and index. The writing is a legal task, not a development one.

---

## 3. No sitemap, no robots.txt

Every content model carries `meta_title` and `meta_description`, and `CMSPage` adds `og_title`,
`og_description`, `og_image`, and `canonical_url`. The SEO groundwork is done and nothing exposes it
to a crawler.

```
GET /sitemap.xml      pages, blog posts, doctors, hospitals, destinations, treatments, packages
GET /robots.txt
```

For a business that depends on organic search for international patients, this is cheap and
high-return. **Effort: S.**

Worth pairing with a check that the frontend renders `meta_*` server-side — the fields being in the
API does not help if the page ships as an empty shell.

---

## 4. Search is blog-only

`GET /pages/blog/search` exists. There is no way to search doctors, hospitals, treatments, packages,
or destinations from one place, so a visitor who knows what they want has to guess which section to
browse.

```
GET /api/v1/search?q=&types=doctor,hospital,treatment,package
```

The AI chatbot partly covers this, but a search box is what most visitors reach for first.
**Effort: M.**

---

## 5. Content pages worth adding

These have no model or endpoint, and all are standard for medical tourism:

| Page | Why it matters |
|---|---|
| **How it works** | The single most-requested page on a medical travel site — enquiry → quote → travel → treatment → follow-up |
| **Visa & travel guide** | International patients need this before anything else. Exists as chatbot knowledge, not as a page |
| **Cost comparison** | "Knee replacement: UK £12,000 vs India ₹450,000" is the core value proposition and appears nowhere |
| **Insurance & payment options** | What is accepted, what is not |
| **Accreditations & certifications** | Trust signals — JCI, NABH |
| **Patient guide / what to expect** | Pre-arrival, during stay, post-discharge |

All can be CMS pages — no schema work, just authoring and a menu entry.

---

## 6. Smaller gaps

- **Newsletter is a stub.** `POST /leads/newsletter` returns a success message and stores nothing —
  the comment says "In production, integrate with email service". Subscribers are being silently
  discarded.
- **No 404 content endpoint** — no suggested links or search prompt for the frontend to render.
- **Blog has no RSS feed.**
- **No `/pages/stats`** — impact numbers exist (`/pages/impact-stats`) but are separate from the live
  platform counts an admin dashboard already computes.
- **`/pages/contact` is registered twice** on the same path; the second registration is unreachable.

---

## 7. What is already good

Stated so the above is not read as "the site is empty":

- Home, about, contact, destinations (with doctors and hospitals per destination), services, FAQ with
  categories, team, testimonials, hero sliders, impact stats, navigation, site settings
- Blog with categories, search, comments, and moderation
- Hospitality section with its own sub-pages
- Public listings for doctors, hospitals, packages, and careers
- A CMS with blocks, publishing, SEO fields, menu placement, and role-gated pages
- Quote form with document upload, and the contact form

---

## Suggested order

**First — the two that are more than cosmetic**
1. Public treatment endpoints (§1) — fixes links the chatbot is already handing out
2. Seed legal pages and add `/pages/legal` (§2) — then get the policies written

**Then — cheap and high-return**
3. `sitemap.xml` and `robots.txt` (§3)
4. Fix the newsletter stub so subscribers are stored (§6)
5. Remove the duplicate `/pages/contact` registration (§6)

**Then — content and features**
6. How it works, visa guide, cost comparison as CMS pages (§5)
7. Global search (§4)

Items 1, 3, 4, and 5 are each a few hours. Item 2 is a short engineering task blocked on a legal one,
so it is worth starting the writing now.
