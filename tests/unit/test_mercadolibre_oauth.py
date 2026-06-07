"""T019 — MercadoLibre OAuth (client-credentials + refresh).

No live API: a fake TokenClient and an injected clock make these deterministic and
runnable without ML credentials.
"""

from __future__ import annotations

import pytest

from src.config import Settings
from src.collectors.base import Collector
from src.collectors.mercadolibre import MercadoLibreCollector


def _settings(client_id="id-123", client_secret="secret-abc") -> Settings:
    return Settings(
        storage_connection_string="UseDevelopmentStorage=true",
        ml_client_id=client_id,
        ml_client_secret=client_secret,
    )


class FakeTokenClient:
    """Records calls and returns canned tokens (no network)."""

    def __init__(self, expires_in: int = 3600) -> None:
        self.calls: list[tuple[str, str]] = []
        self._expires_in = expires_in

    def fetch_token(self, client_id: str, client_secret: str) -> dict:
        self.calls.append((client_id, client_secret))
        return {
            "access_token": f"token-{len(self.calls)}",
            "expires_in": self._expires_in,
            "token_type": "bearer",
        }


class FakeClock:
    """A controllable monotonic clock."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _collector(token_client, clock, settings=None) -> MercadoLibreCollector:
    return MercadoLibreCollector(
        settings=settings or _settings(),
        token_client=token_client,
        time_fn=clock,
    )


def test_satisfies_collector_protocol():
    # The CI gate: the adapter must duck-type as a Collector, constructible bare.
    assert isinstance(MercadoLibreCollector(), Collector)


def test_construction_does_no_network_and_needs_no_creds():
    # Building the adapter with blank creds must not raise or call the token client.
    tc = FakeTokenClient()
    c = _collector(tc, FakeClock(), settings=_settings(None, None))
    assert tc.calls == []
    assert c.name == "mercadolibre"
    assert c.capabilities.has_api is True
    assert c.capabilities.provides_visits is True
    assert c.capabilities.provides_listing_age is True
    assert c.capabilities.removal_signal.value == "status"


def test_first_call_fetches_token():
    tc = FakeTokenClient()
    c = _collector(tc, FakeClock())
    assert c._access_token() == "token-1"
    assert tc.calls == [("id-123", "secret-abc")]


def test_token_is_cached_within_ttl():
    tc = FakeTokenClient(expires_in=3600)
    clock = FakeClock()
    c = _collector(tc, clock)

    first = c._access_token()
    clock.now += 100  # still well within TTL
    second = c._access_token()

    assert first == second == "token-1"
    assert len(tc.calls) == 1  # no second fetch


def test_token_refreshes_after_expiry():
    tc = FakeTokenClient(expires_in=3600)
    clock = FakeClock()
    c = _collector(tc, clock)

    assert c._access_token() == "token-1"
    clock.now += 3600  # past expiry (margin makes this comfortably expired)
    assert c._access_token() == "token-2"
    assert len(tc.calls) == 2


def test_expiry_margin_triggers_early_refresh():
    # With a 3600s TTL and 60s margin, the token must be considered expired at 3540s+.
    tc = FakeTokenClient(expires_in=3600)
    clock = FakeClock()
    c = _collector(tc, clock)

    c._access_token()
    clock.now += 3559  # past (3600 - 60) margin
    c._access_token()
    assert len(tc.calls) == 2


def test_missing_credentials_raises_only_when_token_needed():
    tc = FakeTokenClient()
    c = _collector(tc, FakeClock(), settings=_settings(None, None))
    with pytest.raises(RuntimeError, match="credentials missing"):
        c._access_token()
    assert tc.calls == []  # never attempted the fetch


def test_missing_access_token_in_response_raises():
    class NoTokenClient:
        def fetch_token(self, client_id, client_secret):
            return {"expires_in": 3600}  # no access_token

    c = _collector(NoTokenClient(), FakeClock())
    with pytest.raises(RuntimeError, match="no access_token"):
        c._access_token()
