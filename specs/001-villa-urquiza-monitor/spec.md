# Feature Specification: Villa Urquiza Daily Monitor (MercadoLibre)

**Feature Branch**: `001-villa-urquiza-monitor`

**Created**: 2026-06-07

**Status**: Draft

**Input**: User description: "Daily monitor for Villa Urquiza apartment listings for sale via MercadoLibre"

## Clarifications

### Session 2026-06-07

- Q: How to handle non-USD (ARS) listings against the USD 115,000 ceiling?
  → A: **USD only** — track only USD-priced listings; ignore ARS ones (no conversion).
- Q: "2 ambientes" — exactly 2, or 2+?
  → A: **Exactly 2**.
- Q: ">40 m²" refers to which area? → A: **Covered area (superficie cubierta)**.
- Q: When is a listing reported as REMOVED?
  → A: **As soon as it is absent from one successful run** (or the source reports it
  closed/paused). The partial/empty-response safeguard still applies — a failed or
  empty fetch never marks listings removed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Daily change digest (Priority: P1)

As the apartment hunter, each day I want to see what **changed** among listings that
match my Villa Urquiza criteria — what's **new**, what **changed price**, and what was
**removed** — so I can react quickly without re-scanning every listing myself.

**Why this priority**: This is the entire reason the system exists. On its own it
delivers a usable product: a daily "what changed" report. Everything else enriches it.

**Independent Test**: Run the monitor on a starting set of listings, then run it again
after a controlled change set (one new, one price drop, one removed). The digest for
the second run lists exactly those three events, each with a working listing link.

**Acceptance Scenarios**:

1. **Given** a listing matching my criteria that was not seen before, **When** the
   daily run executes, **Then** it appears in the digest as a **new** listing with its
   link, price, and neighborhood.
2. **Given** a tracked listing whose price differs from the last run, **When** the
   daily run executes, **Then** it appears as a **price change** showing old and new
   price.
3. **Given** a tracked listing that is no longer available, **When** the daily run
   executes, **Then** it appears as **removed**.
4. **Given** a previously removed listing that is available again, **When** the daily
   run executes, **Then** it appears as **relisted**.

---

### User Story 2 - Current listings with aging and views (Priority: P2)

As the apartment hunter, I want a list of all currently-active matching listings, each
showing **how long it has been on the market** and **how many times it has been
viewed**, so I can judge demand and staleness.

**Why this priority**: Adds decision-making context on top of the digest, but the
digest is valuable without it.

**Independent Test**: After a daily run, request the current-listings view and confirm
each active listing shows an age and (where the source provides it) a view count.

**Acceptance Scenarios**:

1. **Given** active matching listings, **When** I request the current list, **Then**
   each entry shows its link, price, neighborhood, and **days on market**.
2. **Given** a listing whose source provides view counts, **When** I request the list,
   **Then** the entry shows a **view count**.
3. **Given** a listing whose source does **not** provide view counts or a start date,
   **When** I request the list, **Then** the entry still appears, with those fields
   empty (no error).

---

### User Story 3 - Multiple search profiles (Priority: P3)

As the apartment hunter, I want to define more than one named search profile (other
neighborhoods or criteria) and get a separate digest and listing view for each.

**Why this priority**: The first profile (Villa Urquiza) is the MVP; multi-profile is
a natural extension once one profile works end to end.

**Independent Test**: Define a second profile and confirm its digest and listings are
tracked and reported independently from the first.

**Acceptance Scenarios**:

1. **Given** two profiles with different criteria, **When** the daily run executes,
   **Then** each profile produces its own digest and listing set with no
   cross-contamination.

---

### Edge Cases

- **Source temporarily unavailable / partial results**: a run that returns no or
  partial data MUST NOT mark any previously-tracked listing as removed (removal is
  processed only after a successful, complete run).
- **Removal timing**: after a successful run, a tracked listing absent from results, or
  reported closed/paused by the source, is reported REMOVED that same run.
- **Currency**: only USD-priced listings are tracked; ARS-priced listings are ignored.
  A price change is only reported between two USD amounts.
- **Duplicate listing within a source**: the same listing seen twice in one run is
  tracked once.
- **Missing enrichment data**: absent view count or start date leaves those fields
  empty rather than failing the listing.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST, once per day, gather all listings that match a search
  profile's criteria from the configured source.
- **FR-002**: The system MUST persist tracked listings between runs so that successive
  runs can be compared.
- **FR-003**: The system MUST detect and report, per run, four change types: **new**,
  **price change** (with old and new price), **removed**, and **relisted**.
- **FR-004**: The system MUST record, for each listing, **how long it has been on the
  market** (listing age), using the source's listing-start date when available and
  otherwise the date the system first saw the listing.
- **FR-005**: The system MUST record a listing's **view count** when the source
  exposes it, and leave it empty otherwise — without failing the run.
- **FR-006**: Every tracked listing MUST carry a canonical **link (URL)** to the
  listing on its source; a listing without a link MUST NOT be stored or reported.
- **FR-007**: After a successful run, the system MUST report a tracked listing as
  removed when it is absent from that run's results OR the source reports it
  closed/paused.
- **FR-008**: The system MUST process removals only after a successful, complete source
  response; an empty or partial/failed response MUST NOT mark any listing as removed.
- **FR-012**: The system MUST track only **USD-priced** listings; non-USD listings are
  excluded (no currency conversion).
- **FR-013**: Profile matching MUST require **exactly 2 ambientes** and **covered area
  (superficie cubierta) greater than 40 m²**.
- **FR-009**: The system MUST expose, on demand, (a) the **change digest** for a
  profile since a given date and (b) the **current active listings** for a profile.
- **FR-010**: A **search profile** MUST define the criteria used to match listings
  (operation, price ceiling, room count, minimum area, neighborhoods) and the source.
- **FR-011**: Re-running a day MUST be **idempotent**: it MUST NOT create duplicate
  listings or duplicate change events for the same observed state.

### Key Entities *(include if feature involves data)*

- **Search Profile**: a named set of match criteria (operation, price ceiling, rooms,
  minimum area, neighborhoods) plus the source to query.
- **Listing**: a tracked property — link (required), title, price, currency,
  operation, neighborhood, rooms, area, status, listing age, view count, first-seen
  and last-seen dates, active flag.
- **Change Event**: a dated record of a change to a listing — type (new / price change
  / removed / relisted), the listing link, and old/new price for price changes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a daily run, the user can retrieve the complete set of currently
  active matching listings, and every entry has a working link (100%).
- **SC-002**: In a controlled two-day test (one new, one price drop, one removed), the
  digest reports exactly those three events — no misses, no false positives.
- **SC-003**: A listing that becomes unavailable is reported as removed on the next
  successful daily run.
- **SC-004**: A newly published matching listing appears in the next day's digest
  (within one daily run, subject to source freshness).
- **SC-005**: Every active listing shows a listing age; listings whose source provides
  view counts also show a view count.
- **SC-006**: A run against an unavailable or empty source produces no false "removed"
  reports.

## Assumptions

- The first profile is **Villa Urquiza**: operation **buy (venta)**, **USD-priced
  only**, price ceiling **USD 115,000**, **exactly 2 ambientes**, **covered area
  > 40 m²**, neighborhoods **Villa Urquiza + Villa Ortúzar + Coghlan**.
- The source for this feature is **MercadoLibre**; view counts and listing-start dates
  come from the source and may lag.
- Single user, personal use; output is consumed as a backend (no UI in this feature).
- Daily cadence is sufficient; near-real-time updates are out of scope.
- Descriptive extras (natural gas, lighting, floor, building age) may be recorded but
  are **not** used to filter or rank (ranking is out of scope per the constitution).
