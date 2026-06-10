"""Azure Table Storage wrapper.

Two tables (keys per data-model.md):
- Listings: PartitionKey = profile, RowKey = "<source>:<source_id>"
- Changes:  PartitionKey = profile, RowKey = "<occurred_at ISO8601>:<source_id>:<type>"

This module is source-agnostic; it persists/loads the common model only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from azure.data.tables import TableServiceClient, UpdateMode

from src.models import ChangeEvent, Listing

LISTINGS_TABLE = "Listings"
CHANGES_TABLE = "Changes"


def _strip_system_keys(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        k: v
        for k, v in entity.items()
        if k not in ("PartitionKey", "RowKey", "Timestamp", "etag")
    }


def _listing_to_entity(profile: str, listing: Listing) -> dict[str, Any]:
    # mode="json" -> enums become values, datetimes become ISO strings (Table-friendly).
    data = {k: v for k, v in listing.model_dump(mode="json").items() if v is not None}
    data["PartitionKey"] = profile
    data["RowKey"] = listing.key
    return data


def _entity_to_listing(entity: dict[str, Any]) -> Listing:
    # pydantic coerces ISO strings back to datetime and strings back to enums;
    # extra keys (PartitionKey/RowKey/Timestamp) are ignored.
    return Listing(**_strip_system_keys(dict(entity)))


def _change_row_key(event: ChangeEvent) -> str:
    return f"{event.occurred_at.isoformat()}:{event.source_id}:{event.type.value}"


def _change_to_entity(profile: str, event: ChangeEvent) -> dict[str, Any]:
    data = {k: v for k, v in event.model_dump(mode="json").items() if v is not None}
    data["PartitionKey"] = profile
    data["RowKey"] = _change_row_key(event)
    return data


def _entity_to_change(entity: dict[str, Any]) -> ChangeEvent:
    return ChangeEvent(**_strip_system_keys(dict(entity)))


class Storage:
    """Thin facade over the two tables. Construct once per run."""

    def __init__(self, connection_string: str) -> None:
        self._svc = TableServiceClient.from_connection_string(connection_string)

    def ensure_tables(self) -> None:
        self._svc.create_table_if_not_exists(LISTINGS_TABLE)
        self._svc.create_table_if_not_exists(CHANGES_TABLE)

    # --- Listings -------------------------------------------------------------

    def upsert_listing(self, profile: str, listing: Listing) -> None:
        self._svc.get_table_client(LISTINGS_TABLE).upsert_entity(
            _listing_to_entity(profile, listing), mode=UpdateMode.REPLACE
        )

    def get_listings(self, profile: str) -> list[Listing]:
        """All tracked listings for a profile (active and removed) — used by diff."""
        client = self._svc.get_table_client(LISTINGS_TABLE)
        q = f"PartitionKey eq '{profile}'"
        return [_entity_to_listing(e) for e in client.query_entities(q)]

    def query_active_listings(self, profile: str) -> list[Listing]:
        """Active listings only — used by GET /api/listings."""
        client = self._svc.get_table_client(LISTINGS_TABLE)
        q = f"PartitionKey eq '{profile}' and is_active eq true"
        return [_entity_to_listing(e) for e in client.query_entities(q)]

    # --- Changes --------------------------------------------------------------

    def append_change(self, profile: str, event: ChangeEvent) -> None:
        self._svc.get_table_client(CHANGES_TABLE).create_entity(
            _change_to_entity(profile, event)
        )

    def get_changes_since(self, profile: str, since: datetime) -> list[ChangeEvent]:
        client = self._svc.get_table_client(CHANGES_TABLE)
        q = f"PartitionKey eq '{profile}' and RowKey ge '{since.isoformat()}'"
        return [_entity_to_change(e) for e in client.query_entities(q)]
