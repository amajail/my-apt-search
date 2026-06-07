# Contributing — working with 2 developers

This project is built **spec-driven** (Spec Kit) and **source-agnostic** (see
[`.specify/memory/constitution.md`](.specify/memory/constitution.md)). That design is
what lets two people work in parallel with almost no file conflicts.

## Roles

| Dev | Lane | Owns |
|-----|------|------|
| **Dev A — Core & Platform** | pipeline, storage, API, Functions host, profiles | `src/models.py`, `src/pipeline/`, `src/storage/`, `function_app.py`, `src/profiles.py`, `src/config.py`, the test harness |
| **Dev B — Sources/Adapters** | data-source adapters | `src/collectors/mercadolibre.py`, later all of feature `002` (Zonaprop), adapter rate-limit/retry |

The lanes touch different files. They meet only at the **`Collector` contract**
(`src/collectors/base.py`) and the **common model** (`src/models.py`).

> Load balance: Dev A owns more *files*, but Dev B owns the two hardest *problems*
> (MercadoLibre OAuth/visits, then Zonaprop scraping + anti-bot). It evens out across
> the life of the project.

## The one rule: freeze the interfaces first

There is exactly one serialization point — **Phase 2 Foundational** in
[`specs/001-villa-urquiza-monitor/tasks.md`](specs/001-villa-urquiza-monitor/tasks.md)
(T004–T011). **Dev A lands these solo and announces the freeze.** They define:

- `src/models.py` — the common shapes (T004)
- `src/collectors/base.py` — the `Collector` port (T006)
- `src/collectors/registry.py` (T007)
- `src/storage/tables.py` signatures (T008)
- `tests/contract/fake_collector.py` — the stand-in everyone codes against (T010)

After the freeze, both devs work in parallel against stable signatures. **Changing a
frozen signature is a deliberate, announced PR** (it ripples), never a casual edit.

## Task assignment (feature 001)

| Phase | Dev A | Dev B |
|-------|-------|-------|
| 1 Setup | T001–T003 | — |
| 2 Foundational *(freeze)* | T004–T011 | — |
| 3 US1 (MVP) | T012–T018, T022–T024 | T019–T021 (MercadoLibre adapter) |
| 4 US2 | T025, T026, T028, T029, T030 | T027 (`get_visits`) |
| 5 US3 | T031–T034 | — |
| 6 Polish | T035, T037, T038, T039 | T036 (ML retry/backoff) |

Dev B is unblocked by the **FakeCollector**: Dev A's pipeline/API work never waits on
the real MercadoLibre code, and vice versa.

## Branch & PR model

- Base feature branch: `001-villa-urquiza-monitor`.
- Each dev works on **short-lived task branches** off it, e.g.
  `001/devB/meli-search`, and opens a **small PR per task or checkpoint** back into the
  feature branch.
- **Merge gate (CI):** the contract test `tests/contract/test_pipeline_agnostic.py`
  (T012) and the capability-gap test (T013) MUST pass. If a PR makes the core import an
  adapter, the build goes red — that's the guardrail for Constitution Principle I.
- Keep PRs small; rebase on the feature branch often to avoid drift.
- Commit footer: `Co-Authored-By: ...` and reference the task id (e.g. `T020`).

## Adding the second source (feature 002 — Zonaprop)

**Do this only after** feature 001's Foundational phase is frozen (ideally after the
001 MVP is proven), so Zonaprop builds on a stable `Collector` contract. Then Dev B
owns it end to end:

```bash
# from a clean checkout of the frozen contract (001 merged, or its foundational base)
/speckit.specify   "Zonaprop apartment-listings source adapter"
/speckit.clarify    # optional
/speckit.plan
/speckit.tasks
/speckit.implement
```

Because Zonaprop is just another adapter, integrating it is **one new file
(`src/collectors/zonaprop.py`) + one line in `registry.py`** — no change to Dev A's
core. The capability-gap test (T013) already proves the core handles a source with no
view counts, which is exactly Zonaprop's shape.

## Definition of done (per task)

- Code + its tests committed; contract/capability tests green locally.
- For an adapter: declares its `Capabilities` honestly and sets `Listing.url`.
- For core: imports no adapter module.
- PR merged into the feature branch with the task id referenced.

## Local validation

See [`specs/001-villa-urquiza-monitor/quickstart.md`](specs/001-villa-urquiza-monitor/quickstart.md):
fake-adapter contract tests (no creds), the Azurite two-day diff, and the MercadoLibre
smoke test.
