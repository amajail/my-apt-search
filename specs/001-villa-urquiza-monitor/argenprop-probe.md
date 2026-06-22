# Argenprop source feasibility probe

**Date:** 2026-06-07 · **Branch:** `001/devC/source-probe` · **Source:** https://www.argenprop.com
**Scope:** feasibility probe only — fixtures + memo. No production adapter; frozen core
files (`models.py`, `collectors/base.py`, `registry.py`, pipeline, storage) untouched.

> Context: this probe exists because MercadoLibre is walled — its API returns 403
> `PolicyAgent` even with a valid token (see memory `mercadolibre-api-policyagent-block`),
> and the referenced `source-access-blocker.md` was not present in the tree. Argenprop is
> the candidate replacement source.

## VERDICT: ✅ FEASIBLE

Argenprop is fully **server-rendered**, has **no blocking anti-bot wall**, exposes
**machine-readable data attributes per card** plus **ld+json on detail pages**, and lets
**every profile criterion be expressed in the URL**. A pure-`httpx` collector (no headless
browser) is viable on Azure Functions. **Recommendation: build the Argenprop adapter.**

---

## Method

Polite, low-volume `httpx` GETs with a realistic Chrome User-Agent and `Accept-Language:
es-AR`, 2–3 s between requests, ~12 requests total. Raw responses saved as fixtures under
`tests/fixtures/argenprop/`.

---

## Checklist answers (with evidence)

### 1. Server-rendered? — ✅ YES

Plain `httpx` GET of a search page returns all listings in the HTML, no JS needed.

```
GET https://www.argenprop.com/departamentos/venta/villa-urquiza
→ 200 · 666 KB · text/html · server: nginx/1.27.4 (ASP.NET Core MVC)
→ <title>3.032 Departamentos en Venta en Villa Urquiza, Capital Federal</title>
→ 20 listing cards present in HTML (data-item-card="…")
```
Fixture: `search_villa_urquiza.html`. No headless browser required → meets the
`httpx`-only constraint.

### 2. Anti-bot? — ✅ NONE blocking

- No Cloudflare (no `cf-ray` header), no DataDome, no "verify you're human" interstitial.
- Every request returned **200** with full listing data on the first try.
- `captcha` hits in source = Google reCAPTCHA **only on the register popup** (and the
  hidden enterprise badge) — not a gate on listing data.
- `cloudflare` hits = the Leaflet map's `cdnjs.cloudflare.com` asset CDN. `robot` = the
  `<meta name="robots" content="index,follow">` tag + the Roboto font. All benign.

### 3. Embedded structured data? — ✅ YES (two layers)

**Results page** — each card carries a `data-track-aviso` attribute block with clean,
typed fields (no HTML parsing needed for the core numbers):

```
idaviso="16847795"        # → source_id (matches trailing --<id> in the URL)
idtipooperacion="1"       # 1 = venta
idmoneda="2"              # 2 = USD (confirmed), 1 = ARS
montonormalizado="132000" # price as a clean integer
dormitorios="1"           # BEDROOMS (see risk: ≠ ambientes)
idbarrio="39"             # 39 = Villa Urquiza
idlocalidad / idpartido / idprovincia …
```

**Detail page** — `application/ld+json` (`@type: Apartment`), e.g. fixture
`detail_16847795_ldjson.json`:

```json
{ "@type":"Apartment", "numberOfRooms":2, "numberOfBedrooms":1,
  "floorSize":{"value":45,"unitCode":"MTK"},
  "address":{"addressRegion":"Villa Urquiza","streetAddress":"Pacheco al 2900",
             "addressLocality":"Capital Federal, Argentina"} }
```
`numberOfRooms` = **ambientes** (the profile's `rooms`); `numberOfBedrooms` = dormitorios.
No `__NEXT_DATA__` / `__PRELOADED_STATE__`.

### 4. Stable url + source_id — ✅ YES

- **source_id** = `idaviso` (e.g. `16847795`), also the integer after `--` in the URL.
- **url** = canonical `https://www.argenprop.com/departamento-en-venta-en-villa-urquiza-2-ambientes--16847795`.
  Stable across the price-change/relisting lifecycle (id-suffixed). Satisfies Principle III.

### 5. Per-listing fields — ✅ all reachable

| Field | Results page | Detail page | Notes |
|---|---|---|---|
| price | ✅ `montonormalizado` (int) / `card__price` "USD 210.000" | ✅ ld+json desc | clean int on card |
| currency | ✅ `idmoneda` (2=USD) / `card__currency` "USD" | ✅ | **USD distinguishable**; ARS=1 |
| ambientes (rooms) | ⚠️ slug/title only (`…-2-ambientes--…`) | ✅ ld+json `numberOfRooms` | card `ambientes` attr is empty |
| covered area m² | ✅ `card__main-features` "72 m² cubie." (text) | ✅ ld+json `floorSize.value` (int) | card text uses decimal comma |
| neighborhood | ✅ `idbarrio` + slug | ✅ ld+json `addressRegion` | |
| title / address / photo | ✅ | ✅ | |
| antiquity (age_years) | ✅ "A Estrenar / 6 años / 11 años" | ✅ | **building** age, not listing age (see #8) |

USD vs ARS is unambiguous: `idmoneda` (2 vs 1), the `card__currency` text, and the
`monedadestino=dolares` URL filter all agree.

### 6. Filterable search URL — ✅ YES, every criterion in the URL

Confirmed by probing — all criteria expressible as path segments:

```
https://www.argenprop.com/departamentos/venta/
    villa-urquiza-o-villa-ortuzar-o-coghlan   # multi-barrio, "-o-" join (normalized alpha)
    /2-ambientes                              # exact ambientes
    /dolares-hasta-115000                     # currency (USD) + price ceiling, combined
    /desde-40-m2                              # covered-area floor
?pagina-2                                     # pagination (note: "pagina-N", no "=")
```
Verified result:
```
→ 200 · "270 Departamentos en Venta desde 40 m2 hasta USD 115.000 de 2 ambientes
         en Coghlan, Villa Ortuzar, Villa Urquiza"
→ 20/20 cards idmoneda=2 (USD), monto_range (79000, 115000), all slugs "…-2-ambientes-…"
```
Fixture: `search_filtered_full_criteria.html`.

Caveats:
- The price filter is a **path segment**, not a query param (`?PrecioHasta=115000` → 404;
  `/dolares-hasta-115000` → 200). Currency-only as query works (`?monedadestino=dolares`).
- `desde-40-m2` is **inclusive** (≥40); the profile wants strictly **>40** → enforce the
  `area_m2 == 40` exclusion client-side.
- Still validate `idmoneda == 2` client-side as defense-in-depth.

### 7. Removal / status signal — ✅ HTTP 410 Gone (per-URL)

A non-existent listing id returns a clean error status, not a redirect or a silent
disappearance:
```
GET …/departamento-en-venta-en-villa-urquiza--10000001 → 410  (title "Error 410")
```
Fixture: `removal_410_gone.html` (the signal is the **status code**, not the styled body).
Maps to `RemovalSignal.http_404` (the enum's "listing URL returns not-found" — 410 is the
same per-URL gone signal). Absence-from-results is available as a backstop.

### 8. Listing age — ❌ NOT provided

No publication date anywhere: no "publicado hace X días" on results or detail, no
`datePosted`/`datePublished` in ld+json. The visible "A Estrenar / 6 años / 11 años" is
**building antiquity** (→ `age_years`, a descriptive extra), not listing age. Therefore
`provides_listing_age = False`; aging falls back to `first_seen` (Principle II graceful
degradation).

Also note: **no view counts** (`visualizaciones` / `visitas`) on results or detail →
`provides_visits = False`.

---

## Proposed Capabilities

```python
Capabilities(
    has_api=False,               # HTML scraping; no public API (internal /listing/* form
                                 #   endpoints exist but are unnecessary)
    provides_visits=False,       # no view counts anywhere
    provides_listing_age=False,  # no publication date; age_years is building antiquity only
    removal_signal=RemovalSignal.http_404,  # dead listing URL → 410 Gone
)
```

---

## Sketch — how the adapter would map (NOT built this turn)

`search(profile) -> list[ListingRef]`
1. Build the canonical URL from the profile:
   `…/departamentos/{operation}/{barrios joined by "-o-"}/{rooms}-ambientes/dolares-hasta-{price_max}/desde-{min_area}-m2`
   (needs a barrio-slug map: Villa Urquiza / Villa Ortúzar / Coghlan → slug + `idbarrio`).
2. GET each page (`?pagina-N`) until a page yields < page-size cards.
3. For each `data-track-aviso` card → `ListingRef(source_id=idaviso, url=<absolute slug href>)`.
   Pre-filter on the cheap card attrs (`idmoneda==2`, `montonormalizado<=price_max`).

`get_item(ref) -> Listing`
1. GET `ref.url`. **410 → status=closed / drop** (removal signal).
2. Parse the `application/ld+json` Apartment block:
   - `price`/`currency` ← card `montonormalizado`/`idmoneda` (carry from search) — ld+json
     here omits price, so price must come from the card or the detail price node.
   - `rooms` ← `numberOfRooms` (**ambientes** — authoritative), enforce `== profile.rooms`.
   - `area_m2` ← `floorSize.value`, enforce `> profile.min_area_m2` (strict).
   - `neighborhood` ← `address.addressRegion`; `title`/`description`/`photo_url` from page.
   - `age_years` ← antiquity text (descriptive only — never filter/rank, Principle IV).
   - `listing_started_at` ← None (not available) → pipeline uses `first_seen`.
3. Drop any listing without a canonical url (Principle III).

`get_visits(ref) -> None`  (capability off).

### Fields missing / hard to get
- **Listing publication date** — absent (aging via `first_seen`).
- **View counts** — absent.
- **ambientes on the results page** — only in the slug/title; the clean numeric is
  `numberOfRooms` on the detail page. The URL filter already restricts the search set to
  `2-ambientes`, so `search()` is safe; `get_item()` re-confirms via ld+json.

---

## Risks

1. **ambientes vs dormitorios.** The card's clean numeric attr is `dormitorios` (bedrooms),
   *not* ambientes; `ambientes` attr is empty. Read ambientes from the slug/`numberOfRooms`,
   never from `dormitorios`. (Pipeline correctness risk if confused.)
2. **No API contract / HTML churn.** Field positions can change without notice. Mitigate by
   pinning the saved fixtures and unit-testing the mapping.
3. **reCAPTCHA Enterprise badge is sitewide.** Low volume kept us at 200 throughout; a daily
   snapshot is well within polite limits, but high request rates could trigger a challenge.
   Keep volume low, UA realistic, add delays.
4. **Inclusive area filter / currency-coupled price filter.** `desde-40-m2` is ≥40 and the
   price ceiling is fused with `dolares`; enforce strict `>40` and re-check `idmoneda==2`
   client-side.
5. **Unusual pagination param** `?pagina-N` (no `=`). Pin it.
6. **Area text format** on results cards uses a decimal comma + "cubie." label
   ("38,50 m² cubie.") — parse defensively, or prefer the detail ld+json integer.

---

## Fixtures saved (`tests/fixtures/argenprop/`)

| File | What |
|---|---|
| `search_villa_urquiza.html` | unfiltered results page (data-track-aviso cards) |
| `search_filtered_full_criteria.html` | full-criteria canonical search (venta · 3 barrios · 2 amb · USD ≤115k · ≥40 m²) |
| `detail_16847795.html` | one detail page (ld+json source) |
| `detail_16847795_ldjson.json` | extracted ld+json Apartment blob |
| `removal_410_gone.html` | dead-listing response (HTTP 410 signal) |

## Recommendation

**Build the Argenprop adapter.** It clears every hard constraint: server-rendered (no
headless browser), no anti-bot wall on polite traffic, stable per-listing url + source_id,
all profile criteria expressible in the URL, a clean per-URL removal signal (410), and
structured data (card attrs + ld+json) that populates the `Listing` model. The only
unsupported capabilities — listing age and visits — degrade gracefully by design
(Principle II), so they are not blockers. Argenprop is a strong replacement for the walled
MercadoLibre source.
