---
description: "Task list for Villa Urquiza Daily Monitor (001)"
---

# Tasks: Villa Urquiza Daily Monitor (MercadoLibre)

**Input**: Design documents from `specs/001-villa-urquiza-monitor/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: INCLUDED — the constitution mandates a contract test (core stays
source-agnostic) and a capability-gap test, and the spec defines Independent Tests per
story (e.g. the two-day diff). Test tasks are written before their implementation.

**Organization**: grouped by user story; each story is an independently testable increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]** = parallelizable (different files, no incomplete-task dependency)
- **[Story]** = US1 / US2 / US3 (omitted for Setup, Foundational, Polish)
- Paths are repo-root relative; single-project layout per plan.md.

---

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Create project structure per plan.md: `function_app.py`, `host.json`, `requirements.txt`, `local.settings.json.example`, `src/`, `src/collectors/`, `src/pipeline/`, `src/storage/`, `src/profiles/`, `tests/{contract,integration,unit}/`
- [x] T002 Populate `requirements.txt` (azure-functions, azure-data-tables, httpx, pydantic, pyyaml; dev: pytest, pytest-asyncio) and install into `.venv`
- [x] T003 [P] Configure tooling: `pytest.ini` (test paths + markers), ruff/black config, and `local.settings.json.example` with `AzureWebJobsStorage=UseDevelopmentStorage=true` + `ML_CLIENT_ID`/`ML_CLIENT_SECRET` placeholders

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T004 [P] Common model in `src/models.py`: `Listing`, `ChangeEvent`, `SearchProfile`, `Capabilities`, `Visits`, `ListingRef` (pydantic) per data-model.md — `Listing.url` required; enums for operation/currency/status/change-type
- [x] T005 [P] Settings loader in `src/config.py`: storage connection string + ML credentials from environment
- [x] T006 [P] `Collector` interface (Protocol) in `src/collectors/base.py`: `name`, `capabilities`, `search`, `get_item`, `get_visits` — **no source code here** (the port)
- [x] T007 Collector registry in `src/collectors/registry.py`: `get_collector(name)` mapping source name → adapter factory
- [x] T008 Storage wrapper in `src/storage/tables.py`: ensure tables; `upsert_listing`, `query_active_listings(profile)`, `append_change`, `get_changes_since(profile, since)` with the keys from data-model.md
- [x] T009 [P] Profile loader in `src/profiles.py` + `src/profiles/villa_urquiza.yaml` (venta, USD-only, price_max 115000, rooms exactly 2, min covered area 40, barrio location IDs for Villa Urquiza/Villa Ortúzar/Coghlan as TODO placeholders + name comments)
- [x] T010 [P] `FakeCollector` test double in `tests/contract/fake_collector.py`: configurable refs/items/visits and capabilities (drives contract + capability-gap tests)
- [x] T011 Azure Functions skeleton in `function_app.py` + `host.json`: empty timer-trigger and http-trigger stubs that import the app cleanly

**Checkpoint**: Foundation ready — user stories can begin.

---

## Phase 3: User Story 1 - Daily change digest (Priority: P1) 🎯 MVP

**Goal**: A daily run collects matching listings from MercadoLibre, diffs vs the stored
snapshot, and exposes NEW / PRICE_CHANGE / REMOVED / RELISTED as JSON.

**Independent Test**: Run a starting snapshot, then a second run with one new, one price
drop, one removed → `/api/changes` reports exactly those three events.

### Tests for User Story 1 (write first, ensure they fail)

- [ ] T012 [P] [US1] Contract test in `tests/contract/test_pipeline_agnostic.py`: `FakeCollector` drives `pipeline.run` end-to-end; assert `src/pipeline` imports no adapter module
- [ ] T013 [P] [US1] Capability-gap test in `tests/contract/test_capability_gap.py`: `FakeCollector` with `provides_visits=False`, `provides_listing_age=False` → null visits, `first_seen`-based aging, no error
- [ ] T014 [P] [US1] Diff unit tests in `tests/unit/test_diff.py`: new / price-change / removed (absent-1-run) / relisted, idempotent re-run, and **no removals when the fetch failed/partial** (FR-008)
- [ ] T015 [P] [US1] Integration two-day diff in `tests/integration/test_two_day_diff.py` (Azurite): day-1 snapshot → day-2 (1 new, 1 price drop, 1 removed) yields exactly 3 events; re-run day-2 yields none
- [ ] T016 [P] [US1] API contract test in `tests/contract/test_api_changes.py`: `GET /api/changes` matches `contracts/api.md` shape

### Implementation for User Story 1

- [ ] T017 [US1] Diff logic in `src/pipeline/diff.py`: snapshot vs stored → `[ChangeEvent]`; removal on absent-from-successful-run OR status closed/paused; relisted on reappearance (data-model state machine)
- [ ] T018 [US1] Pipeline orchestration in `src/pipeline/run.py`: resolve collector → `search` → `get_item` → diff → persist; **skip removal processing if the collector raised/returned partial** (FR-008)
- [ ] T019 [US1] MercadoLibre OAuth (client-credentials + token refresh) in `src/collectors/mercadolibre.py`
- [ ] T020 [US1] MercadoLibre `search` in `src/collectors/mercadolibre.py`: USD-only, exactly 2 ambientes, covered area > 40 m², price ≤ 115000 USD, barrio location IDs, paging (depends T019)
- [ ] T021 [US1] MercadoLibre `get_item` → `Listing` in `src/collectors/mercadolibre.py`: `permalink`→url, `status`→removal signal, price/currency/attrs; register in `registry.py` (depends T020)
- [ ] T022 [US1] Daily timer trigger in `function_app.py` invoking `pipeline.run` for the Villa Urquiza profile
- [ ] T023 [US1] `GET /api/changes` HTTP trigger in `function_app.py` reading `get_changes_since`
- [ ] T024 [US1] Structured logging + error handling around the daily run (run summary: counts of new/changed/removed)

**Checkpoint**: MVP — a real daily digest works end-to-end and is independently testable.

---

## Phase 4: User Story 2 - Current listings with aging and views (Priority: P2)

**Goal**: Expose all active matching listings with days-on-market and view counts.

**Independent Test**: After a run, `/api/listings` returns active listings each with
`days_listed` and (where supported) `visits_total`; unsupported fields are null.

### Tests for User Story 2 (write first)

- [ ] T025 [P] [US2] API contract test in `tests/contract/test_api_listings.py`: `GET /api/listings` matches `contracts/api.md`
- [ ] T026 [P] [US2] Integration test in `tests/integration/test_listings_view.py` (Azurite): listings carry `days_listed` and `visits_total`; a no-visits source yields null without error

### Implementation for User Story 2

- [ ] T027 [US2] Implement `get_visits` in `src/collectors/mercadolibre.py` (`/items/{id}/visits/time_window`, total + last7) and set `capabilities.provides_visits=True`
- [ ] T028 [US2] Enrich step in `src/pipeline/run.py`: call `get_visits` per capabilities; compute `days_listed` from `listing_started_at ?? first_seen`
- [ ] T029 [US2] Persist visits/aging fields via `upsert_listing` in `src/storage/tables.py`
- [ ] T030 [US2] `GET /api/listings` HTTP trigger in `function_app.py` (with `active` filter)

**Checkpoint**: US1 + US2 both work independently.

---

## Phase 5: User Story 3 - Multiple search profiles (Priority: P3)

**Goal**: Track more than one profile, each with its own digest and listings.

**Independent Test**: Two profiles with different criteria are tracked independently with
no cross-contamination.

### Tests for User Story 3 (write first)

- [ ] T031 [P] [US3] Integration test in `tests/integration/test_multi_profile.py` (Azurite): two profiles, separate digests/listings, no bleed

### Implementation for User Story 3

- [ ] T032 [US3] Multi-profile loading in `src/profiles.py`; iterate all profiles in the timer trigger / `pipeline.run`
- [ ] T033 [P] [US3] Add a second example profile in `src/profiles/` to exercise isolation
- [ ] T034 [US3] `GET /api/profiles` HTTP trigger in `function_app.py`

**Checkpoint**: all stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T035 [P] Unit tests for profile loading + ML normalization in `tests/unit/`
- [ ] T036 Retry/backoff around ML rate limits + token expiry in `src/collectors/mercadolibre.py`
- [ ] T037 [P] Update `README.md` run/deploy notes; execute `quickstart.md` scenarios A–C
- [ ] T038 Fold remaining `docs/` content into specs and remove `docs/` (migration step 6); keep README as index
- [ ] T039 [P] CI config to run contract + unit + integration (Azurite) tests

---

## Dependencies & Execution Order

- **Setup (P1)** → **Foundational (P2)** blocks everything → **US1 (P3)** = MVP.
- US2 and US3 depend on Foundational; both build on US1's pipeline but each is
  independently testable. Recommended order: US1 → US2 → US3.
- Within a story: tests (fail first) → models/diff → collector → triggers/endpoints.
- Polish last.

### Parallel opportunities

- Setup T003; Foundational T004/T005/T006/T009/T010 (different files).
- US1 tests T012–T016 all [P]. US2 tests T025/T026 [P].
- MercadoLibre tasks T019→T020→T021 are sequential (same file).

## Implementation Strategy

**MVP = Phase 1 + Phase 2 + Phase 3 (US1).** Build the agnostic core proven by the
FakeCollector contract/capability-gap tests, then the MercadoLibre adapter, then the
timer + `/api/changes`. STOP and validate the two-day diff (SC-002) before US2/US3.

## Notes

- The contract test (T012) is the guardrail for Constitution Principle I — keep it green.
- Commit after each task or logical group.
- Feature 002 (Zonaprop) will add one adapter file + one registry line — no core change.
