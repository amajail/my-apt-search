"""Common, source-agnostic domain model.

Every adapter maps its raw payload into these shapes; the core (pipeline, storage,
API) only ever sees these. Field names are neutral — no portal-specific names leak in.
See specs/001-villa-urquiza-monitor/data-model.md.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Operation(str, Enum):
    venta = "venta"
    alquiler = "alquiler"


class Currency(str, Enum):
    USD = "USD"
    ARS = "ARS"


class Status(str, Enum):
    active = "active"
    paused = "paused"
    closed = "closed"
    unknown = "unknown"


class ChangeType(str, Enum):
    NEW = "NEW"
    PRICE_CHANGE = "PRICE_CHANGE"
    REMOVED = "REMOVED"
    RELISTED = "RELISTED"


class RemovalSignal(str, Enum):
    """How a source confirms a listing is gone."""

    status = "status"        # source reports a closed/paused status
    http_404 = "http_404"    # listing URL returns not-found
    absence = "absence"      # only signal is absence from search results


class Capabilities(BaseModel):
    """Declared by each adapter; drives graceful degradation in the pipeline."""

    has_api: bool
    provides_visits: bool
    provides_listing_age: bool
    removal_signal: RemovalSignal


class ListingRef(BaseModel):
    """Lightweight discovery result from Collector.search."""

    source_id: str
    url: str = Field(min_length=1)  # Principle III: url is always present


class Visits(BaseModel):
    total: int
    last7: Optional[int] = None
    checked_at: datetime


class SearchProfile(BaseModel):
    """A named criteria set. Loaded from YAML; selects criteria + source."""

    name: str
    source: str
    operation: Operation = Operation.venta
    price_max: int = Field(gt=0)
    currency: Currency = Currency.USD  # only listings in this currency are tracked
    rooms: int = Field(gt=0)           # exact match
    min_area_m2: int = Field(gt=0)     # covered area, matched strictly greater-than
    neighborhoods: list[str] = Field(min_length=1)
    # Some adapters (e.g. zonaprop) are driven by the source's own saved-search URL whose
    # filters the structured fields above can't fully express; URL-based adapters read this
    # verbatim, slug-based adapters (e.g. argenprop) ignore it.
    search_url: Optional[str] = None


class Listing(BaseModel):
    """A tracked property. Stored in the Listings table."""

    source: str
    source_id: str
    url: str = Field(min_length=1)  # Principle III: required — never store a url-less listing
    title: str
    price: int
    currency: Currency
    operation: Operation
    neighborhood: str
    rooms: Optional[int] = None
    area_m2: Optional[int] = None
    status: Status = Status.active

    # aging
    listing_started_at: Optional[datetime] = None  # from source; null -> use first_seen
    days_listed: Optional[int] = None              # derived at enrich time

    # views (null when the source does not provide them)
    visits_total: Optional[int] = None
    visits_last7: Optional[int] = None
    visits_checked_at: Optional[datetime] = None

    # lifecycle bookkeeping (owned by the pipeline)
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    is_active: bool = True
    removed_at: Optional[datetime] = None
    missed_runs: int = 0  # retained knob; removal threshold is 1 for the first profile

    # descriptive extras (recorded only; never used to filter or rank — Principle IV)
    has_natural_gas: Optional[bool] = None
    floor: Optional[int] = None
    age_years: Optional[int] = None
    description: Optional[str] = None
    photo_url: Optional[str] = None

    @property
    def key(self) -> str:
        """Stable identity within a source — used as the Listings RowKey."""
        return f"{self.source}:{self.source_id}"


class ChangeEvent(BaseModel):
    """An append-only record of a change. Stored in the Changes table."""

    type: ChangeType
    source_id: str
    url: str = Field(min_length=1)
    title: str
    currency: Optional[Currency] = None
    old_price: Optional[int] = None  # PRICE_CHANGE only
    new_price: Optional[int] = None  # PRICE_CHANGE only
    occurred_at: datetime
