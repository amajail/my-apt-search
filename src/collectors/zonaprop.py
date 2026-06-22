"""Zonaprop (https://www.zonaprop.com.ar) source adapter.

Implements the frozen `Collector` protocol (src/collectors/base.py). ALL Zonaprop
specifics — URL handling, paging, JSON parsing, the removal signal — live here and
nowhere else (Constitution Principle I & II). The core only ever sees the common model
in src/models.py.

Cloudflare note: Zonaprop sits behind a Cloudflare *managed challenge* (the homepage,
search, and the internal rplis-api all return 403 `cf-mitigated: challenge` to a plain
httpx GET). The challenge is defeated WITHOUT a headless browser by impersonating a real
browser's TLS/HTTP-2 fingerprint via `curl_cffi` (probed 2026-06-21: `impersonate=
"chrome124"` returns HTTP 200 with the full server-rendered page). Because a browser TLS
fingerprint can't be produced on the Azure Functions consumption plan reliably, this
adapter is intended to run from a LOCAL scheduled job (see scripts/run_daily.py), not the
Functions timer. The fetcher is injectable, so the bypass tool can be swapped (e.g. a
Playwright fallback) without touching the parsing/mapping below.

Data source: the search page embeds the entire result set as JSON in
`window.__PRELOADED_STATE__` -> `listStore.listPostings` (30 cards/page) plus a
`listStore.paging` block with the next-page URL. No per-listing detail fetch is needed —
`search()` parses the FULL Listing for every card and caches it, so `get_item()` does no
I/O. A daily run therefore makes one fetch per result page (~1-2 total for a narrow
search), never one-per-listing.

Capabilities: has_api=False, provides_visits=False, provides_listing_age=True (the card
JSON carries the publication date), removal_signal=absence (we only read search pages; a
listing gone from the next day's results is the removal signal — we never GET a per-listing
URL to read a 404).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

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

logger = logging.getLogger(__name__)

BASE_URL = "https://www.zonaprop.com.ar"
MAX_PAGES = 20  # safety cap on pagination (a narrow search is 1-2 pages)
IMPERSONATE = "chrome124"  # curl_cffi browser-fingerprint profile that clears Cloudflare

ZONAPROP_CAPABILITIES = Capabilities(
    has_api=False,
    provides_visits=False,
    provides_listing_age=True,
    removal_signal=RemovalSignal.absence,
)

# mainFeatures feature ids (stable Zonaprop codes).
_F_COVERED_AREA = "CFT101"  # Superficie cubierta (m²) — the area we filter on
_F_ROOMS = "CFT1"           # Ambientes
_F_ANTIQUITY = "CFT5"       # Antigüedad (building age, years) — descriptive only

# Price currencyId on the card JSON: "2" = USD, "1" = ARS.
_CURRENCY_BY_ID = {"2": Currency.USD, "1": Currency.ARS}


# --- Pure parsing helpers (unit-tested directly against saved fixtures) -------


def extract_preloaded_state(html: str) -> Optional[dict]:
    """Return the parsed ``window.__PRELOADED_STATE__`` object, or None if absent.

    The value is a JS object literal followed by more script; a regex can't bound it,
    so we brace-balance from the first ``{`` (respecting string literals).
    """
    marker = "window.__PRELOADED_STATE__"
    i = html.find(marker)
    if i < 0:
        return None
    i = html.find("{", i)
    if i < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for j in range(i, len(html)):
        c = html[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(html[i : j + 1])
                    except (ValueError, TypeError):
                        return None
    return None


def is_challenge(html: str) -> bool:
    """True if the body is a Cloudflare interstitial rather than the real page."""
    return "Just a moment" in html or "cf-mitigated" in html[:2000]


def _feature_value(posting: dict, feature_id: str) -> Optional[str]:
    feat = (posting.get("mainFeatures") or {}).get(feature_id)
    return feat.get("value") if isinstance(feat, dict) else None


def _to_int(raw) -> Optional[int]:
    if raw is None:
        return None
    try:
        return int(float(str(raw).replace(".", "").replace(",", ".")))
    except (ValueError, TypeError):
        return None


def _usd_venta_price(posting: dict) -> Optional[int]:
    """The Venta price in USD (amount), or None if the posting has no USD sale price."""
    for ot in posting.get("priceOperationTypes") or []:
        op = (ot.get("operationType") or {}).get("name")
        if op != Operation.venta.value.capitalize() and op != "Venta":
            continue
        for price in ot.get("prices") or []:
            if _CURRENCY_BY_ID.get(price.get("currencyId")) == Currency.USD:
                amount = _to_int(price.get("amount"))
                # Drop "precio a consultar" (amount 0/None) — a 0 price is meaningless to a
                # price monitor and would later fire a spurious PRICE_CHANGE.
                if amount and amount > 0:
                    return amount
    return None


def _date_posted_map(state: dict) -> dict[str, str]:
    """postingId -> datePosted string ('M/D/YY'), from the SEO structured-data block."""
    out: dict[str, str] = {}
    try:
        entities = state["listStore"]["seoStructuredData"]["realEstateListing"]["mainEntity"]
    except (KeyError, TypeError):
        return out
    for ent in entities or []:
        url = ent.get("url") or ""
        m = re.search(r"-(\d+)\.html", url)
        if m and ent.get("datePosted"):
            out[m.group(1)] = ent["datePosted"]
    return out


def _parse_date_posted(raw: Optional[str]) -> Optional[datetime]:
    """Parse Zonaprop's 'M/D/YY' publication date into a tz-aware UTC datetime."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%m/%d/%y").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _photo_url(posting: dict) -> Optional[str]:
    pics = (posting.get("visiblePictures") or {}).get("pictures") or []
    if not pics:
        return None
    first = pics[0]
    return first.get("url730x532") or first.get("url")


def _build_listing(
    posting: dict, date_posted: Optional[str], *, base_url: str
) -> Optional[Listing]:
    """Map one raw posting into the common model, or None if it has no canonical url."""
    source_id = str(posting.get("postingId") or "").strip()
    rel_url = posting.get("url")
    if not source_id or not rel_url:
        return None  # Principle III: never emit a url-less listing

    price = _usd_venta_price(posting)
    if price is None:
        return None  # no USD sale price -> not a tracked listing

    location = (posting.get("postingLocation") or {}).get("location") or {}
    title = (posting.get("title") or posting.get("generatedTitle") or "").strip()

    return Listing(
        source="zonaprop",
        source_id=source_id,
        url=base_url + rel_url,
        title=title or source_id,
        price=price,
        currency=Currency.USD,
        operation=Operation.venta,
        neighborhood=location.get("name") or "",
        rooms=_to_int(_feature_value(posting, _F_ROOMS)),
        area_m2=_to_int(_feature_value(posting, _F_COVERED_AREA)),
        status=Status.active,
        listing_started_at=_parse_date_posted(date_posted),
        age_years=_to_int(_feature_value(posting, _F_ANTIQUITY)),
        description=posting.get("descriptionNormalized") or None,
        photo_url=_photo_url(posting),
    )


def parse_page(
    html: str, profile: SearchProfile, *, base_url: str = BASE_URL
) -> tuple[list[Listing], Optional[str]]:
    """Parse one results page -> (matching listings, absolute next-page url or None).

    Applies the profile filters that defend against the URL drifting: USD currency (via
    `_build_listing`), price ceiling, and covered area STRICTLY greater than the floor.
    Raises ValueError if the embedded state is missing (a structural failure, not an
    empty result set) so the caller never treats a broken page as "zero listings".
    """
    state = extract_preloaded_state(html)
    if state is None:
        raise ValueError("zonaprop: no __PRELOADED_STATE__ in page")

    postings = (state.get("listStore") or {}).get("listPostings") or []
    dmap = _date_posted_map(state)

    listings: list[Listing] = []
    for posting in postings:
        listing = _build_listing(
            posting, dmap.get(str(posting.get("postingId") or "")), base_url=base_url
        )
        if listing is None:
            continue
        if listing.price > profile.price_max:
            continue
        # Covered area strictly greater than the floor (URL's 'mas-40-m2' is inclusive).
        if listing.area_m2 is not None and listing.area_m2 <= profile.min_area_m2:
            continue
        listings.append(listing)

    next_rel = (
        ((state.get("listStore") or {}).get("paging") or {}).get("pagesUrl") or {}
    ).get("nextPage")
    next_url = (base_url + next_rel) if next_rel else None
    return listings, next_url


# --- Fetcher (injectable transport that clears Cloudflare) -------------------


class CurlCffiFetcher:
    """Default transport: a `curl_cffi` session impersonating Chrome's TLS fingerprint."""

    def __init__(self, *, impersonate: str = IMPERSONATE, timeout: float = 30.0) -> None:
        self._impersonate = impersonate
        self._timeout = timeout
        self._session = None

    def get_html(self, url: str) -> tuple[int, str]:
        if self._session is None:
            from curl_cffi import requests  # imported lazily; local-run-only dependency

            self._session = requests.Session(impersonate=self._impersonate)
        resp = self._session.get(url, timeout=self._timeout)
        return resp.status_code, resp.text


# --- Collector ---------------------------------------------------------------


class ZonapropCollector:
    """Collector adapter for Zonaprop (CABA apartment listings, via a Cloudflare-clearing
    fetcher). Construction performs NO I/O (the fetcher builds its session lazily)."""

    def __init__(self, *, fetcher=None, base_url: str = BASE_URL) -> None:
        self.name = "zonaprop"
        self.capabilities = ZONAPROP_CAPABILITIES
        self._base_url = base_url
        self._fetcher = fetcher  # injectable; defaults to curl_cffi, built lazily
        self._cache: dict[str, Listing] = {}  # source_id -> Listing, filled by search()

    def _fetch(self) -> CurlCffiFetcher:
        if self._fetcher is None:
            self._fetcher = CurlCffiFetcher()
        return self._fetcher

    def search(self, profile: SearchProfile) -> list[ListingRef]:
        if not profile.search_url:
            raise ValueError(
                f"zonaprop: profile '{profile.name}' has no search_url (required)"
            )

        self._cache = {}
        refs: list[ListingRef] = []
        url: Optional[str] = profile.search_url
        for page in range(1, MAX_PAGES + 1):
            status, html = self._fetch().get_html(url)
            if status != 200 or is_challenge(html):
                # A failed fetch (incl. a Cloudflare block) is a failed run — raise,
                # never return a partial set (FR-008: the pipeline then skips removals).
                raise RuntimeError(
                    f"zonaprop search failed (page {page}, {url}): "
                    f"HTTP {status}{' challenge' if is_challenge(html) else ''}"
                )
            listings, next_url = parse_page(html, profile, base_url=self._base_url)
            for listing in listings:
                if listing.source_id not in self._cache:
                    self._cache[listing.source_id] = listing
                    refs.append(ListingRef(source_id=listing.source_id, url=listing.url))
            if not next_url:
                break
            url = next_url
        else:
            logger.warning("zonaprop: hit MAX_PAGES=%d for %s", MAX_PAGES, profile.name)
        return refs

    def get_item(self, ref: ListingRef) -> Listing:
        """Return the Listing parsed during search(); no network I/O (one fetch/day)."""
        listing = self._cache.get(ref.source_id)
        if listing is None:
            raise RuntimeError(
                f"zonaprop get_item: {ref.source_id} not in search cache "
                "(get_item must follow search in the same run)"
            )
        return listing

    def get_visits(self, ref: ListingRef) -> Optional[Visits]:
        return None  # capability off: Zonaprop exposes no view counts to scraping


registry.register("zonaprop", ZonapropCollector)
