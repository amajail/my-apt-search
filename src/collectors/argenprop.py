"""Argenprop (https://www.argenprop.com) source adapter.

Implements the frozen `Collector` protocol (src/collectors/base.py). ALL Argenprop
specifics — URL building, paging, HTML/ld+json parsing, the removal signal — live here
and nowhere else (Constitution Principle I & II). The core only ever sees the common
model in src/models.py.

Chosen as the MVP source because MercadoLibre is walled (API 403 PolicyAgent; HTML behind
JS anti-bot) and Zonaprop is behind Cloudflare — see
specs/001-villa-urquiza-monitor/{source-access-blocker,zonaprop-probe,argenprop-probe}.md.
Argenprop is fully server-rendered with no blocking anti-bot, so a pure-`httpx` collector
works on the Azure Functions stack (no headless browser).

Capabilities (argenprop-probe.md): has_api=False, provides_visits=False,
provides_listing_age=False, removal_signal=http_404 (a dead listing URL returns 410 Gone;
the pipeline also detects removal by absence from search results).

Design notes:
- ALL profile matching happens in `search()` so the returned refs are exactly the matching
  set (the pipeline includes every ref verbatim and detects removal by absence). The search
  URL filters venta / N-ambientes / USD / price ceiling / area floor; we additionally
  enforce, on each card, USD (`idmoneda==2`), price <= ceiling, and the **strict** area
  rule `covered_area > min_area_m2` (the URL's `desde-40-m2` is inclusive, so exactly-40
  must be excluded client-side).
- `get_item` maps the detail page (ld+json + the titlebar price). Per the no-partial-lies
  rule (FR-008), any non-200 response (incl. a 410 race) RAISES rather than returning an
  incomplete Listing — so the pipeline skips the diff instead of processing a short set.
- ambientes vs dormitorios gotcha: the card's clean numeric attr is `dormitorios`
  (bedrooms), NOT ambientes. Ambientes is taken from the URL filter (search) and the
  detail-page ld+json `numberOfRooms` (get_item) — never from `dormitorios`.
"""

from __future__ import annotations

import json
import re
from typing import Optional

import httpx

from src.collectors import registry
from src.models import (
    Capabilities,
    Currency,
    Listing,
    ListingRef,
    Operation,
    RemovalSignal,
    SearchProfile,
    Status,
    Visits,
)

BASE_URL = "https://www.argenprop.com"
PROPERTY_TYPE = "departamentos"  # this feature monitors apartments
PAGE_SIZE = 20                   # cards per results page (probe: 20)
MAX_PAGES = 50                   # safety cap on pagination

ARGENPROP_CAPABILITIES = Capabilities(
    has_api=False,
    provides_visits=False,
    provides_listing_age=False,
    removal_signal=RemovalSignal.http_404,
)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9",
}

# Card currency code: idmoneda 2 = USD, 1 = ARS.
_CURRENCY_BY_IDMONEDA = {"2": Currency.USD, "1": Currency.ARS}
_CURRENCY_SLUG = {Currency.USD: "dolares", Currency.ARS: "pesos"}


# --- Pure parsing helpers (unit-tested directly against saved fixtures) -------


def _to_number(raw: Optional[str]) -> Optional[float]:
    """Parse an es-AR number ('1.234,50' or '44' or '49,40') into a float."""
    if not raw:
        return None
    cleaned = raw.strip().replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _attr(block: str, name: str) -> Optional[str]:
    m = re.search(rf'\b{name}="([^"]*)"', block)
    return m.group(1) if m else None


def _card_covered_area(card: str) -> Optional[float]:
    """Covered area (superficie cubierta) from the card's feature span, in m²."""
    m = re.search(
        r'icon-superficie_cubierta"></i>\s*<span>\s*([\d.,]+)\s*m', card, re.S
    )
    return _to_number(m.group(1)) if m else None


def parse_search_page(
    html: str, profile: SearchProfile, *, base_url: str = BASE_URL
) -> list[ListingRef]:
    """Extract matching listing refs from one results page.

    Applies the profile filters that the URL cannot guarantee strictly: currency (USD),
    price ceiling, and covered area strictly greater than `min_area_m2`. Drops any card
    without a canonical url (Principle III).
    """
    refs: list[ListingRef] = []
    starts = [m.start() for m in re.finditer(r'data-item-card="\d+"', html)]
    bounds = starts + [len(html)]
    for i in range(len(starts)):
        # Filter attrs (idmoneda, montonormalizado, area) sit on/inside the card div,
        # AFTER data-item-card. The canonical <a href> WRAPS the card, so it appears
        # just BEFORE data-item-card — search it with a small lookback (id-anchored, so
        # it cannot match a neighbouring card's link).
        card = html[bounds[i] : bounds[i + 1]]
        source_id = _attr(card, "idaviso") or re.search(
            r'data-item-card="(\d+)"', card
        ).group(1)

        # Currency (USD only) — defense-in-depth over the URL filter.
        if _CURRENCY_BY_IDMONEDA.get(_attr(card, "idmoneda")) != profile.currency:
            continue
        # Price ceiling (montonormalizado is in the card currency, already USD here).
        monto = _attr(card, "montonormalizado")
        if monto and int(monto) > profile.price_max:
            continue
        # Covered area STRICTLY greater than the floor (URL's desde-N is inclusive).
        area = _card_covered_area(card)
        if area is not None and area <= profile.min_area_m2:
            continue
        # Canonical url — the href ending in --<source_id> (lookback covers the wrapper).
        region = html[max(0, bounds[i] - 500) : bounds[i + 1]]
        m = re.search(rf'href="(/[^"]*--{re.escape(source_id)})"', region)
        if not m:
            continue  # no canonical link -> never emit (Principle III)
        refs.append(ListingRef(source_id=source_id, url=base_url + m.group(1)))
    return refs


def _extract_ldjson_apartment(html: str) -> Optional[dict]:
    for block in re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S
    ):
        try:
            data = json.loads(block)
        except (ValueError, TypeError):
            continue
        if isinstance(data, dict) and (
            "Apartment" in str(data.get("@type", "")) or "floorSize" in data
        ):
            return data
    return None


def _parse_titlebar_price(html: str) -> tuple[Optional[int], Optional[Currency]]:
    m = re.search(r'<p class="titlebar__price">(.*?)</p>', html, re.S)
    text = re.sub(r"\s+", " ", m.group(1)) if m else ""
    pm = re.search(r"(USD|U\$S|\$)\s*([\d.]+)", text)
    if not pm:
        return None, None
    currency = Currency.USD if pm.group(1) in ("USD", "U$S") else Currency.ARS
    return int(pm.group(2).replace(".", "")), currency


def _parse_antiquity(html: str) -> Optional[int]:
    """Building antiquity (descriptive only — never filters/ranks, Principle IV)."""
    return 0 if re.search(r"A Estrenar", html) else None


def map_listing(detail_html: str, ref: ListingRef, *, source: str = "argenprop") -> Listing:
    """Map a detail page into the common Listing model. Caller guarantees HTTP 200."""
    data = _extract_ldjson_apartment(detail_html)
    if data is None:
        raise ValueError(f"argenprop: no ld+json Apartment block for {ref.url}")
    price, currency = _parse_titlebar_price(detail_html)
    if price is None or currency is None:
        raise ValueError(f"argenprop: could not parse price for {ref.url}")

    rooms = data.get("numberOfRooms")  # ambientes (authoritative), NOT numberOfBedrooms
    area = (data.get("floorSize") or {}).get("value")
    address = data.get("address") or {}
    title = (data.get("name") or "").replace(" - Argenprop", "").strip()

    return Listing(
        source=source,
        source_id=ref.source_id,
        url=ref.url,  # required; carried from the ref (Principle III)
        title=title or address.get("addressRegion") or ref.source_id,
        price=price,
        currency=currency,
        operation=Operation.venta,  # this adapter serves venta profiles
        neighborhood=address.get("addressRegion") or "",
        rooms=int(rooms) if rooms is not None else None,
        area_m2=int(area) if area is not None else None,
        status=Status.active,
        listing_started_at=None,  # not provided -> pipeline ages from first_seen
        description=data.get("description"),
        photo_url=data.get("image"),
        age_years=_parse_antiquity(detail_html),
    )


# --- Collector ---------------------------------------------------------------


class ArgenpropCollector:
    """Collector adapter for Argenprop (CABA apartment listings, scraped via httpx)."""

    def __init__(self, *, http_client=None, base_url: str = BASE_URL) -> None:
        self.name = "argenprop"
        self.capabilities = ARGENPROP_CAPABILITIES
        self._base_url = base_url
        self._http = http_client  # injectable; a real httpx.Client is built lazily

    def _client(self):
        if self._http is None:
            self._http = httpx.Client(
                headers=DEFAULT_HEADERS, timeout=30.0, follow_redirects=True
            )
        return self._http

    def _build_search_url(self, profile: SearchProfile, page: int) -> str:
        barrios = "-o-".join(profile.neighborhoods)
        currency = _CURRENCY_SLUG[profile.currency]
        path = (
            f"/{PROPERTY_TYPE}/{profile.operation.value}/{barrios}"
            f"/{profile.rooms}-ambientes"
            f"/{currency}-hasta-{profile.price_max}"
            f"/desde-{profile.min_area_m2}-m2"
        )
        url = self._base_url + path
        if page > 1:
            url += f"?pagina-{page}"  # note: 'pagina-N', no '='
        return url

    def search(self, profile: SearchProfile) -> list[ListingRef]:
        refs: list[ListingRef] = []
        seen: set[str] = set()
        for page in range(1, MAX_PAGES + 1):
            resp = self._client().get(self._build_search_url(profile, page))
            if resp.status_code != 200:
                if page == 1:
                    # A failed first page is a failed run — raise, never return partial.
                    raise RuntimeError(
                        f"argenprop search failed (page {page}): HTTP {resp.status_code}"
                    )
                break  # past the last page
            for ref in parse_search_page(resp.text, profile, base_url=self._base_url):
                if ref.source_id not in seen:
                    seen.add(ref.source_id)
                    refs.append(ref)
            if resp.text.count('data-item-card="') < PAGE_SIZE:
                break  # last page (fewer than a full page of cards)
        return refs

    def get_item(self, ref: ListingRef) -> Listing:
        resp = self._client().get(ref.url)
        if resp.status_code != 200:
            # 410/404 (gone, rare race) or any other non-200 = incomplete data.
            # Raise so the pipeline skips the diff (FR-008) — no partial-success lies.
            raise RuntimeError(f"argenprop get_item {ref.url}: HTTP {resp.status_code}")
        return map_listing(resp.text, ref)

    def get_visits(self, ref: ListingRef) -> Optional[Visits]:
        return None  # capability off: Argenprop exposes no view counts


registry.register("argenprop", ArgenpropCollector)
