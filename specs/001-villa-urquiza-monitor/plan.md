# Implementation Plan: Villa Urquiza Daily Monitor (MercadoLibre)

**Branch**: `001-villa-urquiza-monitor` | **Date**: 2026-06-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-villa-urquiza-monitor/spec.md`

## Summary

Build a daily listing monitor for the Villa Urquiza profile. A scheduled job collects
matching listings from MercadoLibre, normalizes them into a source-agnostic model,
diffs them against the stored snapshot to emit NEW / PRICE_CHANGE / REMOVED / RELISTED
events, records aging and view counts, and exposes the change digest and current
listings as JSON over HTTP. The architecture keeps the core source-agnostic behind a
`Collector` interface; MercadoLibre is the first adapter (built inside this feature).

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: azure-functions (v2 programming model), azure-data-tables,
httpx, pydantic, pyyaml; dev: pytest, Azurite, Azure Functions Core Tools (`func`)

**Storage**: Azure Table Storage (two tables: Listings, Changes)

**Testing**: pytest (unit + contract + integration against Azurite)

**Target Platform**: Azure Functions (Linux consumption plan); local via `func start`

**Project Type**: Single backend service (Functions app)

**Performance Goals**: Not latency-sensitive. One daily run handles a small result set
(tens to low hundreds of listings per profile). API reads return stored data directly.

**Constraints**: Respect MercadoLibre API rate limits and OAuth token lifetime; visits
data lags ~48 h and is limited to a 150-day window; must not mark listings removed on a
partial/empty source response.

**Scale/Scope**: Single user, 1 profile initially (multi-profile supported by design).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance |
|-----------|------------|
| I. Source-Agnostic Core | PASS — pipeline/storage import only `collectors/base.py`; MercadoLibre lives in `collectors/mercadolibre.py`, selected via registry. |
| II. Source Adapter Contract | PASS — MercadoLibre implements `Collector` and declares its capabilities; gaps degrade (visits/age nullable). |
| III. URL required | PASS — `Listing.url` is required; normalization rejects a listing without a permalink. |
| IV. Monitoring-only | PASS — no scoring/ranking; descriptive extras stored only. |
| V. Daily Snapshot & Diff | PASS — change detection is snapshot-vs-stored; no price-history fetch. |

**Result**: All gates pass. No entries in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/001-villa-urquiza-monitor/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions + rationale
├── data-model.md        # Phase 1 — entities, fields, transitions
├── quickstart.md        # Phase 1 — run/validate locally
├── contracts/
│   ├── collector.md     # the Collector port (source adapter contract)
│   └── api.md           # HTTP API: /api/changes, /api/listings, /api/profiles
├── checklists/
│   └── requirements.md  # spec quality checklist (passing)
└── spec.md
```

### Source Code (repository root)

```text
function_app.py            # Azure Functions v2: daily timer + http triggers
host.json
requirements.txt
local.settings.json        # gitignored
src/
├── models.py              # Listing, ChangeEvent, SearchProfile, Capabilities, Visits
├── config.py              # env-driven settings (connection string, ML creds)
├── profiles.py            # load YAML profiles
├── profiles/
│   └── villa_urquiza.yaml
├── collectors/
│   ├── base.py            # Collector interface (the port) — NO source code
│   ├── registry.py        # source name -> adapter
│   └── mercadolibre.py    # adapter #1 (auth + search + item + visits)
├── pipeline/
│   ├── run.py             # orchestrates collect -> enrich -> diff -> persist
│   └── diff.py            # snapshot vs stored -> [ChangeEvent], removal logic
└── storage/
    └── tables.py          # azure-data-tables: upsert_listing, query, append_change
tests/
├── contract/             # fake adapter drives the pipeline; capability-gap test
├── integration/          # Azurite-backed two-day diff scenario
└── unit/                 # diff, normalize, profile loading
```

**Structure Decision**: Single backend service. The `Collector` interface in
`src/collectors/base.py` is the only thing `pipeline/` and `storage/` know about a
source — this enforces Constitution Principle I. MercadoLibre specifics are confined to
`src/collectors/mercadolibre.py` and documented in `contracts/collector.md` +
`research.md`.

## Complexity Tracking

> No constitution violations. Section intentionally empty.
