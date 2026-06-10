"""Load search profiles from YAML files under src/profiles/."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.models import SearchProfile

PROFILES_DIR = Path(__file__).parent / "profiles"


def load_profile(name: str) -> SearchProfile:
    path = PROFILES_DIR / f"{name}.yaml"
    return SearchProfile(**yaml.safe_load(path.read_text()))


def load_all_profiles() -> list[SearchProfile]:
    return [
        SearchProfile(**yaml.safe_load(p.read_text()))
        for p in sorted(PROFILES_DIR.glob("*.yaml"))
    ]
