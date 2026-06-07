"""T015 — two-day diff against real Table Storage (Azurite).

Requires: `azurite` running and `azure-data-tables` installed. Skipped otherwise.
Run with:  azurite --silent &  ;  pytest tests/integration -q
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytest.importorskip("azure.data.tables")

from src.pipeline.run import run_profile  # noqa: E402
from src.storage.tables import Storage  # noqa: E402
from tests.contract.fake_collector import FakeCollector  # noqa: E402
from tests.fakes import make_listing, make_profile  # noqa: E402

DAY1 = datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc)
DAY2 = datetime(2026, 6, 2, 8, 0, tzinfo=timezone.utc)

pytestmark = pytest.mark.integration


@pytest.fixture()
def storage():
    from azure.core.exceptions import AzureError

    s = Storage("UseDevelopmentStorage=true")
    try:
        s.ensure_tables()
    except (AzureError, OSError) as exc:  # Azurite not running
        pytest.skip(f"Azurite not reachable: {exc}")
    # clean any prior rows for this profile so the run starts empty
    for tbl in (s._svc.get_table_client("Listings"), s._svc.get_table_client("Changes")):
        for e in tbl.query_entities("PartitionKey eq 't'"):
            tbl.delete_entity(e["PartitionKey"], e["RowKey"])
    return s


def test_two_day_diff_against_azurite(storage):
    profile = make_profile()
    collector = FakeCollector(
        [make_listing("A", 100000), make_listing("B", 120000), make_listing("C", 80000)]
    )
    run_profile(profile, collector, storage, DAY1)

    # day 2: A unchanged, B price drop, C removed, D new
    collector.set_items(
        [make_listing("A", 100000), make_listing("B", 110000), make_listing("D", 95000)]
    )
    run_profile(profile, collector, storage, DAY2)

    events = storage.get_changes_since(profile.name, DAY2)
    by_type = sorted((e.type.value, e.source_id) for e in events)
    assert by_type == [("NEW", "D"), ("PRICE_CHANGE", "B"), ("REMOVED", "C")]

    # idempotent re-run -> no new events
    run_profile(profile, collector, storage, DAY2)
    again = [e for e in storage.get_changes_since(profile.name, DAY2)]
    assert len(again) == len(events)
