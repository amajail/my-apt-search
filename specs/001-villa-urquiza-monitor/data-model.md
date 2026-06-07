# Phase 1 Data Model — Villa Urquiza Daily Monitor

Source-agnostic entities. Field names are neutral (no portal-specific names). Adapters
map their payloads into these; the core only ever sees these shapes.

## Entity: SearchProfile

Config-defined (YAML); identifies what to match and where.

| Field | Type | Notes |
|-------|------|-------|
| `name` | str | profile id, used as table PartitionKey (e.g. `villa_urquiza`) |
| `source` | str | registry key selecting the adapter (e.g. `mercadolibre`) |
| `operation` | enum `venta` \| `alquiler` | `venta` for this feature |
| `price_max` | int | ceiling, with `currency` |
| `currency` | enum `USD` \| `ARS` | `USD` for this feature |
| `rooms` | int | ambientes (e.g. 2) |
| `min_area_m2` | int | covered area floor (e.g. 40) |
| `neighborhoods` | list[str] | resolved source location IDs (+ name comments) |

**Validation**: `name` and `source` required; `source` must exist in the registry;
`price_max > 0`; `neighborhoods` non-empty.

## Entity: Listing

The tracked unit. Stored in the **Listings** table.

| Field | Type | Null? | Notes |
|-------|------|-------|-------|
| `source` | str | no | e.g. `mercadolibre` |
| `source_id` | str | no | stable id within source |
| `url` | str | **no (required)** | canonical link — Principle III |
| `title` | str | no | |
| `price` | int | no | |
| `currency` | enum USD/ARS | no | |
| `operation` | enum | no | |
| `neighborhood` | str | no | |
| `rooms` | int | yes | |
| `area_m2` | int | yes | |
| `status` | enum `active`\|`paused`\|`closed`\|`unknown` | no | from source removal signal |
| `listing_started_at` | datetime | yes | source start date; null → use `first_seen` for age |
| `days_listed` | int (derived) | yes | `today − (listing_started_at ?? first_seen)` |
| `visits_total` | int | yes | null if source has no visits |
| `visits_last7` | int | yes | null if unsupported |
| `visits_checked_at` | datetime | yes | when visits were last fetched |
| `first_seen` | datetime | no | first run that saw it |
| `last_seen` | datetime | no | most recent run that saw it |
| `is_active` | bool | no | false once REMOVED confirmed |
| `removed_at` | datetime | yes | set when REMOVED |
| `missed_runs` | int | no | consecutive runs absent (for removal threshold); default 0 |
| `has_natural_gas` | bool | yes | descriptive only (not for ranking) |
| `floor` | int | yes | descriptive only |
| `age_years` | int | yes | building age, descriptive only |
| `description` | str (truncated) | yes | |
| `photo_url` | str | yes | |

**Storage keys**: `PartitionKey = profile`, `RowKey = "<source>:<source_id>"`.

**Validation**: `url` non-empty (reject otherwise); `price > 0`; enums constrained.

**State transitions**:

```
(absent)            --seen-->        active (is_active=true, missed_runs=0)
active              --price differs--> active  + PRICE_CHANGE event
active              --absent 1 run-->  active  (missed_runs=1)   [no event]
active              --status closed OR missed_runs>=2--> removed (is_active=false, removed_at set) + REMOVED event
removed             --seen again-->   active (is_active=true, missed_runs=0) + RELISTED event
```

## Entity: ChangeEvent

Append-only audit of what changed. Stored in the **Changes** table.

| Field | Type | Notes |
|-------|------|-------|
| `type` | enum `NEW`\|`PRICE_CHANGE`\|`REMOVED`\|`RELISTED` | |
| `source_id` | str | the affected listing |
| `url` | str | link (always present) |
| `title` | str | |
| `old_price` | int | PRICE_CHANGE only |
| `new_price` | int | PRICE_CHANGE only |
| `currency` | enum | |
| `occurred_at` | datetime | run timestamp |

**Storage keys**: `PartitionKey = profile`,
`RowKey = "<occurred_at ISO8601>:<source_id>:<type>"` (chronological range scans).

## Value object: Capabilities

Declared by each adapter; drives graceful degradation.

| Field | Type | Meaning |
|-------|------|---------|
| `has_api` | bool | API vs scraping (adapter-internal) |
| `provides_visits` | bool | if false → `get_visits` returns None |
| `provides_listing_age` | bool | if false → aging uses `first_seen` |
| `removal_signal` | enum `status`\|`http_404`\|`absence` | how removal is confirmed |

## Value object: Visits

Returned by `Collector.get_visits` (or `None`).

| Field | Type |
|-------|------|
| `total` | int |
| `last7` | int |
| `checked_at` | datetime |
