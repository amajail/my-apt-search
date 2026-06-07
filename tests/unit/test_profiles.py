"""US3 (T032) — profile loading: single, all, and the configured example profiles."""

from __future__ import annotations

from src.models import Currency, Operation
from src.profiles import load_all_profiles, load_profile


def test_load_villa_urquiza_profile():
    p = load_profile("villa_urquiza")
    assert p.source == "mercadolibre"
    assert p.operation == Operation.venta and p.currency == Currency.USD
    assert p.rooms == 2 and p.price_max == 115000 and p.min_area_m2 == 40
    assert len(p.neighborhoods) == 3


def test_load_all_profiles_returns_multiple():
    profiles = load_all_profiles()
    names = {p.name for p in profiles}
    assert {"villa_urquiza", "colegiales"} <= names
    # each is independently valid
    assert all(p.price_max > 0 and p.rooms > 0 for p in profiles)
