"""Snapshot-vs-stored diff — the heart of the monitor (source-agnostic).

Given the listings seen this run (`current`) and the listings already stored
(`stored`), produce the listings to upsert and the change events to append. Implements
the state machine in specs/001-villa-urquiza-monitor/data-model.md:

    (absent) --seen-->            active                                + NEW
    active   --price differs-->   active                                + PRICE_CHANGE
    active   --absent this run--> removed (is_active=False, removed_at) + REMOVED
    removed  --seen again-->      active                                + RELISTED

Removal threshold is absent-1-run (clarified 2026-06-07). Removal is only meaningful
when this function is reached, i.e. after a SUCCESSFUL collect — the pipeline skips the
diff entirely if the collector failed (FR-008).
"""

from __future__ import annotations

from datetime import datetime

from src.models import ChangeEvent, ChangeType, Listing


def diff(
    current: list[Listing], stored: list[Listing], now: datetime
) -> tuple[list[Listing], list[ChangeEvent]]:
    stored_by = {s.key: s for s in stored}
    current_by = {c.key: c for c in current}

    upserts: list[Listing] = []
    events: list[ChangeEvent] = []

    # Seen this run: NEW / PRICE_CHANGE / RELISTED / unchanged.
    for c in current:
        s = stored_by.get(c.key)
        merged = c.model_copy(deep=True)
        merged.last_seen = now
        merged.is_active = True
        merged.removed_at = None
        merged.missed_runs = 0

        if s is None:
            merged.first_seen = now
            events.append(
                ChangeEvent(
                    type=ChangeType.NEW,
                    source_id=c.source_id,
                    url=c.url,
                    title=c.title,
                    currency=c.currency,
                    new_price=c.price,
                    occurred_at=now,
                )
            )
        else:
            merged.first_seen = s.first_seen or now
            # Preserve enrichment (visits) from prior runs unless this run set it.
            if merged.visits_total is None:
                merged.visits_total = s.visits_total
                merged.visits_last7 = s.visits_last7
                merged.visits_checked_at = s.visits_checked_at

            if not s.is_active:
                events.append(
                    ChangeEvent(
                        type=ChangeType.RELISTED,
                        source_id=c.source_id,
                        url=c.url,
                        title=c.title,
                        currency=c.currency,
                        new_price=c.price,
                        occurred_at=now,
                    )
                )
            elif c.price != s.price and c.currency == s.currency:
                events.append(
                    ChangeEvent(
                        type=ChangeType.PRICE_CHANGE,
                        source_id=c.source_id,
                        url=c.url,
                        title=c.title,
                        currency=c.currency,
                        old_price=s.price,
                        new_price=c.price,
                        occurred_at=now,
                    )
                )

        upserts.append(merged)

    # Stored, active, but absent this run -> REMOVED.
    for s in stored:
        if s.key not in current_by and s.is_active:
            removed = s.model_copy(deep=True)
            removed.is_active = False
            removed.removed_at = now
            events.append(
                ChangeEvent(
                    type=ChangeType.REMOVED,
                    source_id=s.source_id,
                    url=s.url,
                    title=s.title,
                    currency=s.currency,
                    occurred_at=now,
                )
            )
            upserts.append(removed)

    return upserts, events
