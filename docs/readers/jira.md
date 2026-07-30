---
sidebar_position: 4
title: Jira Reader
---

# Jira Reader

Connects to a Jira instance via the REST API to read requirements stored as Jira issues (Epics, Stories, Tasks, etc.).

**When to use:** Your requirements are managed in Jira and you want live access without manual exports.

### Tested Jira versions

| Deployment | Version |
|-----------|---------|
| Jira Cloud | latest |
| Jira Data Center | 11.3 |
| Jira Data Center | 10.3 |
| Jira Data Center | 9.4 |

Other versions may work but are not officially supported.

## Installation

Install the Jira extra:

```bash
pip install testbench-requirement-service[jira]
```

## Setup

1. Ensure the Jira account has the [required permissions](#jira-user-permissions).
2. Configure the Jira server URL and authentication type.
3. Provide credentials via `config.toml`, a `.env` file, or environment variables.
4. Start the service.

### Jira user permissions

The Jira account needs the following permissions:

- **Browse Projects** — required to list projects, search issues, read changelogs and field metadata.
- **Create Issues** — required to fetch per-project field metadata. This is used when querying user-defined attributes or when `baseline_field` is set to a custom field name other than `fixVersions` or `sprint`.

### Minimal configuration

```toml
# config.toml
[testbench-requirement-service]
reader_class = "JiraRequirementReader"

[testbench-requirement-service.reader_config]
server_url = "https://example.atlassian.net/"
auth_type = "basic"
username = "my-user@example.com"  # (or set JIRA_USERNAME as environment variable)
password = "my-api-token"         # (or set JIRA_PASSWORD as environment variable)
```

Set credentials via environment variables, e.g. run in the terminal:

```bash
export JIRA_USERNAME=my-user@example.com
export JIRA_PASSWORD=my-api-token
```

Or in a `.env` file:

```text
JIRA_USERNAME=my-user@example.com
JIRA_PASSWORD=my-api-token
```

## Configuration

The configuration can be added directly to `config.toml` under `[testbench-requirement-service.reader_config]` (recommended) or in a separate `.toml` file without a section prefix.

### Connection settings

| Setting | Type | Description | Required | Default |
|---------|------|-------------|----------|---------|
| `server_url` | String | Base URL of the Jira instance (e.g. `https://your-company.atlassian.net`) | Yes | (none) |
| `auth_type` | String | Authentication method: `basic`, `token`, `oauth1`, `oauth2 2LO (service account)`, or `oauth2 3LO (user account)` | No | `basic` |
| `timeout` | Integer | HTTP request timeout in seconds (1–300) | No | `30` |
| `max_retries` | Integer | Max retries for failed API requests (0–10) | No | `3` |
| `cache_ttl` | Float | Cache time-to-live in seconds. `0` = disable caching. | No | `300.0` |
| `proxy_url` | String | HTTP(S) proxy for all Jira API requests (e.g. `http://proxy.example.com:8080`). See [Proxy settings](#proxy-settings). | No | (none) |

### Authentication methods

Pick the authentication flow that matches your Jira deployment. Credentials can be set in the config file or via environment variables.

| `auth_type` | When to use | Required values |
|-------------|-------------|-----------------|
| `basic` | Jira Cloud and Data Center with username + password/API token | `username` + `password` (or `JIRA_USERNAME` + `JIRA_PASSWORD`) |
| `token` | Jira Server/Data Center with Personal Access Tokens | `token` (or `JIRA_BEARER_TOKEN`) |
| `oauth1` | Enterprise instances requiring OAuth 1.0a | `oauth1_access_token`, `oauth1_access_token_secret`, `oauth1_consumer_key`, `oauth1_key_cert_path` (or matching env vars) |
| `oauth2 2LO (service account)` | Jira Cloud, unattended service-to-service access without a user account | `oauth2_client_id` + `oauth2_client_secret` (or `JIRA_OAUTH2_CLIENT_ID` + `JIRA_OAUTH2_CLIENT_SECRET`) |
| `oauth2 3LO (user account)` | Jira Cloud, delegated access on behalf of a user | `oauth2_client_id` + `oauth2_client_secret`, plus a refresh token seeded via the setup wizard |

:::warning
The two OAuth 2.0 values must be typed **exactly** as shown, including spaces, capitalization and parentheses — e.g. `auth_type = "oauth2 3LO (user account)"`. Any other spelling (such as the older `"oauth2"`) is rejected with a validation error at startup. Use `testbench-requirement-service init` / `configure` to pick the value from a list instead of typing it.
:::

#### Basic authentication (`auth_type = "basic"`)

| Setting | Type | Description | Env var |
|---------|------|-------------|---------|
| `username` | String | Jira account username (e-mail for Cloud) | `JIRA_USERNAME` |
| `password` | String | Password or API token (Cloud requires API token) | `JIRA_PASSWORD` |

#### Token authentication (`auth_type = "token"`)

| Setting | Type | Description | Env var |
|---------|------|-------------|---------|
| `token` | String | Personal Access Token (PAT) | `JIRA_BEARER_TOKEN` |

#### OAuth1 authentication (`auth_type = "oauth1"`)

| Setting | Type | Description | Env var |
|---------|------|-------------|---------|
| `oauth1_access_token` | String | OAuth1 access token | `JIRA_OAUTH1_ACCESS_TOKEN` |
| `oauth1_access_token_secret` | String | OAuth1 access token secret | `JIRA_OAUTH1_ACCESS_TOKEN_SECRET` |
| `oauth1_consumer_key` | String | OAuth1 consumer key | `JIRA_OAUTH1_CONSUMER_KEY` |
| `oauth1_key_cert_path` | String | Path to RSA private key file (`.pem`) | `JIRA_OAUTH1_KEY_CERT_PATH` |

#### OAuth2 2LO authentication (`auth_type = "oauth2 2LO (service account)"`)

Two-legged OAuth: the service authenticates as itself using the `client_credentials` grant. No user consent and no refresh token are involved — access tokens are minted from the client ID/secret and re-minted automatically when they expire.

| Setting | Type | Description | Env var |
|---------|------|-------------|---------|
| `oauth2_client_id` | String | OAuth 2.0 client ID (required) | `JIRA_OAUTH2_CLIENT_ID` |
| `oauth2_client_secret` | String | OAuth 2.0 client secret (required) | `JIRA_OAUTH2_CLIENT_SECRET` |

#### OAuth2 3LO authentication (`auth_type = "oauth2 3LO (user account)"`)

Three-legged OAuth: a user grants consent once, and the resulting refresh token is used to obtain short-lived access tokens at runtime.

| Setting | Type | Description | Env var |
|---------|------|-------------|---------|
| `oauth2_client_id` | String | OAuth 2.0 client ID (required) | `JIRA_OAUTH2_CLIENT_ID` |
| `oauth2_client_secret` | String | OAuth 2.0 client secret (required) | `JIRA_OAUTH2_CLIENT_SECRET` |
| `oauth2_refresh_token` | String | Refresh token from the 3LO consent flow. Not written to `config.toml` — the wizard stores it in `tmp/oauth2_tokens.toml`. Required unless a token is already cached there. | `JIRA_OAUTH2_REFRESH_TOKEN` |
| `oauth2_expires_at` | Integer | Optional UNIX timestamp for when the current access token expires. Rarely needed; the service tracks expiry itself. | `JIRA_OAUTH2_EXPIRES_AT` |

See [OAuth 2.0 (3LO) auth](#oauth-20-3lo-auth-jira-cloud) below for the full consent flow and the required scopes.

### Proxy settings

Only needed when the service cannot reach Jira (or `auth.atlassian.com`) directly and has to go through a forward proxy — typical in corporate networks with egress filtering.

| Setting | Type | Description | Default | Env var |
|---------|------|-------------|---------|---------|
| `proxy_url` | String | Proxy URL used for both HTTP and HTTPS Jira API requests, e.g. `http://proxy.example.com:8080`. Credentials can be embedded as `http://user:password@proxy.example.com:8080`. | (none) | — |

```toml
# config.toml
[testbench-requirement-service.reader_config]
server_url = "https://example.atlassian.net/"
proxy_url = "http://proxy.example.com:8080"
```

Notes:

- `proxy_url` has no environment variable. When it is not set, the underlying `requests` library still honors the standard `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY` environment variables; setting `proxy_url` overrides them for Jira API calls.
- `proxy_url` covers the Jira REST API calls, the Atlassian Cloud ID lookup (`/_edge/tenant_info`) and attachment/image downloads. The OAuth 2.0 token requests to `https://auth.atlassian.com/oauth/token` are made through a separate HTTP client that only honors the `HTTPS_PROXY` environment variable — set that as well when using OAuth 2.0 behind a proxy.
- A proxy that terminates TLS (SSL inspection) presents its own certificate. In that case also set `ssl_ca_cert_path` to the proxy's CA bundle, rather than disabling `verify_ssl`.

:::warning[Security]
Embedding proxy credentials in `proxy_url` stores them in plain text in `config.toml`. Prefer a proxy that does not require authentication, or supply the credentialed URL via `HTTPS_PROXY` in the service environment.
:::

### SSL / TLS settings

#### SSL verification (all auth types)

| Setting | Type | Description | Default | Env var |
|---------|------|-------------|---------|---------|
| `verify_ssl` | Boolean | Enable SSL certificate verification. Only set to `false` in dev/test. | `true` | `JIRA_VERIFY_SSL` |
| `ssl_ca_cert_path` | String | Path to CA certificate bundle (`.pem`/`.crt`) for self-signed or corporate CAs | (none) | `JIRA_SSL_CA_CERT_PATH` |

#### Mutual TLS client certificate (all auth types)

| Setting | Type | Description | Env var |
|---------|------|-------------|---------|
| `client_cert_path` | String | Path to client certificate file (`.pem` or `.crt`) | `JIRA_CLIENT_CERT_PATH` |
| `client_key_path` | String | Path to client private key (only needed if separate from cert) | `JIRA_CLIENT_KEY_PATH` |

### Requirements & baselines settings

| Setting | Type | Description | Default |
|---------|------|-------------|---------|
| `baseline_field` | String | Jira field used to identify baselines (e.g. `fixVersions`, `sprint`, or custom field ID) | `fixVersions` |
| `baseline_jql` | String | JQL template for fetching issues of a baseline. Placeholders: `{project}`, `{baseline}` | `project = "{project}" AND fixVersion = "{baseline}" AND issuetype in standardIssueTypes()` |
| `current_baseline_jql` | String | JQL template for the current/active baseline. Placeholder: `{project}` | `project = "{project}" AND issuetype in standardIssueTypes()` |
| `requirement_group_types` | List[String] | Issue types treated as requirement groups/folders | `["Epic"]` |
| `major_change_fields` | List[String] | Fields whose changes count as a major version bump | `["fixVersions"]` |
| `minor_change_fields` | List[String] | Fields whose changes count as a minor version bump | `["summary", "description", "affectsVersions", "status"]` |
| `owner_field` | String | Jira field used as the requirement owner | `assignee` |
| `rendered_fields` | List[String] | Fields to render as HTML in TestBench (must be multiline text in Jira) | `[]` |

### Project-specific overrides

All requirement and baseline settings can be overridden per project.

**Inline in `config.toml`:** Add a `[testbench-requirement-service.reader_config.projects.<project>]` section.

**Separate config file:** Add a `[projects.<project>]` section in your reader config file.

| Setting | Description | Default |
|---------|-------------|---------|
| `baseline_field` | Project-specific baseline field | Inherits from global |
| `baseline_jql` | Project-specific baseline JQL template | Inherits from global |
| `current_baseline_jql` | Project-specific current baseline JQL | Inherits from global |
| `requirement_group_types` | Project-specific group types | Inherits from global |
| `major_change_fields` | Project-specific major change fields | Inherits from global |
| `minor_change_fields` | Project-specific minor change fields | Inherits from global |
| `owner` | Project-specific owner field | Inherits from global |
| `rendered_fields` | Project-specific rendered fields | Inherits from global |


## Authentication

### Basic auth (Jira Cloud)

Recommended for Jira Cloud. Uses your Atlassian account email and an API token.

```toml
# config.toml
[testbench-requirement-service.reader_config]
auth_type  = "basic"
username   = "your-email@company.com"
password  = "your-api-token"
```

Generate an API token at `https://id.atlassian.com/manage-profile/security/api-tokens`.

### Token auth (Jira Data Center)

Uses a Personal Access Token (PAT) generated in your Jira Data Center profile.

```toml
# config.toml
[testbench-requirement-service.reader_config]
auth_type = "token"
token     = "your-personal-access-token"
```

:::note
Personal Access Tokens expire based on the duration set in your Jira Data Center profile. If the service stops authenticating unexpectedly, check whether the token has expired and generate a new one.
:::

### OAuth 2.0 (3LO) auth (Jira Cloud)

Uses an OAuth 2.0 access token obtained via the Atlassian 3-Legged OAuth (3LO) flow. This is recommended when your Atlassian app is registered in the [Atlassian developer console](https://developer.atlassian.com/console/myapps/) and you need delegated user access — every Jira request is made on behalf of the user who granted consent.

```toml
# config.toml
[testbench-requirement-service.reader_config]
auth_type            = "oauth2 3LO (user account)"
oauth2_client_id     = "your-client-id"
oauth2_client_secret = "your-client-secret"
```

#### How to obtain an OAuth 2.0 access token

**Step 1 — Direct the user to the Atlassian authorization URL**

Send the user to the following URL in a browser (GET request). You can construct it manually or copy it from **Authorization → OAuth 2.0 (3LO) → Configure** in the developer console:

```
https://auth.atlassian.com/authorize?
  audience=api.atlassian.com&
  client_id=YOUR_CLIENT_ID&
  scope=read%3Ajira-work%20read%3Ajira-user%20write%3Ajira-work%20offline_access&
  redirect_uri=https://YOUR_APP_CALLBACK_URL&
  state=requirement-service&
  response_type=code&
  prompt=consent
```

| Parameter         | Required       | Description                                                                                                                                               |
| ----------------- | -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `audience`      | Yes            | Always`api.atlassian.com`.                                                                                                                              |
| `client_id`     | Yes            | **Client ID** from your app's **Settings** in the developer console.                                                                          |
| `scope`         | Yes            | Space-separated list of scopes (URL-encoded as`%20`). Only choose scopes already added to your app. See [Required scopes](#required-oauth-scopes) below. |
| `redirect_uri`  | Yes            | Callback URL configured in**Authorization** for your app.                                                                                           |
| `state`         | Yes (security) | An opaque string to prevent CSRF, e.g.`requirement-service`.                                                                                                 |
| `response_type` | Yes            | Must be`code`.                                                                                                                                          |
| `prompt`        | Yes            | Must be`consent` to show the access-grant screen.                                                                                                       |

If the user grants access, Atlassian redirects to `redirect_uri` with an `?code=...` query parameter.

**Step 2 — Exchange the authorization code for an access token**

```bash
curl --request POST \
  --url 'https://auth.atlassian.com/oauth/token' \
  --header 'Content-Type: application/json' \
  --data '{
    "grant_type": "authorization_code",
    "client_id": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "code": "YOUR_AUTHORIZATION_CODE",
    "redirect_uri": "https://YOUR_APP_CALLBACK_URL"
  }'
```

A successful response returns:

```json
{
  "access_token": "<string>",
  "refresh_token":"<string>", 
  "expires_in": 3600,
  "scope": "<string>"
}
```


Run the setup wizard and enter the returned `refresh_token` when prompted. The wizard stores
that token in `tmp/oauth2_tokens.toml`, not in `config.toml`. The service uses the refresh token
to request short-lived access tokens at runtime and updates the cache automatically when they
expire.

Persist only the OAuth client credentials in your configuration (or provide them via environment
variables):

- `oauth2_client_id` (or `JIRA_OAUTH2_CLIENT_ID`) = your client ID
- `oauth2_client_secret` (or `JIRA_OAUTH2_CLIENT_SECRET`) = your client secret

:::note
Do not store OAuth2 access tokens or refresh tokens in `config.toml` or `.env` files. If the refresh
token is revoked or expires, re-run the setup wizard to seed a new `tmp/oauth2_tokens.toml` cache.
Refresh tokens are single-use and expire after 90 days without use.
:::

### OAuth 2.0 (2LO) auth (Jira Cloud)

Uses the Atlassian 2-Legged OAuth (2LO) flow, i.e. the OAuth 2.0 `client_credentials` grant. The service authenticates **as itself** (a service account) instead of on behalf of a user. Choose this for unattended deployments where no user should have to grant consent and no long-lived refresh token has to be maintained.

```toml
# config.toml
[testbench-requirement-service.reader_config]
auth_type            = "oauth2 2LO (service account)"
oauth2_client_id     = "your-client-id"
oauth2_client_secret = "your-client-secret"
```

Or via environment variables:

```bash
export JIRA_OAUTH2_CLIENT_ID=your-client-id
export JIRA_OAUTH2_CLIENT_SECRET=your-client-secret
```

How it differs from 3LO:

| | 2LO (service account) | 3LO (user account) |
|---|---|---|
| Grant type | `client_credentials` | `refresh_token` (after `authorization_code`) |
| Browser consent step | Not needed | Required once |
| Refresh token | Not used | Required, stored in `tmp/oauth2_tokens.toml` |
| Wizard prompts for a token | No | Yes |
| Token cache on disk | No — access tokens are held in memory only | Yes |
| Acts as | The app itself | The consenting user |
| Required settings | `oauth2_client_id`, `oauth2_client_secret` | `oauth2_client_id`, `oauth2_client_secret`, refresh token |

Access tokens are requested from `https://auth.atlassian.com/oauth/token` on first connect and re-minted automatically shortly before they expire, so no manual token rotation is needed. Because nothing is persisted, a restart simply mints a new token.

:::note
2LO requires an Atlassian app that is permitted to use the `client_credentials` grant, with the [required scopes](#required-oauth-scopes) granted to the app itself. If Atlassian rejects the grant, the service fails at startup with `Jira OAuth2 client credentials are not configured` or an authorization error — verify the app type and its scopes in the developer console.
:::

### Required OAuth scopes

The minimum scopes needed by the Requirement Service:

| Scope               | Purpose                                   |
| ------------------- | ----------------------------------------- |
| `read:jira-work`  | Read projects, issues, fields, changelogs |
| `read:jira-user`  | Read user/account information             |
| `write:jira-work` | Create and update issues, field metadata  |

For `readonly = true` deployments, `write:jira-work` can be omitted.

Refer to the Atlassian REST API documentation to confirm which scopes individual endpoints require:

- [Jira Cloud platform REST API](https://developer.atlassian.com/cloud/jira/platform/rest)
- [Jira Software Cloud REST API](https://developer.atlassian.com/cloud/jira/software/rest/intro/)

---


## Example configurations

### Inline TOML (recommended)

```toml
# config.toml
[testbench-requirement-service]
reader_class = "JiraRequirementReader"

[testbench-requirement-service.reader_config]
server_url = "https://example.atlassian.net/"
auth_type = "basic"

# Credentials (alternative to env vars)
# username = "my-user@example.com"
# password = "my-api-token-or-password"

# Connection tuning
# timeout     = 30
# max_retries = 3
# cache_ttl   = 300.0

# Forward proxy for all Jira API requests (optional)
# proxy_url = "http://proxy.example.com:8080"

# Requirement & baseline settings
baseline_field = "fixVersions"
baseline_jql = 'project = "{project}" AND fixVersion = "{baseline}" AND issuetype in standardIssueTypes()'
current_baseline_jql = 'project = "{project}" AND issuetype in standardIssueTypes()'
requirement_group_types = ["Epic"]
major_change_fields = ["fixVersions"]
minor_change_fields = ["summary", "description", "affectsVersions", "status"]
owner_field = "assignee"
rendered_fields = ["Acceptance Criteria", "Technical Specification"]

[testbench-requirement-service.reader_config.projects."Project A"]
baseline_field = "fixVersions"
baseline_jql = 'fixVersion = "{baseline}"'
current_baseline_jql = 'project = "{project}" AND fixVersion = "{baseline}"'
requirement_group_types = ["Initiative"]
owner = "creator"
```

### Separate config file

```toml
# config.toml
[testbench-requirement-service]
reader_class = "JiraRequirementReader"
reader_config_path = "jira_config.toml"
```

```toml
# jira_config.toml (no section prefix)
server_url = "https://example.atlassian.net/"
auth_type = "basic"
# ... same settings as inline example

[projects."Project A"]
baseline_field = "fixVersions"
requirement_group_types = ["Initiative"]
```

### `.env` file

```text
# Basic authentication (Jira Cloud)
JIRA_USERNAME=my-user@example.com
JIRA_PASSWORD=my-api-token

# Token authentication (Jira Server/Data Center)
# JIRA_BEARER_TOKEN=my-personal-access-token

# OAuth1 authentication
# JIRA_OAUTH1_ACCESS_TOKEN=my-access-token
# JIRA_OAUTH1_ACCESS_TOKEN_SECRET=my-access-token-secret
# JIRA_OAUTH1_CONSUMER_KEY=my-consumer-key
# JIRA_OAUTH1_KEY_CERT_PATH=/path/to/private-key.pem

# OAuth2 authentication (2LO and 3LO)
# JIRA_OAUTH2_CLIENT_ID=my-client-id
# JIRA_OAUTH2_CLIENT_SECRET=my-client-secret

# Mutual TLS (optional)
# JIRA_CLIENT_CERT_PATH=/path/to/client.crt
# JIRA_CLIENT_KEY_PATH=/path/to/client.key

# Forward proxy for the OAuth2 token endpoint (auth.atlassian.com).
# Jira API requests use the `proxy_url` reader setting instead.
# HTTPS_PROXY=http://proxy.example.com:8080
```

:::warning
Do not put `JIRA_OAUTH2_REFRESH_TOKEN` in a `.env` file for normal operation — the refresh token rotates on every use and belongs in the runtime cache (`tmp/oauth2_tokens.toml`) that the setup wizard seeds. Only use the environment variable for one-off seeding in automated deployments.
:::

## Testing

### Smoke test

1. Set your Jira credentials (via environment variables or config):
   ```bash
   export JIRA_USERNAME=my-user@example.com
   export JIRA_PASSWORD=my-api-token
   ```

2. Start the server:
   ```bash
   testbench-requirement-service start
   ```

3. Call the `projects` endpoint:
   ```bash
   curl -u "ADMIN_USERNAME:PASSWORD" http://127.0.0.1:8020/projects
   ```

4. Verify that the expected Jira projects are returned.

### Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| `ModuleNotFoundError` | Missing `[jira]` dependencies | Run `pip install testbench-requirement-service[jira]` |
| Connection refused | Wrong `server_url` | Verify the URL is reachable and includes the protocol (`https://`) |
| 401 / 403 from Jira | Invalid or missing credentials | Check that the env vars or config match the selected `auth_type` |
| SSL errors | Self-signed or corporate CA certificate | Set `ssl_ca_cert_path` to your CA bundle, or set `verify_ssl = false` for testing only |
| Timeout errors | Slow Jira instance or network | Increase `timeout` and `max_retries` in config |
| Validation error on `auth_type` | Value not spelled exactly as the allowed literal | Use `basic`, `token`, `oauth1`, `oauth2 2LO (service account)` or `oauth2 3LO (user account)` — see [Authentication methods](#authentication-methods) |
| Connection works, but OAuth2 token refresh times out | Egress to `auth.atlassian.com` is blocked; `proxy_url` does not cover the token endpoint | Set the `HTTPS_PROXY` environment variable for the service process |
| `Jira OAuth2 refresh token is not configured` | 3LO refresh token missing or expired (90 days unused, or revoked) | Re-run `testbench-requirement-service configure` and enter a fresh refresh token |
| `Jira OAuth2 client credentials are not configured` | `oauth2_client_id` / `oauth2_client_secret` missing or still placeholders | Set both in the config or via `JIRA_OAUTH2_CLIENT_ID` / `JIRA_OAUTH2_CLIENT_SECRET` |
| Connection refused / timeout in a corporate network | Direct egress to Jira blocked | Set `proxy_url` to your forward proxy — see [Proxy settings](#proxy-settings) |
