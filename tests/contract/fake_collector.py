"""A fully in-memory Collector used to drive the pipeline without any real source.

This is the freeze reference: every real adapter mirrors this shape. It also lets the
core be tested for source-agnosticism (T012) and graceful degradation (T013) before any
real adapter exists.
"""

from __future__ import annotations

from typing import Optional

from src.models import (
    Capabilities,
    Listing,
    ListingRef,
    RemovalSignal,
    SearchProfile,
    Visits,
)

DEFAULT_CAPABILITIES = Capabilities(
    has_api=True,
    provides_visits=True,
    provides_listing_age=True,
    removal_signal=RemovalSignal.status,
)


class FakeCollector:
    """Implements the Collector protocol structurally (duck-typed)."""

    def __init__(
        self,
        items: list[Listing],
        *,
        name: str = "fake",
        capabilities: Optional[Capabilities] = None,
        visits: Optional[dict[str, Visits]] = None,
    ) -> None:
        self.name = name
        self.capabilities = capabilities or DEFAULT_CAPABILITIES
        self._items = {it.source_id: it for it in items}
        self._visits = visits or {}

    def set_items(self, items: list[Listing]) -> None:
        """Swap the visible set — handy for day-1 / day-2 diff scenarios."""
        self._items = {it.source_id: it for it in items}

    def search(self, profile: SearchProfile) -> list[ListingRef]:
        return [ListingRef(source_id=it.source_id, url=it.url) for it in self._items.values()]

    def get_item(self, ref: ListingRef) -> Listing:
        return self._items[ref.source_id]

    def get_visits(self, ref: ListingRef) -> Optional[Visits]:
        if not self.capabilities.provides_visits:
            return None
        return self._visits.get(ref.source_id)
