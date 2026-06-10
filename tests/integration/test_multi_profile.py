"""T031 — two profiles are tracked independently in real storage (no cross-contamination)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytest.importorskip("azure.data.tables")

from src.api import changes_payload, listings_payload  # noqa: E402
from src.pipeline.run import run_profile  # noqa: E402
from src.storage.tables import Storage  # noqa: E402
from tests.contract.fake_collector import FakeCollector  # noqa: E402
from tests.fakes import make_listing, make_profile  # noqa: E402

NOW = datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc)
pytestmark = pytest.mark.integration


@pytest.fixture()
def storage():
    from azure.core.exceptions import AzureError

    s = Storage("UseDevelopmentStorage=true")
    try:
        s.ensure_tables()
    except (AzureError, OSError) as exc:
        pytest.skip(f"Azurite not reachable: {exc}")
    for name in ("p1", "p2"):
        for tbl in (s._svc.get_table_client("Listings"), s._svc.get_table_client("Changes")):
            for e in tbl.query_entities(f"PartitionKey eq '{name}'"):
                tbl.delete_entity(e["PartitionKey"], e["RowKey"])
    return s


def test_two_profiles_are_isolated(storage):
    p1 = make_profile("p1")
    p2 = make_profile("p2")

    run_profile(p1, FakeCollector([make_listing("A", 100000), make_listing("B", 120000)]), storage, NOW)
    run_profile(p2, FakeCollector([make_listing("C", 90000)]), storage, NOW)

    assert listings_payload(storage, "p1")["count"] == 2
    assert listings_payload(storage, "p2")["count"] == 1

    p1_ids = {l["source_id"] for l in listings_payload(storage, "p1")["listings"]}
    p2_ids = {l["source_id"] for l in listings_payload(storage, "p2")["listings"]}
    assert p1_ids == {"A", "B"} and p2_ids == {"C"}  # no bleed

    # changes are scoped per profile too
    assert len(changes_payload(storage, "p1", NOW)["events"]) == 2
    assert len(changes_payload(storage, "p2", NOW)["events"]) == 1
