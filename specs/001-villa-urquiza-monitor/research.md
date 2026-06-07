# Phase 0 Research — Villa Urquiza Daily Monitor

Decisions that resolve the Technical Context. Format per decision: **Decision /
Rationale / Alternatives considered**.

## 1. Hosting & scheduling — Azure Functions (Python v2 model)

- **Decision**: One Azure Functions app using the v2 programming model in
  `function_app.py`. A **timer trigger** (`schedule` CRON) runs the daily monitor; two
  **HTTP triggers** serve `/api/changes` and `/api/listings`.
- **Rationale**: Locked-in platform; timer + HTTP in one app keeps deploy simple and
  matches the "daily run + JSON backend" shape. Consumption plan is cheap for a
  once-a-day job.
- **Alternatives**: System cron + a separate web service (more moving parts);
  in-process APScheduler (needs an always-on host — wasteful for daily).

## 2. Storage layout — Azure Table Storage

- **Decision**: Two tables.
  - **Listings**: `PartitionKey = profile`, `RowKey = "<source>:<source_id>"`.
  - **Changes**: `PartitionKey = profile`, `RowKey = "<ISO8601-timestamp>:<source_id>:<type>"`.
- **Rationale**: The `source:source_id` RowKey makes upserts idempotent (Principle V /
  FR-011) and dedupes within a source. Timestamp-prefixed Change RowKeys sort
  chronologically, so "changes since X" is an efficient range query for the digest.
- **Alternatives**: Single table with a type column (mixes lifecycles, harder queries);
  SQLite/Postgres (rejected by constitution — Table Storage from day one).

## 3. Change detection — snapshot + diff

- **Decision**: Each run builds today's matched set, loads the stored snapshot for the
  profile, and diffs: unseen id → NEW; same id, different price (same currency) →
  PRICE_CHANGE; stored-active id absent today → candidate REMOVED; previously-removed id
  present again → RELISTED.
- **Rationale**: No source exposes price history (Principle V); diffing is the only
  portable mechanism and behaves identically across sources.
- **Alternatives**: Trusting a source price-history endpoint (doesn't exist / not
  portable).

## 4. Removal confirmation — avoid false positives

- **Decision**: A stored-active listing missing from today's results is **not** removed
  immediately. Confirm via the source removal signal (MercadoLibre `status` ∈
  {paused, closed} from the item endpoint); if the signal is unavailable, require the
  listing to be **absent for 2 consecutive runs** before emitting REMOVED. A run that
  returns empty/partial data (collector error) skips removal processing entirely.
- **Rationale**: Satisfies FR-007, FR-008, SC-003, SC-006 — search ranking churn and
  transient outages must not look like delistings.
- **Alternatives**: Immediate removal on absence (false positives); status-only (misses
  hard-deleted listings that 404).

## 5. MercadoLibre adapter

- **Decision**: Adapter confined to `src/collectors/mercadolibre.py`. Site **MLA**
  (Argentina). Capabilities: `has_api=true`, `provides_visits=true`,
  `provides_listing_age=true`, `removal_signal=status`.
  - **Auth**: OAuth client-credentials app token; refresh on expiry. Credentials
    (`ML_CLIENT_ID`, `ML_CLIENT_SECRET`) from app settings.
  - **Search**: query by operation (venta), attributes (rooms, covered area), and
    **neighborhood location IDs** (Villa Urquiza / Villa Ortúzar / Coghlan), price ≤ USD
    115,000; page through results.
  - **Item → model**: `permalink` → `url`; `start_time`/`date_created` →
    `listing_started_at`; `status` → removal signal; price/currency/attributes mapped.
  - **Visits**: `GET /items/{id}/visits/time_window?last=N&unit=day` (+ total) →
    `visits_total`, `visits_last7`. Tolerate the ~48 h lag / 150-day window; null on miss.
- **Rationale**: Real API → no scraping; richest data source, good first adapter.
- **Open setup task**: register the ML developer app (no app yet) — tracked in
  quickstart + tasks, not a code blocker for the agnostic core.
- **Alternatives**: Scraping ML HTML (fragile, unnecessary given the API).

## 6. Neighborhood resolution

- **Decision**: Resolve the three barrio names to ML location IDs once and store them in
  `villa_urquiza.yaml` (with the names as comments).
- **Rationale**: Location IDs are stable and make search filtering exact; doing it once
  avoids a lookup every run.
- **Alternatives**: Free-text neighborhood matching (imprecise, noisy).

## 7. Validation strategy

- **Decision**: A **fake in-memory adapter** drives the full pipeline in contract tests
  (proves the core never imports a source); a **capability-gap test** runs an adapter
  with `provides_visits=false` end-to-end on null fields; integration tests run the
  two-day diff scenario against **Azurite**.
- **Rationale**: Directly validates Principles I & II and SC-002 before the real ML
  adapter or a second source exists.
- **Alternatives**: Live-API tests only (flaky, slow, needs credentials).
