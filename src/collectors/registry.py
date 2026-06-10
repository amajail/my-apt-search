"""Source registry: maps a profile's `source` name to its adapter factory.

Adapters self-register at import time, e.g. at the bottom of mercadolibre.py:

    from src.collectors import registry
    registry.register("mercadolibre", MercadoLibreCollector)

The registry never imports an adapter. The composition root (function_app.py) imports
the adapter modules so their registration runs — keeping the pipeline/storage free of
any source import (Constitution Principle I).
"""

from __future__ import annotations

from typing import Callable

from src.collectors.base import Collector

_FACTORIES: dict[str, Callable[[], Collector]] = {}


def register(name: str, factory: Callable[[], Collector]) -> None:
    _FACTORIES[name] = factory


def get_collector(name: str) -> Collector:
    try:
        return _FACTORIES[name]()
    except KeyError:
        raise KeyError(
            f"No collector registered for source '{name}'. "
            f"Registered sources: {sorted(_FACTORIES)}"
        )


def registered_sources() -> list[str]:
    return sorted(_FACTORIES)
