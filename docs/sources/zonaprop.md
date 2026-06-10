# Source Adapter — Zonaprop

Adapter #2. **No public API → scraping.** This adapter is a deliberate **stress
test for the [Source Adapter Contract](../ARCHITECTURE.md#source-adapter-contract)**:
it lacks an API, view counts, reliable listing age, and auth — yet plugs into the
core with **no core changes**, only this adapter file + one registry line.

## Capabilities

| Capability | Value |
|------------|-------|
| `has_api` | **false** (HTML scraping) |
| `provides_visits` | **false** → `get_visits` returns `None`, `visits_*` stay null |
| `provides_listing_age` | **partial** — sometimes "publicado hace X días"; otherwise aging falls back to `first_seen` |
| `stable_id` | Zonaprop property id parsed from the listing URL |
| `url` | listing URL (required) |
| `removal_signal` | absence from search **and** listing URL returning a removed/404 page (no `status` field) |
| auth | none, but **anti-bot** (likely Cloudflare / DataDome) |
| rate limits / anti-bot | polite rate limiting; cache by listing URL |

## Search

- Barrio / operation / price are encoded in the Zonaprop **search URL**.
- Parse the results page: HTML, or an embedded JSON / `__NEXT_DATA__` blob if
  present.
- Returns `ListingRef = {source_id, url}` per match.

## Fetch strategy

- Plain HTTP first.
- Escalate to a **headless browser (Playwright)** only if blocked by anti-bot.
- Polite rate limiting; cache by listing URL to avoid re-fetching.

## Item → common model

- Map parsed fields (price, currency, ambientes, m², neighborhood) to the common
  model.
- `url` → required field; `source_id` → property id from the URL.
- `listing_started_at` set only when "publicado hace X días" is available;
  otherwise left null and aging uses `first_seen`.

## Removal signal

No `status` field like MercadoLibre. Detect removal by:

1. Absence from search results, **and**
2. The listing URL returning a removed / 404 page.

Fall back to "absent for N consecutive days" (default N=2) when ambiguous.

## Why this matters

A source missing visits, reliable age, auth, and an API still satisfies the same
interface. This confirms the layering: **the core never bends to a source** — the
source fills the contract and degrades gracefully.

## Smoke test

One search-page parse → normalized listings (with null `visits_*` and, where
unavailable, null `listing_started_at`).
