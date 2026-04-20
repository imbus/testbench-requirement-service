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
| `auth_type` | String | Authentication method: `basic`, `token`, or `oauth1` | No | `basic` |
| `timeout` | Integer | HTTP request timeout in seconds (1–300) | No | `30` |
| `max_retries` | Integer | Max retries for failed API requests (0–10) | No | `3` |
| `cache_ttl` | Float | Cache time-to-live in seconds. `0` = disable caching. | No | `300.0` |

### Authentication methods

Pick the authentication flow that matches your Jira deployment. Credentials can be set in the config file or via environment variables.

| `auth_type` | When to use | Required values |
|-------------|-------------|-----------------|
| `basic` | Jira Cloud and Data Center with username + password/API token | `username` + `password` (or `JIRA_USERNAME` + `JIRA_PASSWORD`) |
| `token` | Jira Server/Data Center with Personal Access Tokens | `token` (or `JIRA_BEARER_TOKEN`) |
| `oauth1` | Enterprise instances requiring OAuth 1.0a | `oauth1_access_token`, `oauth1_access_token_secret`, `oauth1_consumer_key`, `oauth1_key_cert_path` (or matching env vars) |

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

# Mutual TLS (optional)
# JIRA_CLIENT_CERT_PATH=/path/to/client.crt
# JIRA_CLIENT_KEY_PATH=/path/to/client.key
```

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
