"""Unit tests for the Argenprop adapter — driven by saved fixtures, no live calls."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.collectors import registry
from src.collectors.base import Collector
from src.collectors.argenprop import (
    ArgenpropCollector,
    map_listing,
    parse_search_page,
)
from src.models import Currency, ListingRef, Operation, SearchProfile, Status

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "argenprop"


def _profile(**over) -> SearchProfile:
    base = dict(
        name="villa_urquiza",
        source="argenprop",
        operation=Operation.venta,
        currency=Currency.USD,
        price_max=115000,
        rooms=2,
        min_area_m2=40,
        neighborhoods=["villa-urquiza", "villa-ortuzar", "coghlan"],
    )
    base.update(over)
    return SearchProfile(**base)


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeResp:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text


class FakeClient:
    """Routes a GET to a canned response by substring match on the URL."""

    def __init__(self, routes: list[tuple[str, FakeResp]], default: FakeResp) -> None:
        self.routes = routes
        self.default = default
        self.calls: list[str] = []

    def get(self, url: str) -> FakeResp:
        self.calls.append(url)
        for needle, resp in self.routes:
            if needle in url:
                return resp
        return self.default


# --- protocol / capabilities -------------------------------------------------


def test_satisfies_collector_protocol():
    assert isinstance(ArgenpropCollector(), Collector)


def test_capabilities_declared_honestly():
    c = ArgenpropCollector()
    assert c.name == "argenprop"
    assert c.capabilities.has_api is False
    assert c.capabilities.provides_visits is False
    assert c.capabilities.provides_listing_age is False
    assert c.capabilities.removal_signal.value == "http_404"


def test_self_registered_in_registry():
    got = registry.get_collector("argenprop")
    assert isinstance(got, ArgenpropCollector)


# --- search URL building -----------------------------------------------------


def test_build_search_url_encodes_all_criteria():
    url = ArgenpropCollector()._build_search_url(_profile(), 1)
    assert url == (
        "https://www.argenprop.com/departamentos/venta/"
        "villa-urquiza-o-villa-ortuzar-o-coghlan/2-ambientes/"
        "dolares-hasta-115000/desde-40-m2"
    )
    assert ArgenpropCollector()._build_search_url(_profile(), 3).endswith("?pagina-3")


# --- search-page parsing (against the real fixture) --------------------------


def test_parse_search_page_returns_matching_refs():
    refs = parse_search_page(_fixture("search_filtered_full_criteria.html"), _profile())
    assert len(refs) > 0
    for r in refs:
        assert r.source_id.isdigit()
        assert r.url.startswith("https://www.argenprop.com/")
        assert r.url.endswith(f"--{r.source_id}")  # canonical, id-suffixed


def test_parse_search_page_filters_currency_price_and_strict_area():
    # Three synthetic cards: ARS (reject), USD over price (reject), USD area==40 (reject,
    # strict >40), USD ok (accept).
    def card(idv, idmoneda, monto, area):
        return (
            f'<div data-item-card="{idv}" data-track-aviso idaviso="{idv}" '
            f'idmoneda="{idmoneda}" montonormalizado="{monto}">'
            f'<li><i class="basico1-icon-superficie_cubierta"></i><span>{area} m&#xB2; cubie.</span></li>'
            f'<a href="/departamento-en-venta--{idv}">x</a></div>'
        )
    html = (
        card("111", "1", "90000", "55")     # ARS -> reject
        + card("222", "2", "130000", "55")  # USD over ceiling -> reject
        + card("333", "2", "100000", "40")  # USD but area==40 -> reject (strict >40)
        + card("444", "2", "100000", "41")  # USD, ok -> accept
    )
    refs = parse_search_page(html, _profile())
    assert [r.source_id for r in refs] == ["444"]


# --- detail mapping (against the real fixture) -------------------------------


def test_map_listing_populates_the_model():
    ref = ListingRef(
        source_id="16847795",
        url="https://www.argenprop.com/departamento-en-venta-en-villa-urquiza-2-ambientes--16847795",
    )
    listing = map_listing(_fixture("detail_16847795.html"), ref)

    assert listing.url == ref.url and listing.url  # required, non-empty
    assert listing.source == "argenprop"
    assert listing.source_id == "16847795"
    assert listing.price == 132000
    assert listing.currency == Currency.USD
    assert listing.operation == Operation.venta
    assert listing.rooms == 2          # numberOfRooms = ambientes (not dormitorios=1)
    assert listing.area_m2 == 45       # ld+json floorSize
    assert listing.neighborhood == "Villa Urquiza"
    assert listing.status == Status.active
    assert listing.listing_started_at is None  # not provided -> first_seen aging
    assert listing.photo_url and listing.photo_url.startswith("https://")
    assert listing.title


# --- collector methods with a fake client ------------------------------------


def test_search_pages_and_stops_at_short_page():
    page1 = FakeResp(200, _fixture("search_filtered_full_criteria.html"))  # 20 cards
    empty = FakeResp(200, "<html>0 resultados</html>")
    client = FakeClient(routes=[("pagina-2", empty)], default=page1)

    refs = ArgenpropCollector(http_client=client).search(_profile())

    assert len(refs) > 0
    assert any("pagina-2" in u for u in client.calls)      # paged past page 1
    assert not any("pagina-3" in u for u in client.calls)  # stopped after the empty page


def test_search_raises_when_first_page_fails():
    client = FakeClient(routes=[], default=FakeResp(503, "boom"))
    with pytest.raises(RuntimeError, match="search failed"):
        ArgenpropCollector(http_client=client).search(_profile())


def test_get_item_raises_on_gone_listing():
    ref = ListingRef(source_id="10000001", url="https://www.argenprop.com/x--10000001")
    client = FakeClient(routes=[], default=FakeResp(410, _fixture("removal_410_gone.html")))
    with pytest.raises(RuntimeError, match="HTTP 410"):
        ArgenpropCollector(http_client=client).get_item(ref)


def test_get_item_maps_on_200():
    ref = ListingRef(
        source_id="16847795",
        url="https://www.argenprop.com/departamento-en-venta-en-villa-urquiza-2-ambientes--16847795",
    )
    client = FakeClient(routes=[], default=FakeResp(200, _fixture("detail_16847795.html")))
    listing = ArgenpropCollector(http_client=client).get_item(ref)
    assert listing.price == 132000 and listing.rooms == 2


def test_get_visits_returns_none():
    ref = ListingRef(source_id="1", url="https://www.argenprop.com/x--1")
    assert ArgenpropCollector().get_visits(ref) is None


# --- optional live smoke (skipped unless ARGENPROP_LIVE=1) --------------------


@pytest.mark.skipif(
    os.environ.get("ARGENPROP_LIVE") != "1",
    reason="live smoke: set ARGENPROP_LIVE=1 to hit the real site",
)
def test_live_search_and_get_item_smoke():
    import time

    import httpx

    from src.collectors.argenprop import DEFAULT_HEADERS, map_listing

    profile = _profile()
    collector = ArgenpropCollector()
    with httpx.Client(headers=DEFAULT_HEADERS, timeout=30, follow_redirects=True) as h:
        page1 = h.get(collector._build_search_url(profile, 1))
        assert page1.status_code == 200
        refs = parse_search_page(page1.text, profile)
        assert refs, "expected at least one matching listing"
        time.sleep(2)  # polite
        detail = h.get(refs[0].url)
        assert detail.status_code == 200
        listing = map_listing(detail.text, refs[0])
        assert listing.url and listing.price > 0
        assert listing.currency == Currency.USD and listing.rooms == 2
        assert listing.area_m2 is None or listing.area_m2 > 40
