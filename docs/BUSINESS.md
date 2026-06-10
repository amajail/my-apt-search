# my-apt-search — Business

## Purpose

A personal tool that **monitors apartment listings for sale** in Buenos Aires and
tracks how they change over time. It is **not** a search-ranking tool. Each day it
gathers listings that match my criteria and tells me **what changed since
yesterday**.

## What it does (per profile, once a day)

- **New** listings matching my filters.
- **Price changes** on listings already being tracked.
- **Removed** listings (delisted / no longer available).
- **Aging** — how long each listing has been on the market.
- **Views** — how many times a listing has been seen by others (where the source
  exposes it).

The headline value is the **daily change digest** (new / price-changed / removed),
backed by a full list of currently tracked listings with their age and view counts.

## Search profiles

A **profile** is a named set of criteria. The system is multi-profile so more
cities or filters can be added later without changing how it works.

**First profile — Villa Urquiza**

| Criterion | Value |
|-----------|-------|
| Operation | venta (buy) |
| Price ceiling | USD 115,000 |
| Ambientes | 2 |
| Covered area | > 40 m² |
| Neighborhoods | Villa Urquiza + Villa Ortúzar + Coghlan |

Nice-to-haves recorded when available but **not** used to filter or rank:
gas natural, buena iluminación, piso 3°+, antigüedad < 15 años.

## Requirements

- **Source-independent.** The tool must not be tied to any single portal. New
  sources are added without changing the core. Start with MercadoLibre, then
  Zonaprop.
- **Personal use**, single user.
- Output is **JSON**, consumed as a backend by a future frontend or notification.

## Out of scope

- No ranking or scoring of listings.
- No contacting sellers or booking through the tool.
- Not a public product.
