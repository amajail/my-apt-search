# Quickstart — run & validate the Villa Urquiza monitor locally

A validation/run guide. Implementation detail lives in `tasks.md`; entity/field detail
in [data-model.md](./data-model.md); interfaces in [contracts/](./contracts).

## Prerequisites

- Python 3.11, Azure Functions Core Tools (`func`), and **Azurite** (local Table
  emulator: `npm i -g azurite`).
- A MercadoLibre developer app (for the live smoke test only):
  set `ML_CLIENT_ID` / `ML_CLIENT_SECRET`. Not required for the fake-adapter tests.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp local.settings.json.example local.settings.json   # set AzureWebJobsStorage=UseDevelopmentStorage=true
```

## Validation scenarios

### A. Core is source-agnostic (no credentials needed)

```bash
pytest tests/contract -q
```

Expected: the `FakeCollector` drives `collect → enrich → diff → persist`; the
capability-gap test passes with null visits and `first_seen`-based aging. Proves
Constitution Principles I & II.

### B. Two-day diff scenario (Azurite) — SC-002

```bash
azurite --silent &                 # start local Table storage
pytest tests/integration -q        # day-1 snapshot, then day-2 with 1 new / 1 price drop / 1 removed
```

Expected: exactly three Change events (NEW, PRICE_CHANGE, REMOVED); no false removals;
re-running day-2 produces no duplicate events (idempotency, FR-011).

### C. End-to-end locally

```bash
azurite --silent &
func start
# trigger the daily run (debug HTTP route or invoke the timer), then:
curl "http://localhost:7071/api/changes?profile=villa_urquiza&since=2026-06-06"
curl "http://localhost:7071/api/listings?profile=villa_urquiza"
```

Expected: `/api/changes` returns the digest; `/api/listings` returns active listings,
each with a `url`, `days_listed`, and (where available) `visits_total`.

### D. MercadoLibre smoke test (needs credentials) — SC-001/004/005

```bash
python -m src.collectors.mercadolibre --profile villa_urquiza --limit 5
```

Expected: up to 5 normalized listings printed, each with `url`, `listing_started_at` →
`days_listed`, and `visits_total`.

## Done when

- Scenarios A and B pass in CI (no network).
- Scenario C returns the two JSON shapes in [contracts/api.md](./contracts/api.md).
- Scenario D returns real ML listings once the app credentials are configured.
