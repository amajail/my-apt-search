"""Daily run orchestration: collect -> (enrich) -> diff -> persist. Source-agnostic.

`run_profile` takes the collector and storage as arguments, so it is fully testable with
a FakeCollector + in-memory storage (no source, no Azure). `run_profile_for_source`
is the thin wiring used by the timer trigger; it resolves the adapter from the registry
and builds real storage.

FR-008: if the collector raises (a failed/partial fetch), the exception propagates out
of `run_profile` BEFORE the diff — so no removals are processed on a bad run.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from src.collectors.base import Collector
from src.models import ChangeType, SearchProfile
from src.pipeline.diff import diff

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    profile: str
    seen: int
    new: int
    price_changes: int
    removed: int
    relisted: int


def run_profile(
    profile: SearchProfile,
    collector: Collector,
    storage,
    now: Optional[datetime] = None,
) -> RunResult:
    now = now or datetime.now(timezone.utc)

    refs = collector.search(profile)
    # A get_item failure propagates -> we never reach diff -> no removals (FR-008).
    current = [collector.get_item(ref) for ref in refs]

    # NOTE: visits/aging enrichment is US2 (T028); skipped here.

    stored = storage.get_listings(profile.name)
    upserts, events = diff(current, stored, now)

    for listing in upserts:
        storage.upsert_listing(profile.name, listing)
    for event in events:
        storage.append_change(profile.name, event)

    counts = {t: 0 for t in ChangeType}
    for e in events:
        counts[e.type] += 1

    result = RunResult(
        profile=profile.name,
        seen=len(current),
        new=counts[ChangeType.NEW],
        price_changes=counts[ChangeType.PRICE_CHANGE],
        removed=counts[ChangeType.REMOVED],
        relisted=counts[ChangeType.RELISTED],
    )
    logger.info(
        "run %s: seen=%d new=%d price_changes=%d removed=%d relisted=%d",
        result.profile,
        result.seen,
        result.new,
        result.price_changes,
        result.removed,
        result.relisted,
    )
    return result


def run_profile_for_source(
    profile: SearchProfile,
    *,
    settings=None,
    now: Optional[datetime] = None,
) -> RunResult:
    """Wiring for the timer trigger. Imports the registry (never an adapter)."""
    from src.collectors import registry
    from src.config import load_settings
    from src.storage.tables import Storage

    settings = settings or load_settings()
    storage = Storage(settings.storage_connection_string)
    storage.ensure_tables()
    collector = registry.get_collector(profile.source)
    return run_profile(profile, collector, storage, now)
