"""Pure response builders for the HTTP API.

Kept free of azure.functions so they are unit-testable with any storage object that has
the read methods. The Functions HTTP triggers (function_app.py) parse query params and
json.dumps these dicts. Shapes match specs/001-villa-urquiza-monitor/contracts/api.md.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.models import ChangeEvent, Listing


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _date(value: datetime | None) -> str | None:
    return value.date().isoformat() if value else None


def _event_json(e: ChangeEvent) -> dict[str, Any]:
    out: dict[str, Any] = {
        "type": e.type.value,
        "source_id": e.source_id,
        "url": e.url,
        "title": e.title,
        "occurred_at": _iso(e.occurred_at),
    }
    if e.currency is not None:
        out["currency"] = e.currency.value
    if e.old_price is not None:
        out["old_price"] = e.old_price
    if e.new_price is not None:
        out["new_price"] = e.new_price
    return out


def _listing_json(l: Listing) -> dict[str, Any]:
    return {
        "source": l.source,
        "source_id": l.source_id,
        "url": l.url,
        "title": l.title,
        "price": l.price,
        "currency": l.currency.value,
        "neighborhood": l.neighborhood,
        "rooms": l.rooms,
        "area_m2": l.area_m2,
        "status": l.status.value,
        "days_listed": l.days_listed,
        "last_bumped_at": _date(l.last_bumped_at),
        "visits_total": l.visits_total,
        "visits_last7": l.visits_last7,
        "first_seen": _date(l.first_seen),
        "last_seen": _date(l.last_seen),
        "is_active": l.is_active,
    }


def changes_payload(storage, profile: str, since: datetime) -> dict[str, Any]:
    events = storage.get_changes_since(profile, since)
    events = sorted(events, key=lambda e: e.occurred_at)
    return {
        "profile": profile,
        "since": _date(since),
        "events": [_event_json(e) for e in events],
    }


def profiles_payload(names: list[str]) -> dict[str, Any]:
    return {"profiles": sorted(names)}


def listings_payload(storage, profile: str, active: bool = True) -> dict[str, Any]:
    listings = (
        storage.query_active_listings(profile) if active else storage.get_listings(profile)
    )
    return {
        "profile": profile,
        "count": len(listings),
        "listings": [_listing_json(l) for l in listings],
    }
