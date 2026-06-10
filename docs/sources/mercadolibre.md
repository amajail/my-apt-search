# Source Adapter — MercadoLibre

Adapter #1. **API-based, rich data.** Implements the
[Source Adapter Contract](../ARCHITECTURE.md#source-adapter-contract). All
MercadoLibre-specific knowledge lives here; the core knows none of it.

## Capabilities

| Capability | Value |
|------------|-------|
| `has_api` | **true** (official REST API) |
| `provides_visits` | **true** |
| `provides_listing_age` | **true** |
| `stable_id` | ML item id (e.g. `MLA-1234567890`) |
| `url` | item `permalink` |
| `removal_signal` | item `status` (`active` / `paused` / `closed`) |
| auth | OAuth app token (client-credentials) |
| rate limits / anti-bot | standard API rate limits; no anti-bot |

## Search

- ML Search API on site **MLA** (Argentina).
- Filter by operation (venta), attributes (rooms, covered area), and
  **neighborhood location IDs** — resolve Villa Urquiza / Villa Ortúzar / Coghlan
  to their ML neighborhood ids.
- Returns `ListingRef = {source_id, url}` per match.

## Item → common model

- `start_time` / `date_created` → `listing_started_at` (drives aging).
- `status` (`active` / `paused` / `closed`) → `removal_signal`.
- `permalink` → `url` (required).
- price, currency, attributes → corresponding common-model fields.
- Text signals (gas natural, iluminación, piso, antigüedad) pulled from title +
  description + attributes and stored as descriptive fields.

## Visits / views

- `GET /items/{ITEM_ID}/visits/time_window?last=N&unit=day` (plus total-visits
  endpoints) → `visits_total`, `visits_last7`.
- **Caveats:** counted unique-per-day, **~48 h delay**, **150-day** max window.
  Needs the access token.

## Price history

None exposed by ML. Derived by the core via daily snapshot + diff (not adapter
concern).

## Auth — setup (no app yet)

The Search / Items / Visits endpoints require an OAuth app token. Setup steps to
include in the build:

1. Register an application at **developers.mercadolibre.com.ar**.
2. Obtain the app's `ML_CLIENT_ID` and `ML_CLIENT_SECRET`.
3. Store them in the Function App settings (and `local.settings.json` for local
   dev — gitignored).
4. The adapter fetches/refreshes the access token (client-credentials) before
   each run.

## Smoke test

One authenticated **search + item + visits** call for Villa Urquiza prints N
normalized listings with `days_listed` and `visits_total`.
