"""T026 — listings view against real Table Storage (Azurite): aging + visits persist.

Requires Azurite + azure-data-tables. Skipped otherwise.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("azure.data.tables")

from src.api import listings_payload  # noqa: E402
from src.models import Visits  # noqa: E402
from src.pipeline.run import run_profile  # noqa: E402
from src.storage.tables import Storage  # noqa: E402
from tests.contract.fake_collector import FakeCollector  # noqa: E402
from tests.fakes import make_listing, make_profile  # noqa: E402

NOW = datetime(2026, 6, 30, 8, 0, tzinfo=timezone.utc)
pytestmark = pytest.mark.integration


@pytest.fixture()
def storage():
    from azure.core.exceptions import AzureError

    s = Storage("UseDevelopmentStorage=true")
    try:
        s.ensure_tables()
    except (AzureError, OSError) as exc:
        pytest.skip(f"Azurite not reachable: {exc}")
    for tbl in (s._svc.get_table_client("Listings"), s._svc.get_table_client("Changes")):
        for e in tbl.query_entities("PartitionKey eq 't'"):
            tbl.delete_entity(e["PartitionKey"], e["RowKey"])
    return s


def test_listings_view_persists_aging_and_visits(storage):
    profile = make_profile()
    collector = FakeCollector(
        [make_listing("A", 100000, listing_started_at=NOW - timedelta(days=20))],
        visits={"A": Visits(total=333, last7=12, checked_at=NOW)},
    )
    run_profile(profile, collector, storage, NOW)

    item = listings_payload(storage, profile.name)["listings"][0]
    assert item["days_listed"] == 20 and item["visits_total"] == 333
