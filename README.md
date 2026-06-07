# my-apt-search

A personal, Azure-hosted backend that **monitors apartment listings over time** and
reports daily what changed — new listings, price changes, removals — plus listing
aging and view counts. It is **not** a search-ranking tool.

The design is layered so the **core is data-source agnostic**: each portal is an
independent, swappable adapter. MercadoLibre is the first source; Zonaprop follows.

> **Status:** design stage. Documentation only — no implementation yet.

## Documentation

| Doc | Scope |
|-----|-------|
| [docs/BUSINESS.md](docs/BUSINESS.md) | Purpose, what it tracks, search profiles, requirements |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Source-agnostic core + the Source Adapter Contract |
| [docs/sources/mercadolibre.md](docs/sources/mercadolibre.md) | MercadoLibre adapter (#1) |
| [docs/sources/zonaprop.md](docs/sources/zonaprop.md) | Zonaprop adapter (#2) |

## Build order

1. **Agnostic core** — common model, `Collector` interface, registry, diff, Table
   Storage, timer + HTTP triggers. Proven with a fake in-memory adapter.
2. **MercadoLibre adapter** — API-based: search, item, visits, OAuth.
3. **Zonaprop adapter** — scraped: search/detail parsing, removal via 404/absence.
