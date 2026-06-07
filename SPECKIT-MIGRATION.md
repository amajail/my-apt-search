# Spec Kit migration plan — my-apt-search

Handoff note so we can pick this up fresh and **iterate one step at a time**
(not all in one run). Work top-to-bottom; each step is independent.

## Decisions made
- Adopt **Spec Kit** as the source of truth.
- **Fold `docs/` into Spec Kit and remove `docs/`** (avoid two sources of truth).
- Slice by **user value (vertical)**, not by architectural layer.
- Iterate: do one Spec Kit step per session, review, then continue.

## Target structure
- `.specify/memory/constitution.md` — durable, cross-cutting invariants.
- `specs/001-villa-urquiza-meli/` — P1 MVP (spec.md → plan.md → tasks.md).
- `specs/002-zonaprop-source/` — P2.
- `docs/` removed once its content is absorbed (current files are the raw material:
  `docs/BUSINESS.md`, `docs/ARCHITECTURE.md`, `docs/sources/{mercadolibre,zonaprop}.md`).

## Feature slices (vertical, MVP-first)
- **P1 — "Daily monitor for Villa Urquiza on MercadoLibre."** Real digest
  end-to-end. The source-agnostic core is built *inside* P1 as a design
  constraint (guaranteed by the constitution), NOT as its own user story.
  Internal task order within P1: agnostic core (fake adapter) → MercadoLibre adapter.
- **P2 — "Add Zonaprop as a second source."** Exercises extensibility
  (no API, no view counts, anti-bot → stress-tests the adapter contract).
- **P3 (optional)** — more profiles / daily notification.

## Constitution should encode (draft these into constitution.md first)
1. **Source-agnostic core** — the core never imports an adapter; one-way dependency.
2. **Source Adapter Contract** — every source implements `search / get_item /
   get_visits` and declares a capabilities matrix; capability gaps degrade
   gracefully (null fields; aging falls back to `first_seen`).
3. **`url` is a required first-class field** — no listing without one.
4. **Scope guard** — monitoring only; NO ranking/scoring, no contacting sellers.
5. **Daily snapshot + diff** is how change history / price changes are derived
   (no source exposes price history).

## Doc → Spec Kit mapping
| Existing doc | Goes to |
|--------------|---------|
| BUSINESS.md → durable rules ("source-independent", "no ranking") | constitution principles |
| BUSINESS.md → what-it-tracks, profiles, outcomes | `specs/001-…/spec.md` (user stories + SC-xxx) |
| ARCHITECTURE.md → stack, pipeline, storage, API | `specs/001-…/plan.md` + `data-model.md` |
| ARCHITECTURE.md → Source Adapter Contract + common model | `specs/001-…/contracts/` |
| sources/mercadolibre.md | `specs/001-…/plan.md` or `research.md` (P1 uses MeLi) |
| sources/zonaprop.md | `specs/002-…/plan.md` + `research.md` (scraping/anti-bot) |

## Step-by-step (one per session)
1. [x] `/speckit.constitution` — DONE: `.specify/memory/constitution.md` v1.0.0
       (5 principles + tech constraints + workflow). Review when back.
2. [x] `/speckit.specify` — DONE: `specs/001-villa-urquiza-monitor/spec.md`
       (3 user stories P1/P2/P3, FR-001..011, key entities, SC-001..006).
       Quality checklist passes. Review when back.
3. [x] `/speckit.plan` — DONE: `specs/001-villa-urquiza-monitor/plan.md` +
       research.md, data-model.md, contracts/{collector,api}.md, quickstart.md.
       Constitution Check passes. `docs/ARCHITECTURE.md` now absorbed here.
4. [ ] `/speckit.tasks` — P1 task list. Review.
5. [ ] `/speckit.implement` — build P1 incrementally (core w/ fake adapter first).
6. [ ] Remove `docs/` once P1 spec+plan absorb it (keep README as index).
7. [ ] Later: `/speckit.specify` P2 "Zonaprop source", then plan/tasks/implement.

## Reference profile — Villa Urquiza (P1)
venta (buy); price ≤ **USD 115,000**; 2 ambientes; > 40 m²;
neighborhoods **Villa Urquiza + Villa Ortúzar + Coghlan**.
Tracks: new / price-change / removed / relisted, listing aging, views.
MercadoLibre = MLA site, OAuth app token, visits via
`/items/{id}/visits/time_window` (unique/day, ~48h delay, 150-day window).

> Full prior design detail lives in `docs/` (until folded in) and in the approved
> plan at `~/.claude/plans/polished-leaping-squid.md`.
