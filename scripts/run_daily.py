#!/usr/bin/env python3
"""Local daily runner for the apartment monitor.

Why this exists: the Zonaprop adapter clears Cloudflare with a browser TLS fingerprint
(curl_cffi), which can't run on the Azure Functions consumption plan. So instead of the
Functions timer trigger, the daily snapshot+diff is driven from here — a plain script you
schedule locally.

It reuses the exact source-agnostic wiring the timer used (`run_profile_for_source`): load
each profile, resolve its collector from the registry, run collect -> diff -> persist into
Azure Table Storage. Profiles whose `source` isn't registered (e.g. the MercadoLibre
example) are skipped with a warning rather than crashing the run.

Usage:
    .venv/bin/python scripts/run_daily.py                # run every registered profile
    .venv/bin/python scripts/run_daily.py villa_urquiza  # run named profile(s)

Storage: the daily diff is only meaningful against DURABLE storage. Put a real Azure
Storage connection string in ~/.config/apt-monitor.env as:
    AzureWebJobsStorage="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;..."
This file (chmod 600, outside the repo) is auto-loaded below. Without it the run falls back
to the local Azurite emulator (UseDevelopmentStorage=true), which is fine for tests but
ephemeral — every run would then report all listings as NEW.

Schedule once per day, e.g. add to `crontab -e` (08:00 local):
    0 8 * * * cd /home/amajail/repos/my-apt-search && .venv/bin/python scripts/run_daily.py >> ~/apt-monitor.log 2>&1
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Make `src` importable when run as `python scripts/run_daily.py` (sys.path[0] = scripts/).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load secrets (esp. AzureWebJobsStorage) from ~/.config/apt-monitor.env if present, so both
# cron and interactive runs get durable storage without exporting env vars by hand. Existing
# environment variables win (never override an explicitly-set value).
_ENV_FILE = Path.home() / ".config" / "apt-monitor.env"
if _ENV_FILE.is_file():
    for _line in _ENV_FILE.read_text().splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _key, _val = _line.split("=", 1)
        os.environ.setdefault(_key.strip(), _val.strip().strip('"').strip("'"))

import src.collectors.zonaprop  # noqa: E402,F401  (self-registers "zonaprop")
from src.collectors import registry  # noqa: E402
from src.pipeline.run import run_profile_for_source  # noqa: E402
from src.profiles import load_all_profiles, load_profile  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
# The Azure SDK logs every HTTP request/response at INFO — too noisy for a daily log.
logging.getLogger("azure").setLevel(logging.WARNING)
log = logging.getLogger("run_daily")


def main(argv: list[str]) -> int:
    names = argv[1:]
    profiles = [load_profile(n) for n in names] if names else load_all_profiles()

    registered = set(registry.registered_sources())
    exit_code = 0
    for profile in profiles:
        if profile.source not in registered:
            log.warning(
                "skipping profile '%s': source '%s' is not registered (registered: %s)",
                profile.name,
                profile.source,
                sorted(registered),
            )
            continue
        try:
            result = run_profile_for_source(profile)
            log.info(
                "DONE %s: seen=%d new=%d price_changes=%d removed=%d relisted=%d",
                result.profile,
                result.seen,
                result.new,
                result.price_changes,
                result.removed,
                result.relisted,
            )
        except Exception:  # one bad profile must not abort the others
            log.exception("profile '%s' failed", profile.name)
            exit_code = 1

    # Refresh the static GitHub Pages data (best-effort — never fail the run on export).
    # `git push` afterwards publishes it.
    try:
        from datetime import datetime, timezone

        from export_web import export  # scripts/ is on sys.path[0]

        exported = export([p.name for p in profiles], now=datetime.now(timezone.utc))
        log.info("exported web data for: %s", ", ".join(exported) or "(none)")
    except Exception:
        log.warning("web export failed (run still OK)", exc_info=True)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
