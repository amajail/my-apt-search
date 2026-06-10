# Contract — Collector (source adapter port)

The single interface the core depends on. `pipeline/` and `storage/` import **only**
this; they never import an adapter (Constitution Principle I). Each source provides one
implementation, registered by `name`.

## Interface

```python
class Collector(Protocol):
    name: str                      # registry key, e.g. "mercadolibre"
    capabilities: Capabilities     # see data-model.md

    def search(self, profile: SearchProfile) -> list[ListingRef]:
        """Discover listings matching the profile. ListingRef = {source_id, url}."""

    def get_item(self, ref: ListingRef) -> Listing:
        """Fetch + map one listing into the common model. MUST set url; MUST set
        status from the source removal signal where available."""

    def get_visits(self, ref: ListingRef) -> Visits | None:
        """Return view counts, or None if capabilities.provides_visits is False."""
```

## Obligations on every adapter

1. **URL required** — `get_item` MUST populate `Listing.url`; if the source yields no
   canonical link, the adapter MUST drop the listing (never emit a url-less listing).
2. **Declare capabilities** — set `capabilities` honestly; the pipeline branches on them.
3. **Graceful degradation** — unsupported visits/age return `None` / leave fields null;
   MUST NOT raise for a missing optional capability.
4. **Own auth, paging, rate limits, anti-bot** — fully encapsulated; the core passes
   only a `SearchProfile`.
5. **Stable `source_id`** — durable across runs (used in the Listings RowKey).
6. **No partial-success lies** — on a fetch failure that yields an incomplete set,
   raise (so the pipeline skips removal processing) rather than returning a short list.

## Registry

```python
# collectors/registry.py
REGISTRY: dict[str, Callable[[], Collector]] = {
    "mercadolibre": MercadoLibreCollector,
    # "zonaprop": ZonapropCollector,   # added in feature 002 — one line, no core change
}
def get_collector(name: str) -> Collector: ...
```

## Conformance tests (mandatory)

- **Contract test**: a `FakeCollector` returning canned refs/items/visits drives
  `pipeline.run` end-to-end; asserts the pipeline imports no adapter module.
- **Capability-gap test**: a `FakeCollector` with `provides_visits=False` and
  `provides_listing_age=False` produces listings with null visits and `first_seen`-based
  aging, with no errors (pre-validates the Zonaprop shape).
