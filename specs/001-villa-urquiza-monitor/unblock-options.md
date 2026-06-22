# Unblocking the Data Dependency — Options (devC research)

**Date:** 2026-06-07 · **Context:** MercadoLibre (API + scraping) and Zonaprop
(Cloudflare) are both walled on the httpx/Azure-Functions stack. This memo researches how
to regain a listing-data feed. Argenprop is being probed in parallel — **if Argenprop is
httpx-scrapable, it is the cheapest unblock and most of the below is moot.**

## What we already proved

- **ML**: official API 403 (PolicyAgent); public HTML behind JS anti-bot + verification.
- **Zonaprop**: whole site behind Cloudflare managed challenge — homepage, search, internal
  `rplis-api`, AND the sitemaps it advertises in `robots.txt` all return 403
  (`cf-mitigated: challenge`). Only `robots.txt` itself is exempt → **sitemap-discovery
  does NOT unblock Zonaprop.**
- **Sitemaps in general**: free and challenge-exempt only where the host allows it —
  **Argenprop `sitemap.xml` returns real XML (nginx, no challenge)**; ML/Zonaprop do not.

## Options to unblock (ranked for this project: personal, low daily volume, Functions)

### 1. Managed scraping / "web unlocker" API  ⭐ recommended for walled sources
Send the target URL to a third-party API; it solves Cloudflare/anti-bot and returns
rendered HTML/JSON. Called over plain HTTP → **keeps the Azure Functions stack** (no
headless browser in-process). Providers: ZenRows, Scrapfly, ScrapingBee, Bright Data Web
Unlocker, Oxylabs, ScraperAPI; Apify offers ready-made portal "actors".
- **Pros:** robust (ZenRows cites ~99.9% CF success), no infra/arms-race to maintain,
  fits the adapter pattern (swap the httpx client for the unlocker client behind the same
  injectable seam used in T019).
- **Cons:** monthly cost (~US$29–69 entry plans; anti-bot+JS requests burn more credits),
  free tiers (~1k requests) may be tight; a third party sees our traffic; ToS gray area.
- **Cost control:** scrape only the *search-results* pages (cards already carry
  url/price/rooms/area/neighborhood) instead of every detail page → ~5–10 rendered fetches
  per daily run (~150–300/mo), which fits a cheap or free tier.

### 2. Aggregator data source instead of a portal
Use a service that already aggregates Argentine listings as clean data, sidestepping
portal anti-bot entirely. **Properati** (2M+ AR properties; accessible via an Apify actor /
data export). CASAFARI (200M listings, enterprise/$$).
- **Pros:** structured data, no per-portal anti-bot, multi-portal coverage.
- **Cons:** coverage/freshness/neighborhood-granularity unverified; dedup; possible cost;
  is itself a 3rd-party dependency.

### 3. Self-hosted headless browser (Playwright / FlareSolverr)
- **Pros:** no per-request API fee.
- **Cons:** needs an always-on host (FlareSolverr ~500 MB RAM/req) → **breaks the
  Functions-consumption hosting constraint**; fragile vs Cloudflare updates; ongoing
  maintenance. Not recommended for a personal daily job.

### 4. Official MercadoLibre partner / commercial API access
- **Pros:** clean, stable, sanctioned. **Cons:** slow, uncertain, likely not granted to an
  individual; adapter parked meanwhile.

### 5. Just use Argenprop (pending its probe)
If Argenprop serves listings to plain httpx (its sitemap and nginx headers are promising),
**no unblock tooling is needed** — build the Argenprop adapter normally and move on. This
is the preferred outcome.

## Recommendation

1. **Wait for the Argenprop probe.** If FEASIBLE → build that adapter; done (Option 5).
2. If Argenprop also fails, adopt **Option 1 (managed unlocker API)** behind the existing
   injectable-client seam, scraping only search-result pages to stay within a cheap/free
   tier. Keep Functions hosting; no constitution change needed.
3. Treat **Option 2 (Properati aggregator)** as the fallback if per-portal scraping is
   undesirable.
4. Avoid Option 3 (breaks hosting) and Option 4 (too slow) unless strategy changes.

**Decision items for the team:** (a) is paying a small monthly scraping-API fee acceptable?
(b) is third-party-unlocker / scraping ToS risk acceptable for a personal monitor?
(c) does the constitution's "no portal-specific knowledge in core" still hold? — yes: the
unlocker/aggregator lives entirely inside the adapter; the core is untouched.

## References
- Cloudflare bypass landscape: https://www.zenrows.com/blog/bypass-cloudflare ·
  https://scrapeops.io/web-scraping-playbook/how-to-bypass-cloudflare/ ·
  https://scrapfly.io/blog/posts/how-to-bypass-cloudflare-anti-scraping
- Properati / AR data via Apify: https://apify.com/unfenced-group/properati-scraper/api
- Live sitemap/robots probe: this session, 2026-06-07.
