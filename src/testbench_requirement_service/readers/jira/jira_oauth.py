import json
import os
import sys
import threading
import time
from pathlib import Path
from urllib import error, request
from urllib.parse import urlencode

import tomli_w

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

token_store: dict[str, str | float] = {
    "access_token": "YOUR_CURRENT_ACCESS_TOKEN",
    "refresh_token": "YOUR_CURRENT_REFRESH_TOKEN",
    "expires_at": time.time() + 3600,
}

_TOKEN_CACHE_PATH = Path("tmp/oauth2_tokens.toml")
_TOKEN_CACHE_SECTION = "oauth2"

refresh_lock_sync = threading.Lock()

_CLIENT_ID = os.getenv("JIRA_OAUTH2_CLIENT_ID", "YOUR_CLIENT_ID")
_CLIENT_SECRET = os.getenv("JIRA_OAUTH2_CLIENT_SECRET", "YOUR_CLIENT_SECRET")

GRANT_REFRESH_TOKEN = "refresh_token"
GRANT_CLIENT_CREDENTIALS = "client_credentials"

CLOUD_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
_DC_TOKEN_PATH = "/rest/oauth2/1.0/token"
BODY_FORMAT_JSON = "json"
BODY_FORMAT_FORM = "form"


def data_center_token_url(server_url: str) -> str:
    """Return the Jira Data Center OAuth2 token endpoint for *server_url*."""
    return server_url.rstrip("/") + _DC_TOKEN_PATH


_oauth2_settings = {
    "client_id": _CLIENT_ID,
    "client_secret": _CLIENT_SECRET,
    "grant_type": GRANT_REFRESH_TOKEN,
    "token_url": CLOUD_TOKEN_URL,
    "body_format": BODY_FORMAT_JSON,
}


def _load_token_store_from_disk() -> None:
    """Load persisted OAuth2 tokens from tmp/oauth2_tokens.toml when available."""
    if not _TOKEN_CACHE_PATH.exists():
        return

    try:
        with _TOKEN_CACHE_PATH.open("rb") as cache_file:
            data = tomllib.load(cache_file)
    except (OSError, tomllib.TOMLDecodeError):
        return

    section = data.get(_TOKEN_CACHE_SECTION, data)
    if not isinstance(section, dict):
        return

    refresh_token = section.get("refresh_token")
    if isinstance(refresh_token, str) and refresh_token:
        token_store["refresh_token"] = refresh_token


def _persist_token_store_to_disk() -> None:
    """Persist OAuth2 runtime tokens to tmp/oauth2_tokens.toml atomically."""
    refresh_token = str(token_store.get("refresh_token", ""))

    if not refresh_token:
        return
    if _is_placeholder(refresh_token):
        return

    cache_section: dict[str, str | float] = {
        "refresh_token": refresh_token,
    }

    payload = {_TOKEN_CACHE_SECTION: cache_section}

    _TOKEN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = _TOKEN_CACHE_PATH.with_suffix(".tmp")

    try:
        with tmp_path.open("wb") as cache_file:
            tomli_w.dump(payload, cache_file)
        tmp_path.replace(_TOKEN_CACHE_PATH)
    except OSError:
        return


def _is_placeholder(value: str) -> bool:
    return value.startswith("YOUR_")


def exchange_authorization_code_sync(  # noqa: PLR0913
    *,
    token_url: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    code_verifier: str,
) -> str:
    """Exchange a 3LO authorization code (with PKCE verifier) for tokens (Jira DC).

    Performs the one-time ``authorization_code`` grant against *token_url*
    (``{server_url}/rest/oauth2/1.0/token`` on Jira Data Center), stores the
    resulting access and refresh tokens in the in-memory token store, persists
    the refresh token to the on-disk cache, and returns the refresh token.

    Raises ``JiraAuthExpiredError`` on HTTP 400/401 (invalid, expired, or
    already-used code; verifier mismatch) or when the response contains no
    refresh token.
    """
    payload = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "code": code,
        "code_verifier": code_verifier,
    }
    data = _post_oauth_token_request(payload, token_url=token_url, body_format=BODY_FORMAT_FORM)

    refresh_token = data.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        raise JiraAuthExpiredError("Jira OAuth2 token response did not contain a refresh token")

    token_store["access_token"] = str(data.get("access_token", ""))
    token_store["refresh_token"] = refresh_token
    token_store["expires_at"] = time.time() + int(str(data.get("expires_in", 0)))
    _persist_token_store_to_disk()
    return refresh_token


def has_cached_refresh_token() -> bool:
    """Return whether a usable OAuth2 refresh token is available in the runtime cache."""
    _load_token_store_from_disk()
    refresh_token = str(token_store.get("refresh_token", ""))
    return bool(refresh_token) and not _is_placeholder(refresh_token)


def seed_oauth2_refresh_token(refresh_token: str) -> None:
    """Store a wizard-provided OAuth2 refresh token in the runtime token cache."""
    token_store["refresh_token"] = refresh_token
    token_store["access_token"] = ""
    token_store["expires_at"] = 0.0
    _persist_token_store_to_disk()


class JiraAuthExpiredError(Exception):
    """Raised when Jira OAuth refresh fails due to invalid or expired authorization."""


def configure_oauth2_runtime(
    *,
    access_token: str | None = None,
    refresh_token: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    expires_at: int | None = None,
    grant_type: str | None = None,
    token_url: str | None = None,
    body_format: str | None = None,
) -> None:
    """Apply OAuth2 runtime values from config/environment to token refresh state."""
    if grant_type != GRANT_CLIENT_CREDENTIALS:
        _load_token_store_from_disk()

    # Always accept explicit config credentials, even when a token cache exists.
    # This allows runtime config values to override placeholder env defaults.
    if grant_type:
        _oauth2_settings["grant_type"] = grant_type
    if client_id:
        _oauth2_settings["client_id"] = client_id
    if client_secret:
        _oauth2_settings["client_secret"] = client_secret
    if token_url:
        _oauth2_settings["token_url"] = token_url
    if body_format:
        _oauth2_settings["body_format"] = body_format

    if access_token and not _is_placeholder(access_token):
        token_store["access_token"] = access_token
    if refresh_token and not _is_placeholder(refresh_token):
        token_store["refresh_token"] = refresh_token
    if expires_at is not None:
        token_store["expires_at"] = float(expires_at)

    if _oauth2_settings.get("grant_type") != GRANT_CLIENT_CREDENTIALS:
        _persist_token_store_to_disk()


def _post_oauth_token_request(
    payload: dict[str, str],
    token_url: str | None = None,
    body_format: str | None = None,
) -> dict[str, object]:
    """POST *payload* to the configured OAuth token endpoint and return the JSON body.

    Explicit *token_url* / *body_format* arguments override the runtime settings
    (used for the one-time authorization-code exchange, which runs before the
    OAuth2 runtime is configured). Cloud uses JSON bodies; Data Center expects
    application/x-www-form-urlencoded."""

    url = token_url or str(_oauth2_settings.get("token_url", CLOUD_TOKEN_URL))
    fmt = body_format or str(_oauth2_settings.get("body_format", BODY_FORMAT_JSON))
    if fmt == BODY_FORMAT_FORM:
        data = urlencode(payload).encode("utf-8")
        content_type = "application/x-www-form-urlencoded"
    else:
        data = json.dumps(payload).encode("utf-8")
        content_type = "application/json"

    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": content_type},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=20) as resp:
            raw_data = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        if exc.code in {400, 401}:
            raise JiraAuthExpiredError from exc
        raise

    data_object = json.loads(raw_data)
    if not isinstance(data_object, dict):
        raise RuntimeError("Unexpected token response format from Jira OAuth endpoint")
    return data_object


def _refresh_jira_token_sync() -> dict[str, object]:
    client_id = _oauth2_settings.get("client_id", "")
    client_secret = _oauth2_settings.get("client_secret", "")

    if _is_placeholder(client_id) or _is_placeholder(client_secret):
        raise JiraAuthExpiredError("Jira OAuth2 client credentials are not configured")
    payload = {
        "grant_type": GRANT_REFRESH_TOKEN,
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": str(token_store.get("refresh_token", "")),
    }
    return _post_oauth_token_request(payload)


def _mint_client_credentials_token_sync() -> dict[str, object]:
    client_id = _oauth2_settings.get("client_id", "")
    client_secret = _oauth2_settings.get("client_secret", "")
    missing = not client_id or not client_secret

    if missing or _is_placeholder(client_id) or _is_placeholder(client_secret):
        raise JiraAuthExpiredError("Jira OAuth2 client credentials are not configured")

    payload = {
        "grant_type": GRANT_CLIENT_CREDENTIALS,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    return _post_oauth_token_request(payload)


def _is_cached_2lo_token_valid(is_first_call: bool) -> str | None:
    """Check if a cached 2LO token is valid and return it, or None if not."""
    if is_first_call:
        return None

    expires_at = float(str(token_store.get("expires_at", 0)))
    access_token = str(token_store.get("access_token", ""))
    if access_token and not _is_placeholder(access_token) and time.time() < (expires_at - 300):
        return access_token
    return None


def _get_valid_client_credentials_token(is_first_call: bool) -> str:
    cached_token = _is_cached_2lo_token_valid(is_first_call=False)
    if cached_token is not None:
        return cached_token
    with refresh_lock_sync:
        cached_token = _is_cached_2lo_token_valid(is_first_call)
        if cached_token is not None:
            return cached_token
        data = _mint_client_credentials_token_sync()
        token_store["access_token"] = str(data.get("access_token", ""))
        token_store["expires_at"] = time.time() + int(str(data.get("expires_in", 0)))
        return str(token_store.get("access_token", ""))


def get_valid_jira_token_sync(
    fallback_token: str | None = None, is_first_call: bool = False
) -> str:
    """Returns a valid access token for synchronous callers.

    If refresh credentials are not configured, the provided fallback token is used.
    """
    if _oauth2_settings.get("grant_type") == GRANT_CLIENT_CREDENTIALS:
        return _get_valid_client_credentials_token(is_first_call)
    expires_at, access_token = _get_cached_token_data(fallback_token)
    token_before_lock = access_token

    if time.time() < (expires_at - 300) and access_token and not is_first_call:
        return access_token

    with refresh_lock_sync:
        _load_token_store_from_disk()

        expires_at, access_token = _get_cached_token_data(fallback_token)

        # Check one more time in case the disk load yielded a fresh, valid token
        refreshed_by_peer = access_token != token_before_lock
        if (
            time.time() < (expires_at - 300)
            and access_token
            and (not is_first_call or refreshed_by_peer)
        ):
            return access_token

        refresh_token = str(token_store.get("refresh_token", ""))
        if _is_placeholder(refresh_token) or not refresh_token:
            if fallback_token:
                return fallback_token
            raise JiraAuthExpiredError("Jira OAuth2 refresh token is not configured")

        data = _refresh_jira_token_sync()

        token_store["access_token"] = str(data.get("access_token", ""))
        token_store["refresh_token"] = str(data.get("refresh_token", ""))
        token_store["expires_at"] = time.time() + int(str(data.get("expires_in", 0)))
        _persist_token_store_to_disk()

        return str(token_store.get("access_token", ""))


def _get_cached_token_data(fallback_token: str | None) -> tuple[float, str]:
    expires_at = float(str(token_store.get("expires_at", 0)))
    access_token = str(token_store.get("access_token", ""))

    if fallback_token and (_is_placeholder(access_token) or not access_token):
        access_token = fallback_token
    return expires_at, access_token
