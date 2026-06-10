"""T034 — GET /api/profiles payload shape."""

from __future__ import annotations

from src.api import profiles_payload


def test_profiles_payload_sorted():
    assert profiles_payload(["villa_urquiza", "colegiales"]) == {
        "profiles": ["colegiales", "villa_urquiza"]
    }


def test_profiles_payload_empty():
    assert profiles_payload([]) == {"profiles": []}
