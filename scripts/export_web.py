#!/usr/bin/env python3
"""Export the monitor's stored data to static JSON for the GitHub Pages site (web/).

GitHub Pages is static and the Azure storage key must never reach the browser, so the data
is pre-rendered HERE (where the connection string already lives, via ~/.config/apt-monitor.env)
into web/data/*.json. The static site (web/index.html) fetches those files; nothing secret is
published. Reuses the exact API response shapes (src/api.py) the HTTP endpoints return.

Writes, for each registered profile:
    web/data/<profile>.json   {generated_at, profile, count, listings:[...], changes:[...]}
and an index:
    web/data/index.json       {generated_at, profiles:[...]}

Usage:
    .venv/bin/python scripts/export_web.py                 # all registered profiles
    .venv/bin/python scripts/export_web.py villa_urquiza   # named profile(s)

Run it after scripts/run_daily.py (which also calls it), then `git push` to publish.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

# Load AzureWebJobsStorage from ~/.config/apt-monitor.env if present (same as run_daily.py),
# so the exporter reads durable cloud storage without manual env exports.
_ENV_FILE = Path.home() / ".config" / "apt-monitor.env"
if _ENV_FILE.is_file():
    for _line in _ENV_FILE.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

import src.collectors.zonaprop  # noqa: E402,F401  (self-registers "zonaprop")
from src.api import changes_payload, listings_payload  # noqa: E402
from src.collectors import registry  # noqa: E402
from src.config import load_settings  # noqa: E402
from src.profiles import load_all_profiles, load_profile  # noqa: E402
from src.storage.tables import Storage  # noqa: E402

log = logging.getLogger("export_web")

DATA_DIR = _REPO_ROOT / "web" / "data"
CHANGES_WINDOW_DAYS = 30


def export(profile_names: list[str], *, now: datetime) -> list[str]:
    """Write web/data/<profile>.json + index.json. Returns the profiles exported."""
    settings = load_settings()
    storage = Storage(settings.storage_connection_string)
    storage.ensure_tables()

    profiles = (
        [load_profile(n) for n in profile_names] if profile_names else load_all_profiles()
    )
    registered = set(registry.registered_sources())
    since = now - timedelta(days=CHANGES_WINDOW_DAYS)
    generated_at = now.isoformat()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    exported: list[str] = []
    for profile in profiles:
        if profile.source not in registered:
            log.warning("skipping '%s': source '%s' not registered", profile.name, profile.source)
            continue
        listings = listings_payload(storage, profile.name, active=True)
        changes = changes_payload(storage, profile.name, since)
        doc = {
            "generated_at": generated_at,
            "profile": profile.name,
            "source": profile.source,
            "search_url": profile.search_url,
            "count": listings["count"],
            "listings": listings["listings"],
            "changes": changes["events"],
        }
        (DATA_DIR / f"{profile.name}.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        exported.append(profile.name)
        log.info("wrote web/data/%s.json (%d listings, %d changes)",
                 profile.name, doc["count"], len(doc["changes"]))

    (DATA_DIR / "index.json").write_text(
        json.dumps({"generated_at": generated_at, "profiles": exported}, indent=2),
        encoding="utf-8",
    )
    return exported


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("azure").setLevel(logging.WARNING)
    exported = export(argv[1:], now=datetime.now(timezone.utc))
    if not exported:
        log.error("no profiles exported")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
