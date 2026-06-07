"""Azure Functions app — composition root.

This is the ONLY place that imports concrete adapters, so their `registry.register`
calls run. The pipeline and storage never import an adapter (Constitution Principle I).
"""

from __future__ import annotations

import datetime as _dt
import json
import logging

import azure.functions as func

from src.api import changes_payload, listings_payload
from src.config import load_settings
from src.pipeline.run import run_profile_for_source
from src.profiles import load_all_profiles
from src.storage.tables import Storage

# Composition root: import adapters here so they self-register with the registry.
# Uncomment when the MercadoLibre adapter (T021) lands on the feature branch:
# import src.collectors.mercadolibre  # noqa: F401

app = func.FunctionApp()
logger = logging.getLogger(__name__)


@app.timer_trigger(
    schedule="0 0 8 * * *",  # 08:00 UTC daily; cadence configurable
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def daily_monitor(timer: func.TimerRequest) -> None:  # noqa: ARG001
    """T022: run the collect -> diff -> persist pipeline for every profile."""
    for profile in load_all_profiles():
        try:
            result = run_profile_for_source(profile)
            logger.info("daily_monitor %s -> %s", profile.name, result)
        except Exception:  # one bad source must not abort the others
            logger.exception("daily_monitor failed for profile %s", profile.name)


def _storage() -> Storage:
    return Storage(load_settings().storage_connection_string)


@app.route(route="changes", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_changes(req: func.HttpRequest) -> func.HttpResponse:
    """T023: GET /api/changes?profile=<name>&since=<ISO date>."""
    profile = req.params.get("profile")
    if not profile:
        return func.HttpResponse('{"error": "missing profile"}', status_code=400,
                                 mimetype="application/json")
    since_raw = req.params.get("since")
    if since_raw:
        since = _dt.datetime.fromisoformat(since_raw)
    else:
        since = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=1)
    payload = changes_payload(_storage(), profile, since)
    return func.HttpResponse(json.dumps(payload), mimetype="application/json")


@app.route(route="listings", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_listings(req: func.HttpRequest) -> func.HttpResponse:
    """T030 (US2): GET /api/listings?profile=<name>&active=true."""
    profile = req.params.get("profile")
    if not profile:
        return func.HttpResponse('{"error": "missing profile"}', status_code=400,
                                 mimetype="application/json")
    active = req.params.get("active", "true").lower() != "false"
    payload = listings_payload(_storage(), profile, active=active)
    return func.HttpResponse(json.dumps(payload), mimetype="application/json")
