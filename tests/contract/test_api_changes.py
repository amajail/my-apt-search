"""T016 — GET /api/changes payload shape (tested via the pure builder)."""

from __future__ import annotations

from datetime import datetime, timezone

from src.api import changes_payload, listings_payload
from src.pipeline.run import run_profile
from tests.contract.fake_collector import FakeCollector
from tests.fakes import FakeStorage, make_listing, make_profile

DAY1 = datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc)
DAY2 = datetime(2026, 6, 2, 8, 0, tzinfo=timezone.utc)


def _seed_two_days():
    profile = make_profile()
    storage = FakeStorage()
    collector = FakeCollector([make_listing("A", 100000), make_listing("B", 120000)])
    run_profile(profile, collector, storage, DAY1)
    # day 2: B drops price
    collector.set_items([make_listing("A", 100000), make_listing("B", 110000)])
    run_profile(profile, collector, storage, DAY2)
    return profile, storage


def test_changes_payload_shape():
    profile, storage = _seed_two_days()
    payload = changes_payload(storage, profile.name, DAY2)

    assert payload["profile"] == profile.name
    assert payload["since"] == "2026-06-02"
    types = [e["type"] for e in payload["events"]]
    assert types == ["PRICE_CHANGE"]
    e = payload["events"][0]
    assert e["url"].startswith("https://") and e["old_price"] == 120000 and e["new_price"] == 110000
    assert "occurred_at" in e


def test_listings_payload_shape():
    profile, storage = _seed_two_days()
    payload = listings_payload(storage, profile.name)

    assert payload["count"] == 2
    sample = payload["listings"][0]
    for key in ("url", "price", "currency", "days_listed", "visits_total", "is_active"):
        assert key in sample
    assert sample["url"]  # always present
