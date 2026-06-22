"""Unit tests for the Zonaprop adapter — driven by saved fixtures, no live calls.

Fixtures were captured from the user's real saved search via curl_cffi (which clears
Zonaprop's Cloudflare challenge): page 1 (30 listings, links to page 2) and page 2 (21
listings, no next page) — 51 total.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.collectors import registry
from src.collectors.base import Collector
from src.collectors.zonaprop import (
    ZonapropCollector,
    extract_preloaded_state,
    parse_page,
)
from src.models import Currency, ListingRef, Operation, SearchProfile, Status

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "zonaprop"
SEARCH_URL = (
    "https://www.zonaprop.com.ar/departamentos-venta-villa-urquiza-saavedra-"
    "villa-pueyrredon-con-balcon-1-habitacion-2-ambientes-mas-40-m2-cubiertos-"
    "hasta-20-anos-menos-115000-dolar-orden-publicado-descendente.html"
)


def _profile(**over) -> SearchProfile:
    base = dict(
        name="villa_urquiza",
        source="zonaprop",
        operation=Operation.venta,
        currency=Currency.USD,
        price_max=115000,
        rooms=2,
        min_area_m2=40,
        neighborhoods=["Villa Urquiza", "Saavedra", "Villa Pueyrredón"],
        search_url=SEARCH_URL,
    )
    base.update(over)
    return SearchProfile(**base)


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeFetcher:
    """Routes get_html(url) to a canned (status, html) by substring match on the URL."""

    def __init__(self, routes: list[tuple[str, tuple[int, str]]], default) -> None:
        self.routes = routes
        self.default = default
        self.calls: list[str] = []

    def get_html(self, url: str) -> tuple[int, str]:
        self.calls.append(url)
        for needle, resp in self.routes:
            if needle in url:
                return resp
        return self.default


def _state_html(postings: list[dict], next_page=None) -> str:
    """Wrap synthetic postings in a minimal __PRELOADED_STATE__ page."""
    state = {
        "listStore": {
            "listPostings": postings,
            "paging": {"pagesUrl": {"nextPage": next_page}},
            "seoStructuredData": {"realEstateListing": {"mainEntity": []}},
        }
    }
    return f"<html><script>window.__PRELOADED_STATE__ = {json.dumps(state)};</script></html>"


def _card(idv, currency_id, amount, covered_area, rooms="2"):
    return {
        "postingId": idv,
        "url": f"/propiedades/clasificado/x-{idv}.html",
        "title": f"Depto {idv}",
        "priceOperationTypes": [
            {
                "operationType": {"name": "Venta", "operationTypeId": "1"},
                "prices": [{"currencyId": currency_id, "amount": amount, "currency": "USD"}],
            }
        ],
        "mainFeatures": {
            "CFT101": {"value": covered_area},
            "CFT1": {"value": rooms},
        },
        "postingLocation": {"location": {"name": "Villa Urquiza"}},
    }


# --- protocol / capabilities -------------------------------------------------


def test_satisfies_collector_protocol():
    assert isinstance(ZonapropCollector(), Collector)


def test_capabilities_declared_honestly():
    c = ZonapropCollector()
    assert c.name == "zonaprop"
    assert c.capabilities.has_api is False
    assert c.capabilities.provides_visits is False
    assert c.capabilities.provides_listing_age is True  # card JSON carries datePosted
    assert c.capabilities.removal_signal.value == "absence"


def test_self_registered_in_registry():
    assert isinstance(registry.get_collector("zonaprop"), ZonapropCollector)


def test_construction_does_no_io():
    fetcher = FakeFetcher(routes=[], default=(200, ""))
    ZonapropCollector(fetcher=fetcher)
    assert fetcher.calls == []


# --- state extraction & page parsing (against the real fixture) --------------


def test_extract_preloaded_state_balances_braces():
    state = extract_preloaded_state(_fixture("search_villa_urquiza.html"))
    assert state is not None
    assert len(state["listStore"]["listPostings"]) == 30


def test_parse_page_maps_real_listings():
    # 30 raw cards -> 26 tracked: 3 are exactly 40 m² (strict floor) and 1 is non-USD.
    listings, next_url = parse_page(_fixture("search_villa_urquiza.html"), _profile())
    assert len(listings) == 26
    for l in listings:
        assert l.source == "zonaprop"
        assert l.source_id.isdigit()
        assert l.url.startswith("https://www.zonaprop.com.ar/")
        assert l.currency == Currency.USD
        assert l.operation == Operation.venta
        assert l.price <= 115000
        assert l.area_m2 is None or l.area_m2 > 40  # strict floor
        assert l.status == Status.active
    # page 1 links to page 2
    assert next_url and next_url.endswith("-pagina-2.html")


def test_parse_page_populates_a_known_listing():
    listings, _ = parse_page(_fixture("search_villa_urquiza.html"), _profile())
    by_id = {l.source_id: l for l in listings}
    l = by_id["59422589"]
    assert l.price == 104800
    assert l.rooms == 2
    assert l.area_m2 == 42  # covered area (CFT101), not total (46)
    assert l.neighborhood == "Villa Urquiza"
    assert l.listing_started_at == datetime(2026, 6, 19, tzinfo=timezone.utc)
    assert l.photo_url and l.photo_url.startswith("https://")
    assert l.title


def test_parse_page_last_page_has_no_next():
    # 21 raw cards -> 17 tracked: 2 are exactly 40 m², 1 non-USD, 1 "precio a consultar".
    listings, next_url = parse_page(_fixture("search_villa_urquiza_page2.html"), _profile())
    assert len(listings) == 17
    assert next_url is None


def test_parse_page_filters_currency_price_and_strict_area():
    postings = [
        _card("111", "1", 90000, "55"),   # ARS -> reject (no USD price)
        _card("222", "2", 130000, "55"),  # USD over ceiling -> reject
        _card("333", "2", 100000, "40"),  # USD but area==40 -> reject (strict >40)
        _card("444", "2", 100000, "41"),  # USD ok -> accept
    ]
    listings, _ = parse_page(_state_html(postings), _profile())
    assert [l.source_id for l in listings] == ["444"]


def test_parse_page_raises_on_missing_state():
    with pytest.raises(ValueError, match="PRELOADED_STATE"):
        parse_page("<html>no state here</html>", _profile())


# --- collector methods with a fake fetcher -----------------------------------


def test_search_follows_pagination_and_dedupes():
    page1 = (200, _fixture("search_villa_urquiza.html"))
    page2 = (200, _fixture("search_villa_urquiza_page2.html"))
    fetcher = FakeFetcher(routes=[("-pagina-2.html", page2)], default=page1)

    refs = ZonapropCollector(fetcher=fetcher).search(_profile())

    assert len(refs) == 43  # 26 + 17 tracked (51 shown; 8 below strict/USD/price filters)
    assert len({r.source_id for r in refs}) == 43
    assert len(fetcher.calls) == 2  # one fetch per page, nothing more
    assert any("-pagina-2.html" in u for u in fetcher.calls)
    assert not any("-pagina-3" in u for u in fetcher.calls)


def test_get_item_uses_cache_with_no_extra_fetch():
    page1 = (200, _fixture("search_villa_urquiza.html"))
    page2 = (200, _fixture("search_villa_urquiza_page2.html"))
    fetcher = FakeFetcher(routes=[("-pagina-2.html", page2)], default=page1)
    collector = ZonapropCollector(fetcher=fetcher)

    refs = collector.search(_profile())
    fetches_after_search = len(fetcher.calls)
    items = [collector.get_item(r) for r in refs]

    assert len(items) == 43
    assert len(fetcher.calls) == fetches_after_search  # get_item did ZERO I/O
    assert all(it.url and it.price for it in items)


def test_search_raises_without_search_url():
    with pytest.raises(ValueError, match="search_url"):
        ZonapropCollector(fetcher=FakeFetcher(routes=[], default=(200, ""))).search(
            _profile(search_url=None)
        )


def test_search_raises_when_first_page_fails():
    fetcher = FakeFetcher(routes=[], default=(503, "boom"))
    with pytest.raises(RuntimeError, match="search failed"):
        ZonapropCollector(fetcher=fetcher).search(_profile())


def test_search_raises_on_cloudflare_challenge():
    fetcher = FakeFetcher(routes=[], default=(200, "<html>Just a moment...</html>"))
    with pytest.raises(RuntimeError, match="challenge"):
        ZonapropCollector(fetcher=fetcher).search(_profile())


def test_get_item_raises_when_not_in_cache():
    collector = ZonapropCollector(fetcher=FakeFetcher(routes=[], default=(200, "")))
    with pytest.raises(RuntimeError, match="not in search cache"):
        collector.get_item(ListingRef(source_id="999", url="https://x/y-999.html"))


def test_get_visits_returns_none():
    ref = ListingRef(source_id="1", url="https://www.zonaprop.com.ar/x-1.html")
    assert ZonapropCollector().get_visits(ref) is None


# --- optional live smoke (skipped unless ZONAPROP_LIVE=1) --------------------


@pytest.mark.skipif(
    os.environ.get("ZONAPROP_LIVE") != "1", reason="set ZONAPROP_LIVE=1 for a live fetch"
)
def test_live_search_returns_listings():
    refs = ZonapropCollector().search(_profile())
    assert len(refs) > 0
    assert all(r.url.startswith("https://www.zonaprop.com.ar/") for r in refs)
