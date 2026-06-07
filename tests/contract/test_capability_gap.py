"""T013 — capability-gap: a source with no visits / no listing age runs cleanly.

Pre-validates the Zonaprop shape (no view counts) before Zonaprop exists. The pipeline
must produce listings with null visits and never raise for a missing optional capability.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.models import Capabilities, RemovalSignal
from src.pipeline.run import run_profile
from tests.contract.fake_collector import FakeCollector
from tests.fakes import FakeStorage, make_listing, make_profile

NOW = datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc)

NO_EXTRAS = Capabilities(
    has_api=False,
    provides_visits=False,
    provides_listing_age=False,
    removal_signal=RemovalSignal.absence,
)


def test_source_without_visits_runs_and_leaves_nulls():
    profile = make_profile()
    storage = FakeStorage()
    # listing_started_at omitted -> aging will fall back to first_seen (US2 enrich)
    collector = FakeCollector([make_listing("A", 100000)], capabilities=NO_EXTRAS)

    result = run_profile(profile, collector, storage, NOW)

    assert result.new == 1
    stored = storage.get_listings(profile.name)[0]
    assert stored.visits_total is None and stored.visits_last7 is None
    assert stored.first_seen == NOW  # the fallback anchor for aging
    assert stored.url  # still present (Principle III)
