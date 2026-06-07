# Source Probe — Zonaprop (devC)

**Verdict:** 🔴 **NOT FEASIBLE** on the current stack (httpx-only, Azure Functions).
**Date:** 2026-06-07 · **Branch:** `001/devC/source-probe`
**Context:** alternative-source scouting after MercadoLibre was blocked
(see `source-access-blocker.md`). This probe evaluates Zonaprop
(https://www.zonaprop.com.ar).

## TL;DR

Zonaprop sits entirely behind a **Cloudflare managed JS challenge**. Every entry point —
homepage, search-results pages, and the site's internal JSON API — returns
**HTTP 403 with `cf-mitigated: challenge`** and the "Just a moment..." interstitial. A
plain `httpx` request cannot pass it; doing so needs a real browser executing JavaScript
(and a valid `cf_clearance` cookie), which conflicts with the Azure Functions
consumption-plan / httpx-only constraint. Same class of wall as MercadoLibre scraping —
arguably stricter (whole-site Cloudflare, not per-path).

## Evidence (httpx + realistic browser headers, 2026-06-07)

| Request | Result |
|---|---|
| `GET /` (homepage) | **403** · `server: cloudflare` · `cf-ray` present · **`cf-mitigated: challenge`** · 5.9 KB "Just a moment..." |
| `GET /departamentos-venta-villa-urquiza.html` | **403** · same Cloudflare challenge · title "Just a moment..." · no listings |
| `GET /...-2-ambientes.html` | **403** · same |
| `POST /rplis-api/postings` (internal XHR) | **403** · same Cloudflare challenge |
| Warm session (homepage first → `__cf_bm` cookie → retry search) | still **403** · `__cf_bm` does not grant clearance |

Raw evidence saved at `tests/fixtures/zonaprop/cloudflare_challenge_search.html` (the 403
challenge body + response headers). No listing markup (`posting-card` / `__NEXT_DATA__` /
`ld+json`) is present in any response — only the challenge shell.

## Checklist answers

1. **Server-rendered?** — Can't tell; never get past the challenge to see listing HTML.
2. **Anti-bot?** — **Yes, hard.** Cloudflare managed challenge (`cf-mitigated: challenge`)
   on every path. This is the dealbreaker.
3. **Embedded JSON / internal API?** — Site is a JS app with an `rplis-api`, but the API
   is behind the same Cloudflare challenge → 403.
4.–8. (url / source_id / price+currency / rooms / area / neighborhood / removal / age) —
   **Not assessable**: no listing data is reachable.

## Recommendation

**Do not build a Zonaprop adapter on the current stack.** It would require headless-browser
infrastructure (Playwright + stealth, or a Cloudflare-solving service) running off Azure
Functions consumption — the same heavyweight, fragile path rejected for MercadoLibre, plus
an ongoing Cloudflare arms race. Prefer a lighter-protected portal (Argenprop is being
probed in parallel) before committing any scraping infra. If no httpx-scrapable source
exists, the project's source strategy / hosting constraint needs a deliberate rethink at
the spec level.

## References
- Live probe: this session, 2026-06-07. Evidence fixture:
  `tests/fixtures/zonaprop/cloudflare_challenge_search.html`.
- Related: `specs/001-villa-urquiza-monitor/source-access-blocker.md` (MercadoLibre).
