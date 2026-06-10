# Contract — HTTP API

JSON read API over stored data. No recompute on request; the daily run produces
everything. All responses `application/json`.

## GET /api/changes

The daily digest — the primary deliverable (User Story 1).

**Query params**: `profile` (required), `since` (ISO date, optional; default = last 24 h).

**200 response**:

```json
{
  "profile": "villa_urquiza",
  "since": "2026-06-06",
  "events": [
    {
      "type": "PRICE_CHANGE",
      "source_id": "MLA-1234567890",
      "url": "https://...",
      "title": "Depto 2 amb Villa Urquiza",
      "old_price": 119000,
      "new_price": 112000,
      "currency": "USD",
      "occurred_at": "2026-06-07T08:00:00Z"
    },
    { "type": "NEW",     "source_id": "MLA-...", "url": "https://...", "title": "...", "currency": "USD", "occurred_at": "..." },
    { "type": "REMOVED", "source_id": "MLA-...", "url": "https://...", "title": "...", "occurred_at": "..." }
  ]
}
```

`old_price`/`new_price` present only for `PRICE_CHANGE`.

## GET /api/listings

Current tracked listings with aging + views (User Story 2).

**Query params**: `profile` (required), `active` (bool, optional; default true).

**200 response**:

```json
{
  "profile": "villa_urquiza",
  "count": 1,
  "listings": [
    {
      "source": "mercadolibre",
      "source_id": "MLA-1234567890",
      "url": "https://...",
      "title": "Depto 2 amb Villa Urquiza",
      "price": 112000,
      "currency": "USD",
      "neighborhood": "Villa Urquiza",
      "rooms": 2,
      "area_m2": 45,
      "status": "active",
      "days_listed": 23,
      "visits_total": 540,
      "visits_last7": 31,
      "first_seen": "2026-05-15",
      "last_seen": "2026-06-07",
      "is_active": true
    }
  ]
}
```

`visits_*` and `days_listed` may be `null` when the source doesn't provide them
(Principle II graceful degradation). `url` is always present (Principle III).

## GET /api/profiles  *(nice-to-have)*

```json
{ "profiles": ["villa_urquiza"] }
```

## Errors

| Status | When |
|--------|------|
| 400 | missing/invalid `profile` |
| 404 | unknown profile name |
| 500 | storage unavailable |
