"""US2 enrich (T028): visits attached where supported; aging from start date or first_seen."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.models import Capabilities, RemovalSignal, Visits
from src.pipeline.run import run_profile
from tests.contract.fake_collector import FakeCollector
from tests.fakes import FakeStorage, make_listing, make_profile

NOW = datetime(2026, 6, 30, 8, 0, tzinfo=timezone.utc)

NO_EXTRAS = Capabilities(
    has_api=False,
    provides_visits=False,
    provides_listing_age=False,
    removal_signal=RemovalSignal.absence,
)


def test_visits_and_aging_populated():
    profile = make_profile()
    storage = FakeStorage()
    started = NOW - timedelta(days=30)
    collector = FakeCollector(
        [make_listing("A", 100000, listing_started_at=started)],
        visits={"A": Visits(total=540, last7=31, checked_at=NOW)},
    )

    run_profile(profile, collector, storage, NOW)

    stored = storage.get_listings(profile.name)[0]
    assert stored.visits_total == 540 and stored.visits_last7 == 31
    assert stored.days_listed == 30  # from source listing_started_at


def test_no_visits_source_nulls_and_ages_from_first_seen():
    profile = make_profile()
    storage = FakeStorage()
    collector = FakeCollector([make_listing("A", 100000)], capabilities=NO_EXTRAS)

    run_profile(profile, collector, storage, NOW)

    stored = storage.get_listings(profile.name)[0]
    assert stored.visits_total is None
    assert stored.days_listed == 0  # first_seen == NOW (fallback anchor)


def test_visits_preserved_when_source_returns_none_later():
    profile = make_profile()
    storage = FakeStorage()
    collector = FakeCollector(
        [make_listing("A", 100000)], visits={"A": Visits(total=100, last7=5, checked_at=NOW)}
    )
    run_profile(profile, collector, storage, NOW)

    # next run: visits not yet refreshed (lag) -> None returned, prior value preserved
    collector._visits = {}
    run_profile(profile, collector, storage, NOW + timedelta(days=1))

    stored = storage.get_listings(profile.name)[0]
    assert stored.visits_total == 100
