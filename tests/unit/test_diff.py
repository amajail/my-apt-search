"""T014 — diff unit tests: NEW / PRICE_CHANGE / REMOVED / RELISTED + idempotency."""

from __future__ import annotations

from datetime import datetime, timezone

from src.models import ChangeType
from src.pipeline.diff import diff
from tests.fakes import make_listing

DAY1 = datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc)
DAY2 = datetime(2026, 6, 2, 8, 0, tzinfo=timezone.utc)


def _persist(upserts):
    """Simulate storage: return the upserted listings as the next run's stored set."""
    return {l.key: l for l in upserts}


def test_new_listing_emits_new():
    upserts, events = diff([make_listing("A", 100000)], [], DAY1)
    assert [e.type for e in events] == [ChangeType.NEW]
    assert upserts[0].first_seen == DAY1 and upserts[0].is_active


def test_price_change_emits_old_and_new():
    stored = list(_persist(diff([make_listing("A", 100000)], [], DAY1)[0]).values())
    upserts, events = diff([make_listing("A", 90000)], stored, DAY2)
    assert [e.type for e in events] == [ChangeType.PRICE_CHANGE]
    assert events[0].old_price == 100000 and events[0].new_price == 90000
    assert upserts[0].first_seen == DAY1  # preserved


def test_absent_listing_emits_removed():
    stored = list(_persist(diff([make_listing("A", 100000)], [], DAY1)[0]).values())
    upserts, events = diff([], stored, DAY2)
    assert [e.type for e in events] == [ChangeType.REMOVED]
    assert upserts[0].is_active is False and upserts[0].removed_at == DAY2


def test_relisted_after_removal():
    after_new = _persist(diff([make_listing("A", 100000)], [], DAY1)[0])
    after_removed = _persist(diff([], list(after_new.values()), DAY2)[0])
    upserts, events = diff([make_listing("A", 100000)], list(after_removed.values()), DAY2)
    assert [e.type for e in events] == [ChangeType.RELISTED]
    assert upserts[0].is_active is True and upserts[0].removed_at is None


def test_rerun_is_idempotent():
    stored = list(_persist(diff([make_listing("A", 100000)], [], DAY1)[0]).values())
    _, events = diff([make_listing("A", 100000)], stored, DAY2)
    assert events == []  # nothing changed -> no events


def test_two_day_mixed_changes():
    day1 = [make_listing("A", 100000), make_listing("B", 120000), make_listing("C", 80000)]
    stored = list(_persist(diff(day1, [], DAY1)[0]).values())
    # day2: A unchanged, B price drop, C removed, D new
    day2 = [make_listing("A", 100000), make_listing("B", 110000), make_listing("D", 95000)]
    _, events = diff(day2, stored, DAY2)
    by_type = sorted((e.type.value, e.source_id) for e in events)
    assert by_type == [("NEW", "D"), ("PRICE_CHANGE", "B"), ("REMOVED", "C")]
