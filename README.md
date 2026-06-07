# my-apt-search

A personal apartment search aggregator. It pulls listings from multiple sources
into one place, then filters and ranks them against my own criteria — so I stop
juggling a dozen browser tabs and a spreadsheet.

> **Status:** concept / idea stage. This doc captures the idea before any code.

## The problem

Apartment hunting means checking many sites, each with its own search UI,
filters, and quirks. The same listing shows up in several places, important
ones get buried, and there's no single ranked view of "the places actually
worth my time." Comparing options across sites is manual and tedious.

## The idea

One tool that:

1. **Aggregates** listings from several sources into a single normalized list.
2. **Deduplicates** the same apartment appearing across multiple sources.
3. **Filters** by my hard requirements (budget, location, size, etc.).
4. **Ranks** what's left by how well it fits my preferences.
5. **Surfaces** the results in one view I can scan quickly.

## Goals

- See all relevant listings in one place, normalized to a common shape.
- Spend less time searching, more time on the few listings that matter.
- Make it easy to tweak criteria and re-rank without redoing the search.

## Non-goals (for now)

- Not a public product — just for personal use.
- Not trying to cover every site on day one; start with a couple of sources.
- No booking/contacting landlords through the tool; it just finds and ranks.

## How it might work (rough sketch)

```
 ┌──────────┐   ┌──────────┐   ┌──────────┐
 │ Source A │   │ Source B │   │ Source C │   ← listing sources
 └────┬─────┘   └────┬─────┘   └────┬─────┘
      └──────────────┼──────────────┘
                     ▼
              ┌─────────────┐
              │  Collector  │  fetch / scrape, normalize to common shape
              └──────┬──────┘
                     ▼
              ┌─────────────┐
              │  Dedupe     │  merge the same apartment across sources
              └──────┬──────┘
                     ▼
              ┌─────────────┐
              │ Filter+Rank │  drop misses, score the rest by my preferences
              └──────┬──────┘
                     ▼
              ┌─────────────┐
              │  Output     │  ranked list (CLI table / file / simple page)
              └─────────────┘
```

## My criteria (to fill in)

**Hard filters** (must match):
- Budget: _max rent_
- Location / neighborhoods: _..._
- Size: _bedrooms / m²_
- _Other deal-breakers (pets, furnished, move-in date, ...)_

**Soft preferences** (used for ranking, weighted):
- _e.g. closer to transit = better_
- _e.g. lower price within budget = better_
- _e.g. more natural light / floor / outdoor space_

## Open questions

- Which sources to start with, and do they have APIs or need scraping?
- How to reliably detect duplicate listings across sources?
- Where does it run — one-off script, scheduled job, small local app?
- How are results presented — terminal table, a file, or a small web page?
- (Later) Do I want alerts when new matching listings appear?

## Possible first step

A single script that fetches from **one** source, normalizes the listings,
applies the hard filters, and prints a ranked list. Add a second source once
the shape feels right.
