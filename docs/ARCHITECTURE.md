# my-apt-search — Architecture (source-agnostic core)

> This document contains **zero portal-specific knowledge**. It defines the common
> model, the pipeline, storage, the API, and the **Source Adapter Contract**. If a
> portal name appears here, it's a leak — move it to a source doc under
> [`sources/`](./sources).

See also: [BUSINESS.md](./BUSINESS.md) ·
[sources/mercadolibre.md](./sources/mercadolibre.md) ·
[sources/zonaprop.md](./sources/zonaprop.md).

## Stack & platform

- **Language:** Python.
- **Hosting:** Azure Functions (Python). One Function App with a **daily timer
  trigger** that runs the monitor, and **HTTP triggers** that serve the API.
- **Storage:** Azure Table Storage (`azure-data-tables`) from day one — no local DB.
- **Output:** JSON.

## Layering & dependency rule

```
   profiles (config)              API (HTTP)
        │                             │
        ▼                             ▼
   ┌───────────────────────── CORE (agnostic) ─────────────────────────┐
   │  common model · pipeline (collect→enrich→diff→persist) · storage   │
   │  depends ONLY on the Collector interface                           │
   └───────────────────────────────┬───────────────────────────────────┘
                                    │ interface (port)
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
        Adapter: source A     Adapter: source B     Adapter: source C
        (its own doc)         (its own doc)         (its own doc)
```

**One-way dependency:** adapters depend on the core model; the **core never imports
an adapter**. A registry maps a profile's `source` name to its adapter. Adding a
source = one new adapter file + one registry line + one source doc. Nothing in the
core changes.

## Source Adapter Contract

Every adapter implements this interface, and every source doc fills in the
capabilities table below.

```python
class Collector(Protocol):
    name: str
    capabilities: Capabilities          # what this source can provide
    def search(self, profile) -> list[ListingRef]: ...   # ListingRef = {source_id, url}
    def get_item(self, ref) -> Listing: ...              # map to common model
    def get_visits(self, ref) -> Visits | None: ...      # None if unsupported
```

**Capabilities matrix each source must declare** (drives graceful degradation):

| Capability | Meaning | If absent |
|------------|---------|-----------|
| `has_api` | official API vs scraping | core doesn't care; affects adapter only |
| `provides_visits` | view counts available? | `get_visits` → `None`; field null |
| `provides_listing_age` | listing-start date available? | aging falls back to `first_seen` |
| `stable_id` | durable per-listing id | required — used as `RowKey` |
| `url` | canonical listing link | **required** — every adapter must return it |
| `removal_signal` | status check / 404 / absence | core uses it for REMOVED detection |
| auth | none / token / session | encapsulated in the adapter |
| rate limits / anti-bot | how to fetch politely | encapsulated in the adapter |

The core treats every source through this contract only; capability gaps never
break the pipeline (null fields, fallbacks).

## Common model (no source fields leak in)

- **`url` is a required, first-class field** — the canonical link to the listing on
  its source. Every adapter MUST provide it; it's what the digest and API surface to
  open a listing, and it's the human-facing anchor across price changes and
  relistings. **No listing exists in the system without a `url`.**

- **`Listing`:** `source, source_id, url (required), title, price, currency,
  operation, neighborhood, ambientes, covered_m2, status, listing_started_at
  (nullable), days_listed (derived/nullable), visits_total (nullable), visits_last7
  (nullable), visits_checked_at, first_seen, last_seen, is_active, removed_at,
  has_natural_gas, floor, age_years, description (truncated), photo_url`.

- **`ChangeEvent`:** `type (NEW | PRICE_CHANGE | REMOVED | RELISTED), source_id, url,
  title, old_price, new_price, currency, occurred_at`.

Neutral names only (`listing_started_at`, not a portal-specific field).
`days_listed = today − listing_started_at`, else falls back to `today − first_seen`.

## Daily run (core pipeline — source-agnostic)

1. **Collect** — resolve the adapter from the registry; call `search(profile)`.
2. **Enrich** — `get_item` and `get_visits` (per the source's capabilities).
3. **Diff** against the stored snapshot for the profile:
   - id not stored → **NEW** + insert.
   - stored, price differs → **PRICE_CHANGE** (old/new) + update.
   - stored & active but absent today → confirm via `removal_signal`; if gone →
     **REMOVED** + mark inactive.
   - previously removed, back today → **RELISTED**.
4. **Persist** — upsert Listings (refresh `last_seen`, visits, `days_listed`),
   append events to Changes.

## Storage (Azure Table Storage)

- **Listings** — `PartitionKey = profile`, `RowKey = "<source>:<source_id>"`
  (idempotent upsert + dedupe within a source).
- **Changes** (event log) — `PartitionKey = profile`,
  `RowKey = "<timestamp>:<source_id>:<type>"` (timestamp-prefixed → naturally
  sorted, easy "since X" queries).
- Profiles start as **YAML config files** in the repo; promote to a table later.

## API (HTTP triggers)

- `GET /api/changes?profile=<name>&since=<date>` — the daily digest (primary value).
- `GET /api/listings?profile=<name>` — current tracked listings with `days_listed`,
  `visits_total`, `status`, `last_price`.
- `GET /api/profiles` — *(nice-to-have)*.

Reads come straight from storage; no recompute on request.

## Repo layout

```
my-apt-search/
  function_app.py            # daily timer + http triggers
  host.json, requirements.txt
  docs/
    BUSINESS.md  ARCHITECTURE.md
    sources/mercadolibre.md  sources/zonaprop.md
  src/
    models.py                # common model (Listing, ChangeEvent, Capabilities)
    profiles.py  profiles/villa_urquiza.yaml
    collectors/
      base.py                # Collector interface (the port) — NO source code
      registry.py            # source name -> adapter
      mercadolibre.py        # adapter #1
      zonaprop.py            # adapter #2 (later)
    pipeline/diff.py
    storage/tables.py
    config.py
  README.md  tests/
```

## Build order

1. **Agnostic core** — common model, `Collector` interface, registry, `diff`, Table
   Storage, timer + HTTP triggers, `villa_urquiza.yaml`. Proven with a **fake
   in-memory adapter** — no real source yet.
2. **MercadoLibre adapter** — see [sources/mercadolibre.md](./sources/mercadolibre.md).
3. **Zonaprop adapter** — see [sources/zonaprop.md](./sources/zonaprop.md).

## Verification

- **Contract test:** a fake adapter drives the full pipeline → proves the core is
  source-agnostic and never imports a source.
- **Capability-gap test:** an adapter with `provides_visits=false` /
  `provides_listing_age=false` runs end-to-end with null fields and the `first_seen`
  fallback (the Zonaprop shape, tested before Zonaprop exists).
- **Diff unit tests** (`pytest`): two snapshots (one price drop, one removed, one
  new) → assert exactly those three events.
- **Local end-to-end:** Azurite + `func start`, run twice with changed fixtures →
  Listings rows update and Changes rows appear (inspect via Azure Storage Explorer).

## Open questions (minor / can default)

1. Timer time-of-day (e.g. 08:00 ART) — configurable.
2. Visits enrichment cadence (48 h delay / rate limits) — default each run.
3. Removal confirmation default: status/404 check, fall back to absent N=2 days.
