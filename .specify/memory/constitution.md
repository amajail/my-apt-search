<!--
Sync Impact Report
- Version change: (template) → 1.0.0
- Ratification: initial adoption (constitution first filled from project design docs)
- Principles defined:
  I. Source-Agnostic Core
  II. Source Adapter Contract
  III. URL Is a Required First-Class Field
  IV. Monitoring-Only Scope
  V. Daily Snapshot & Diff
- Added sections: Technology & Architecture Constraints; Development Workflow
- Removed sections: none
- Template alignment:
  ✅ .specify/templates/plan-template.md  (generic "Constitution Check" gate; no change needed)
  ✅ .specify/templates/spec-template.md  (mandatory sections compatible; no change needed)
  ✅ .specify/templates/tasks-template.md (no principle-driven task types to add; no change needed)
- Follow-up TODOs: none
-->

# my-apt-search Constitution

A personal system that **monitors apartment listings over time** and reports daily
what changed (new / price-change / removed / relisted), plus listing aging and
views. These principles are non-negotiable and bind every feature, spec, and plan.

## Core Principles

### I. Source-Agnostic Core

The core (common model, pipeline, storage, API) MUST NOT contain or import any
portal-specific knowledge. Dependency flows **one way**: adapters depend on the
core model; the core never depends on an adapter. A registry maps a profile's
`source` name to its adapter. Adding a source MUST require only a new adapter file,
one registry entry, and its own source document — **no change to the core**.

*Rationale*: the system must outlive any single portal; portal churn must never
ripple into core logic.

### II. Source Adapter Contract

Every data source MUST be integrated as an adapter implementing the shared
`Collector` interface (`search`, `get_item`, `get_visits`) and MUST declare a
**capabilities matrix** (e.g. `has_api`, `provides_visits`, `provides_listing_age`,
`stable_id`, `url`, `removal_signal`, auth, rate-limit/anti-bot strategy). Missing
capabilities MUST degrade gracefully — never break the pipeline: absent visits →
null fields; absent listing-start date → aging falls back to `first_seen`. Each
adapter owns its own auth, paging, rate limiting, and anti-bot handling.

*Rationale*: a uniform contract is what makes sources pluggable and keeps the core
oblivious to how any one source behaves.

### III. URL Is a Required First-Class Field

Every listing MUST carry a canonical `url` to the listing on its source. Adapters
MUST populate it; **no listing may exist in the system without a `url`.** It is the
human-facing anchor across price changes and relistings, and the link the digest
and API surface.

*Rationale*: the URL is the one field a human always needs to act on a listing; it
must never be optional or derived after the fact.

### IV. Monitoring-Only Scope

The system MUST track change over time and nothing more. It MUST NOT rank, score,
or otherwise editorialize listings, and MUST NOT contact sellers or transact.
Descriptive attributes (e.g. gas natural, iluminación, piso, antigüedad) MAY be
recorded but MUST NOT be used to filter or rank.

*Rationale*: scope discipline keeps the product a trustworthy observer, not an
opinionated recommender; ranking is explicitly out of scope.

### V. Daily Snapshot & Diff

Change history MUST be derived by snapshotting matching listings on a schedule
(once per day) and **diffing** against the stored snapshot — producing NEW,
PRICE_CHANGE, REMOVED, and RELISTED events. The system MUST NOT assume any source
exposes price history; price changes are detected by comparison, not fetched.

*Rationale*: no portal offers reliable price history, so the system must own change
detection itself; this also makes detection identical across all sources.

## Technology & Architecture Constraints

- **Language**: Python.
- **Hosting**: Azure Functions (Python) — a daily **timer trigger** runs the
  monitor; **HTTP triggers** serve the API.
- **Storage**: Azure Table Storage (`azure-data-tables`) from day one — no local DB.
  Listings keyed `PartitionKey = profile`, `RowKey = "<source>:<source_id>"`;
  Changes keyed by a timestamp-prefixed RowKey for "since X" queries.
- **Output**: JSON, consumed as a backend.
- **Profiles**: a profile is a named criteria set; the system is multi-profile.
  Profiles start as YAML config files.

## Development Workflow

- Work is **spec-driven** via Spec Kit: constitution → `spec.md` → `plan.md` →
  `tasks.md` → implementation, one reviewable step at a time.
- Features are sliced by **user value (vertical), MVP-first** — not by
  architectural layer. The source-agnostic architecture is a constitutional
  constraint realized inside features, not a user story of its own.
- Every `plan.md` MUST pass a **Constitution Check** against these principles
  before implementation; violations require explicit justification in the plan's
  Complexity Tracking.
- Contract and capability-gap tests MUST prove the core stays source-agnostic
  (a fake in-memory adapter drives the full pipeline; an adapter with
  `provides_visits=false` runs end-to-end on null fields).

## Governance

This constitution supersedes other practices for this project. Amendments are made
by updating this file with a rationale and a version bump:

- **MAJOR**: backward-incompatible principle removal or redefinition.
- **MINOR**: a new principle/section or materially expanded guidance.
- **PATCH**: clarifications and wording.

Every plan and review MUST verify compliance with these principles; unjustified
complexity is grounds to revise the design. Dependent Spec Kit templates
(`plan`, `spec`, `tasks`) MUST stay consistent with any amendment.

**Version**: 1.0.0 | **Ratified**: 2026-06-07 | **Last Amended**: 2026-06-07
