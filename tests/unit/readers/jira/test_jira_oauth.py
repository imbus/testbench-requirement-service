"""Unit tests for the Jira OAuth2 token handling in jira_oauth.py.

The module keeps process-wide mutable state (``token_store``, ``_oauth2_settings``)
and persists tokens to a fixed cache path. The ``oauth_env`` fixture isolates every
test by redirecting the cache path to ``tmp_path`` and resetting the in-memory state to
its placeholder defaults, so tests never touch the real ``tmp/oauth2_tokens.toml`` and
never leak state into each other.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING
from urllib import error

import pytest

if TYPE_CHECKING:
    from typing import Self

from testbench_requirement_service.readers.jira import jira_oauth

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@pytest.fixture
def oauth_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Isolate module-level OAuth state and redirect the token cache to tmp_path."""
    cache_path = tmp_path / "oauth2_tokens.toml"
    monkeypatch.setattr(jira_oauth, "_TOKEN_CACHE_PATH", cache_path)

    monkeypatch.setitem(jira_oauth.token_store, "access_token", "YOUR_CURRENT_ACCESS_TOKEN")
    monkeypatch.setitem(jira_oauth.token_store, "refresh_token", "YOUR_CURRENT_REFRESH_TOKEN")
    monkeypatch.setitem(jira_oauth.token_store, "expires_at", 0.0)

    monkeypatch.setitem(jira_oauth._oauth2_settings, "client_id", "YOUR_CLIENT_ID")
    monkeypatch.setitem(jira_oauth._oauth2_settings, "client_secret", "YOUR_CLIENT_SECRET")

    return jira_oauth


class _FakeResponse:
    """Minimal context-manager stand-in for urllib's urlopen return value."""

    def __init__(self, payload: str) -> None:
        self._payload = payload

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._payload.encode("utf-8")


class TestIsPlaceholder:
    def test_placeholder_values_detected(self) -> None:
        assert jira_oauth._is_placeholder("YOUR_CLIENT_ID") is True
        assert jira_oauth._is_placeholder("YOUR_CURRENT_REFRESH_TOKEN") is True

    def test_real_values_not_flagged(self) -> None:
        assert jira_oauth._is_placeholder("real-refresh-token") is False
        assert jira_oauth._is_placeholder("") is False


class TestHasCachedRefreshToken:
    def test_false_for_placeholder_default(self, oauth_env) -> None:
        assert oauth_env.has_cached_refresh_token() is False

    def test_true_when_real_token_in_store(self, oauth_env) -> None:
        oauth_env.token_store["refresh_token"] = "real-refresh-token"
        assert oauth_env.has_cached_refresh_token() is True

    def test_loads_token_from_disk_cache(self, oauth_env) -> None:
        # A token seeded to disk should be picked up on a fresh check.
        oauth_env.seed_oauth2_refresh_token("disk-refresh-token")
        oauth_env.token_store["refresh_token"] = "YOUR_CURRENT_REFRESH_TOKEN"

        assert oauth_env.has_cached_refresh_token() is True
        assert oauth_env.token_store["refresh_token"] == "disk-refresh-token"


class TestSeedAndPersist:
    def test_seed_writes_token_to_disk(self, oauth_env) -> None:
        oauth_env.seed_oauth2_refresh_token("seeded-token")

        assert oauth_env.token_store["refresh_token"] == "seeded-token"
        assert oauth_env.token_store["access_token"] == ""
        assert oauth_env.token_store["expires_at"] == 0.0

        with oauth_env._TOKEN_CACHE_PATH.open("rb") as handle:
            data = tomllib.load(handle)
        assert data["oauth2"]["refresh_token"] == "seeded-token"
        # Placeholder/empty access token must not be persisted.
        assert "access_token" not in data["oauth2"]

    def test_persist_skips_placeholder_refresh_token(self, oauth_env) -> None:
        oauth_env.token_store["refresh_token"] = "YOUR_CURRENT_REFRESH_TOKEN"
        oauth_env._persist_token_store_to_disk()
        assert not oauth_env._TOKEN_CACHE_PATH.exists()

    def test_persist_skips_empty_refresh_token(self, oauth_env) -> None:
        oauth_env.token_store["refresh_token"] = ""
        oauth_env._persist_token_store_to_disk()
        assert not oauth_env._TOKEN_CACHE_PATH.exists()

    def test_persist_and_load_round_trip(self, oauth_env) -> None:
        oauth_env.token_store["refresh_token"] = "rt"
        oauth_env.token_store["access_token"] = "at"
        oauth_env.token_store["expires_at"] = 1234.0
        oauth_env._persist_token_store_to_disk()

        # Wipe in-memory state, then reload from disk.
        oauth_env.token_store["refresh_token"] = "YOUR_CURRENT_REFRESH_TOKEN"
        oauth_env.token_store["access_token"] = "YOUR_CURRENT_ACCESS_TOKEN"
        oauth_env.token_store["expires_at"] = 0.0
        oauth_env._load_token_store_from_disk()

        assert oauth_env.token_store["refresh_token"] == "rt"
        assert oauth_env.token_store["access_token"] == "at"
        assert oauth_env.token_store["expires_at"] == 1234.0

    def test_load_missing_file_is_noop(self, oauth_env) -> None:
        assert not oauth_env._TOKEN_CACHE_PATH.exists()
        oauth_env._load_token_store_from_disk()  # must not raise
        assert oauth_env.token_store["refresh_token"] == "YOUR_CURRENT_REFRESH_TOKEN"


class TestConfigureOauth2Runtime:
    def test_applies_client_credentials(self, oauth_env) -> None:
        oauth_env.configure_oauth2_runtime(
            client_id="cid", client_secret="secret", refresh_token="rt", expires_at=999
        )
        assert oauth_env._oauth2_settings["client_id"] == "cid"
        assert oauth_env._oauth2_settings["client_secret"] == "secret"
        assert oauth_env.token_store["refresh_token"] == "rt"
        assert oauth_env.token_store["expires_at"] == 999.0

    def test_credentials_override_even_when_cache_exists(self, oauth_env) -> None:
        # Seed a disk cache so the token branch is skipped, but creds still apply.
        oauth_env.seed_oauth2_refresh_token("disk-token")
        oauth_env.configure_oauth2_runtime(
            client_id="cid", client_secret="secret", refresh_token="ignored"
        )
        assert oauth_env._oauth2_settings["client_id"] == "cid"
        # Existing cache means the provided refresh token is not applied over it.
        assert oauth_env.token_store["refresh_token"] == "disk-token"


class TestRefreshJiraTokenSync:
    def test_placeholder_credentials_raise(self, oauth_env) -> None:
        oauth_env.token_store["refresh_token"] = "rt"
        with pytest.raises(oauth_env.JiraAuthExpiredError, match="client credentials"):
            oauth_env._refresh_jira_token_sync()

    def test_successful_refresh_returns_parsed_dict(self, oauth_env, monkeypatch) -> None:
        oauth_env._oauth2_settings["client_id"] = "cid"
        oauth_env._oauth2_settings["client_secret"] = "secret"
        oauth_env.token_store["refresh_token"] = "rt"

        monkeypatch.setattr(
            oauth_env.request,
            "urlopen",
            lambda *_a, **_k: _FakeResponse('{"access_token": "new", "expires_in": 3600}'),
        )
        data = oauth_env._refresh_jira_token_sync()
        assert data["access_token"] == "new"
        assert data["expires_in"] == 3600

    @pytest.mark.parametrize("status", [400, 401])
    def test_auth_errors_become_expired_error(self, oauth_env, monkeypatch, status) -> None:
        oauth_env._oauth2_settings["client_id"] = "cid"
        oauth_env._oauth2_settings["client_secret"] = "secret"
        oauth_env.token_store["refresh_token"] = "rt"

        def _raise(*_a, **_k):
            raise error.HTTPError("url", status, "boom", hdrs=None, fp=None)

        monkeypatch.setattr(oauth_env.request, "urlopen", _raise)
        with pytest.raises(oauth_env.JiraAuthExpiredError):
            oauth_env._refresh_jira_token_sync()

    def test_other_http_errors_propagate(self, oauth_env, monkeypatch) -> None:
        oauth_env._oauth2_settings["client_id"] = "cid"
        oauth_env._oauth2_settings["client_secret"] = "secret"
        oauth_env.token_store["refresh_token"] = "rt"

        def _raise(*_a, **_k):
            raise error.HTTPError("url", 500, "server error", hdrs=None, fp=None)

        monkeypatch.setattr(oauth_env.request, "urlopen", _raise)
        with pytest.raises(error.HTTPError):
            oauth_env._refresh_jira_token_sync()


class TestGetValidJiraTokenSync:
    def test_returns_cached_token_without_refreshing(self, oauth_env, monkeypatch) -> None:
        oauth_env.token_store["access_token"] = "cached"
        oauth_env.token_store["refresh_token"] = "rt"
        oauth_env.token_store["expires_at"] = time.time() + 10_000

        def _fail() -> dict:
            raise AssertionError("refresh must not be called for a valid cached token")

        monkeypatch.setattr(oauth_env, "_refresh_jira_token_sync", _fail)
        assert oauth_env.get_valid_jira_token_sync() == "cached"

    def test_refreshes_when_expired(self, oauth_env, monkeypatch) -> None:
        oauth_env.token_store["access_token"] = "old"
        oauth_env.token_store["refresh_token"] = "rt"
        oauth_env.token_store["expires_at"] = 0.0  # already expired

        monkeypatch.setattr(
            oauth_env,
            "_refresh_jira_token_sync",
            lambda: {"access_token": "fresh", "refresh_token": "rt2", "expires_in": 3600},
        )
        token = oauth_env.get_valid_jira_token_sync()
        assert token == "fresh"
        assert oauth_env.token_store["refresh_token"] == "rt2"
        assert oauth_env.token_store["expires_at"] > 0

    def test_first_call_forces_refresh_even_if_not_expired(self, oauth_env, monkeypatch) -> None:
        oauth_env.token_store["access_token"] = "cached"
        oauth_env.token_store["refresh_token"] = "rt"
        oauth_env.token_store["expires_at"] = time.time() + 10_000

        called = SimpleNamespace(count=0)

        def _refresh() -> dict:
            called.count += 1
            return {"access_token": "fresh", "refresh_token": "rt", "expires_in": 3600}

        monkeypatch.setattr(oauth_env, "_refresh_jira_token_sync", _refresh)
        token = oauth_env.get_valid_jira_token_sync(is_first_call=True)
        assert token == "fresh"
        assert called.count == 1

    def test_falls_back_when_refresh_token_missing(self, oauth_env, monkeypatch) -> None:
        oauth_env.token_store["refresh_token"] = "YOUR_CURRENT_REFRESH_TOKEN"
        oauth_env.token_store["access_token"] = ""
        oauth_env.token_store["expires_at"] = 0.0

        def _fail() -> dict:
            raise AssertionError("refresh must not run without a configured refresh token")

        monkeypatch.setattr(oauth_env, "_refresh_jira_token_sync", _fail)
        assert oauth_env.get_valid_jira_token_sync(fallback_token="fallback") == "fallback"

    def test_raises_when_no_refresh_token_and_no_fallback(self, oauth_env) -> None:
        oauth_env.token_store["refresh_token"] = "YOUR_CURRENT_REFRESH_TOKEN"
        oauth_env.token_store["access_token"] = ""
        oauth_env.token_store["expires_at"] = 0.0

        with pytest.raises(oauth_env.JiraAuthExpiredError, match="not configured"):
            oauth_env.get_valid_jira_token_sync()
