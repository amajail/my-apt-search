"""MercadoLibre (MLA — Argentina) source adapter.

Implements the frozen `Collector` protocol (src/collectors/base.py). ALL MercadoLibre
specifics — OAuth, paging, rate limits, payload mapping — live here and nowhere else
(Constitution Principle I & II). The core only ever sees the common model in
src/models.py.

Self-registers at the bottom of the module; the composition root (function_app.py)
imports this module so that registration runs. The pipeline/storage never import it.

Capabilities (research.md §5): has_api, provides_visits, provides_listing_age,
removal_signal=status.

Build order: T019 OAuth (this commit) → T020 search → T021 get_item + register.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

import httpx

from src.config import Settings, load_settings
from src.models import (
    Capabilities,
    Listing,
    ListingRef,
    RemovalSignal,
    SearchProfile,
    Visits,
)

# --- Constants ---------------------------------------------------------------

API_BASE = "https://api.mercadolibre.com"
OAUTH_TOKEN_URL = f"{API_BASE}/oauth/token"

# Refresh a little before the real expiry so an in-flight request never races a
# server-side expiration.
TOKEN_EXPIRY_MARGIN_S = 60

ML_CAPABILITIES = Capabilities(
    has_api=True,
    provides_visits=True,
    provides_listing_age=True,
    removal_signal=RemovalSignal.status,
)


# --- OAuth token client ------------------------------------------------------


class TokenClient:
    """Fetches an app access token via OAuth client-credentials.

    Isolated behind a tiny seam so tests inject a fake and never hit the network
    (there is no registered ML developer app yet — credentials are blank in dev).
    """

    def __init__(self, *, http_client: Optional[httpx.Client] = None) -> None:
        self._http = http_client

    def fetch_token(self, client_id: str, client_secret: str) -> dict:
        """POST grant_type=client_credentials; return the raw token payload.

        Payload shape: {"access_token": str, "expires_in": int, ...}.
        """
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
        if self._http is not None:
            resp = self._http.post(OAUTH_TOKEN_URL, data=data)
        else:
            resp = httpx.post(OAUTH_TOKEN_URL, data=data, timeout=30.0)
        resp.raise_for_status()
        return resp.json()


# --- Collector ---------------------------------------------------------------


class MercadoLibreCollector:
    """Collector adapter for MercadoLibre Argentina (MLA).

    Constructible with no arguments (the registry factory calls it that way and the
    contract `isinstance(..., Collector)` check needs it). Construction performs NO
    network I/O — credentials are read lazily, only when a token is actually needed,
    so importing/instantiating the adapter is safe without ML credentials.
    """

    def __init__(
        self,
        *,
        settings: Optional[Settings] = None,
        token_client: Optional[TokenClient] = None,
        time_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = "mercadolibre"
        self.capabilities = ML_CAPABILITIES

        self._settings = settings or load_settings()
        self._token_client = token_client or TokenClient()
        self._time_fn = time_fn

        # Token cache.
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

    # --- OAuth -------------------------------------------------------------

    def _access_token(self) -> str:
        """Return a valid app access token, fetching/refreshing as needed."""
        now = self._time_fn()
        if self._token is not None and now < self._token_expires_at:
            return self._token
        return self._refresh_token()

    def _refresh_token(self) -> str:
        client_id = self._settings.ml_client_id
        client_secret = self._settings.ml_client_secret
        if not client_id or not client_secret:
            raise RuntimeError(
                "MercadoLibre credentials missing: set ML_CLIENT_ID and "
                "ML_CLIENT_SECRET (see local.settings.json)."
            )

        payload = self._token_client.fetch_token(client_id, client_secret)
        token = payload.get("access_token")
        if not token:
            raise RuntimeError(
                "MercadoLibre OAuth response had no access_token; "
                f"got keys: {sorted(payload)}"
            )

        # expires_in is seconds from now; subtract a margin to refresh early.
        expires_in = int(payload.get("expires_in", 0))
        self._token = token
        self._token_expires_at = self._time_fn() + max(
            0, expires_in - TOKEN_EXPIRY_MARGIN_S
        )
        return token

    # --- Collector protocol -------------------------------------------------
    # search/get_item land in T020/T021; get_visits stays stubbed until T027.
    # Defined now so `isinstance(MercadoLibreCollector(), Collector)` holds.

    def search(self, profile: SearchProfile) -> list[ListingRef]:
        raise NotImplementedError("MercadoLibre search: T020")

    def get_item(self, ref: ListingRef) -> Listing:
        raise NotImplementedError("MercadoLibre get_item: T021")

    def get_visits(self, ref: ListingRef) -> Optional[Visits]:
        """Stubbed until T027 (US2). Returns None despite provides_visits=True."""
        return None
