"""The Collector port — the ONLY thing the core depends on for a data source.

The pipeline and storage import this module; they MUST NOT import any concrete adapter
(Constitution Principle I). Each source provides one implementation and self-registers
via `registry.register`. See specs/001-villa-urquiza-monitor/contracts/collector.md.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from src.models import Capabilities, Listing, ListingRef, SearchProfile, Visits


@runtime_checkable
class Collector(Protocol):
    name: str
    capabilities: Capabilities

    def search(self, profile: SearchProfile) -> list[ListingRef]:
        """Discover listings matching the profile. ListingRef carries source_id + url."""
        ...

    def get_item(self, ref: ListingRef) -> Listing:
        """Fetch and map one listing into the common model.

        MUST set `url`. MUST set `status` from the source removal signal where
        available. MUST drop (never return) a listing that has no canonical url.
        """
        ...

    def get_visits(self, ref: ListingRef) -> Optional[Visits]:
        """Return view counts, or None when capabilities.provides_visits is False."""
        ...
