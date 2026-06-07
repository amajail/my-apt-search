"""Environment-driven settings.

Local dev reads these from local.settings.json (via the Functions host) or the process
environment; in Azure they come from the Function App application settings.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Settings:
    storage_connection_string: str
    ml_client_id: Optional[str]
    ml_client_secret: Optional[str]


def load_settings() -> Settings:
    return Settings(
        storage_connection_string=os.environ.get(
            "AzureWebJobsStorage", "UseDevelopmentStorage=true"
        ),
        ml_client_id=os.environ.get("ML_CLIENT_ID") or None,
        ml_client_secret=os.environ.get("ML_CLIENT_SECRET") or None,
    )
