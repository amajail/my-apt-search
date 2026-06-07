"""T025 — GET /api/listings payload: aging + views, active filter."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.api import listings_payload
from src.models import Visits
from src.pipeline.run import run_profile
from tests.contract.fake_collector import FakeCollector
from tests.fakes import FakeStorage, make_listing, make_profile

NOW = datetime(2026, 6, 30, 8, 0, tzinfo=timezone.utc)


def test_listings_payload_includes_aging_and_visits():
    profile = make_profile()
    storage = FakeStorage()
    collector = FakeCollector(
        [make_listing("A", 100000, listing_started_at=NOW - timedelta(days=12))],
        visits={"A": Visits(total=200, last7=10, checked_at=NOW)},
    )
    run_profile(profile, collector, storage, NOW)

    item = listings_payload(storage, profile.name)["listings"][0]
    assert item["days_listed"] == 12
    assert item["visits_total"] == 200 and item["visits_last7"] == 10
    assert item["url"] and item["is_active"] is True


def test_active_filter_excludes_removed():
    profile = make_profile()
    storage = FakeStorage()
    collector = FakeCollector([make_listing("A", 100000), make_listing("B", 120000)])
    run_profile(profile, collector, storage, NOW)

    collector.set_items([make_listing("A", 100000)])  # B disappears -> REMOVED
    run_profile(profile, collector, storage, NOW + timedelta(days=1))

    assert listings_payload(storage, profile.name, active=True)["count"] == 1
    assert listings_payload(storage, profile.name, active=False)["count"] == 2
