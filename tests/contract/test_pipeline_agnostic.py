"""T012 — the core stays source-agnostic and runs end-to-end via the FakeCollector.

This is the CI guardrail for Constitution Principle I. If anyone makes the pipeline
import a concrete adapter, this test goes red.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.pipeline.run import run_profile
from tests.contract.fake_collector import FakeCollector
from tests.fakes import FakeStorage, make_listing, make_profile

NOW = datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc)
REPO_ROOT = Path(__file__).resolve().parents[2]


def test_pipeline_imports_no_adapter():
    """Importing the pipeline must not import any concrete adapter (Principle I).

    Run in a CLEAN subprocess so a sibling test that legitimately imports an adapter
    can't pollute the check via shared sys.modules.
    """
    code = (
        "import sys; import src.pipeline.run, src.pipeline.diff; "
        "allowed={'src.collectors','src.collectors.base','src.collectors.registry'}; "
        "leaked=[m for m in sys.modules "
        "if m.startswith('src.collectors') and m not in allowed]; "
        "assert not leaked, leaked"
    )
    r = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=str(REPO_ROOT)
    )
    assert r.returncode == 0, r.stderr


def test_fake_collector_drives_full_pipeline():
    profile = make_profile()
    storage = FakeStorage()
    collector = FakeCollector([make_listing("A", 100000), make_listing("B", 120000)])

    result = run_profile(profile, collector, storage, NOW)

    assert result.seen == 2 and result.new == 2
    assert len(storage.query_active_listings(profile.name)) == 2
    assert all(l.url for l in storage.get_listings(profile.name))  # Principle III


def test_run_aborts_on_collector_failure_no_removals():
    """FR-008: a failed fetch must not remove healthy listings."""
    profile = make_profile()
    storage = FakeStorage()

    # Seed one active listing from a good run.
    run_profile(profile, FakeCollector([make_listing("A", 100000)]), storage, NOW)
    assert len(storage.query_active_listings(profile.name)) == 1
    changes_before = len(storage.changes.get(profile.name, []))

    class FailingCollector(FakeCollector):
        def search(self, profile):  # noqa: ARG002
            raise RuntimeError("source down")

    with pytest.raises(RuntimeError):
        run_profile(profile, FailingCollector([]), storage, NOW)

    # The previously-active listing is untouched — no false REMOVED, no new events.
    assert len(storage.query_active_listings(profile.name)) == 1
    assert len(storage.changes.get(profile.name, [])) == changes_before
