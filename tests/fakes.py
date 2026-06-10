"""In-memory fakes for unit/contract tests (no Azure, no Azurite)."""

from __future__ import annotations

from datetime import datetime

from src.models import ChangeEvent, Currency, Listing, Operation, SearchProfile


def make_profile(name: str = "t", source: str = "fake") -> SearchProfile:
    return SearchProfile(
        name=name,
        source=source,
        price_max=200000,
        rooms=2,
        min_area_m2=40,
        neighborhoods=["x"],
    )


def make_listing(source_id: str, price: int, *, source: str = "fake", **overrides) -> Listing:
    data = dict(
        source=source,
        source_id=source_id,
        url=f"https://example/{source_id}",
        title=f"Depto {source_id}",
        price=price,
        currency=Currency.USD,
        operation=Operation.venta,
        neighborhood="Villa Urquiza",
        rooms=2,
        area_m2=45,
    )
    data.update(overrides)
    return Listing(**data)


class FakeStorage:
    """Mirrors the Storage facade used by the pipeline and API, in memory."""

    def __init__(self) -> None:
        self.listings: dict[str, dict[str, Listing]] = {}
        self.changes: dict[str, list[ChangeEvent]] = {}

    def ensure_tables(self) -> None:  # no-op
        pass

    # --- Listings ---
    def upsert_listing(self, profile: str, listing: Listing) -> None:
        self.listings.setdefault(profile, {})[listing.key] = listing.model_copy(deep=True)

    def get_listings(self, profile: str) -> list[Listing]:
        return list(self.listings.get(profile, {}).values())

    def query_active_listings(self, profile: str) -> list[Listing]:
        return [l for l in self.get_listings(profile) if l.is_active]

    # --- Changes ---
    def append_change(self, profile: str, event: ChangeEvent) -> None:
        self.changes.setdefault(profile, []).append(event)

    def get_changes_since(self, profile: str, since: datetime) -> list[ChangeEvent]:
        return [e for e in self.changes.get(profile, []) if e.occurred_at >= since]
