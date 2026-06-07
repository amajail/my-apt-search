"""Azure Functions app — composition root.

This is the ONLY place that imports concrete adapters, so their `registry.register`
calls run. The pipeline and storage never import an adapter (Constitution Principle I).

Triggers are skeletons here (Foundational phase); they are implemented in US1/US2/US3:
- daily_monitor  -> T022 (pipeline.run per profile)
- get_changes    -> T023 (GET /api/changes)
- get_listings   -> T030 (GET /api/listings)
"""

from __future__ import annotations

import azure.functions as func

# Composition root: import adapters here so they self-register with the registry.
# Uncomment as adapters land (keeps pipeline/storage free of source imports).
# import src.collectors.mercadolibre  # noqa: F401  (T021)

app = func.FunctionApp()


@app.timer_trigger(
    schedule="0 0 8 * * *",  # 08:00 UTC daily; cadence configurable
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def daily_monitor(timer: func.TimerRequest) -> None:  # noqa: ARG001
    # T022: for each profile, run the collect -> enrich -> diff -> persist pipeline.
    raise NotImplementedError("daily_monitor implemented in T022")


@app.route(route="changes", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_changes(req: func.HttpRequest) -> func.HttpResponse:  # noqa: ARG001
    # T023: read get_changes_since(profile, since) and return the digest JSON.
    return func.HttpResponse("not implemented", status_code=501)


@app.route(route="listings", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_listings(req: func.HttpRequest) -> func.HttpResponse:  # noqa: ARG001
    # T030: read query_active_listings(profile) and return the listings JSON.
    return func.HttpResponse("not implemented", status_code=501)
