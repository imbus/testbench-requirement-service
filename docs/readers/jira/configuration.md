---
sidebar_position: 2
title: Jira Reader — Configuration
---

## Configuration settings

| Setting | Type | Description | Required | Default |
| --- | --- | --- | --- | --- |
| `server_url` | String | Base URL of the Jira REST API server. | Yes | - |
| `auth_type` | String | Authentication method (`basic`, `token`, `oauth`). | Yes | `basic` |
| `username` | String | Username for Jira authentication (only for `basic` auth when not using environment variables). | No | - |
| `api_token` | String | API token or password for Jira authentication (only for `basic` auth when not using environment variables). | No | - |
| `baseline_field` | String | Field used to identify baselines in Jira. | No | `fixVersions` |
| `baseline_jql` | String | JQL template used to select issues belonging to a specific baseline. Placeholders: `{project}`, `{baseline}`. | No | `project = "{project}" AND fixVersion = "{baseline}" AND issuetype in ("Epic", "Story", "User Story", "Task", "Bug")` |
| `current_baseline_jql` | String | JQL template used to resolve the active/current baseline. Placeholders: `{project}`, `{baseline}`. | No | `project = "{project}" AND issuetype in ("Epic", "Story", "User Story", "Task", "Bug")` |
| `requirement_group_types` | List[String] | Jira issue types considered as requirement groups. | No | `["Epic"]` |
| `major_change_fields` | List[String] | Fields where changes are treated as major changes. | No | `["fixVersions"]` |
| `minor_change_fields` | List[String] | Fields where changes are treated as minor changes. | No | `["summary", "description", "affectsVersions", "status"]` |
| `owner` | String | Field used for the owner. | No | `assignee` |
| `rendered_fields` | List[String] | List of UDF fields that should be shown as rendered fields in the TestBench client (requires multi-line text field type). | No | `[]` |

## Project-specific overrides (`projects.<project>`)

All settings can be overridden per project under `projects.<project>`.

| Setting | Type | Description | Required | Default |
| --- | --- | --- | --- | --- |
| `baseline_field` | String | Project-specific baseline field. | No | Inherits from global Jira config |
| `baseline_jql` | String | Project-specific baseline JQL template. | No | Inherits from global Jira config |
| `current_baseline_jql` | String | Project-specific current baseline JQL template. | No | Inherits from global Jira config |
| `requirement_group_types` | List[String] | Project-specific list of requirement group issue types. | No | Inherits from global Jira config |
| `major_change_fields` | List[String] | Project-specific major change fields. | No | Inherits from global Jira config |
| `minor_change_fields` | List[String] | Project-specific minor change fields. | No | Inherits from global Jira config |
| `owner` | String | Project-specific owner field. | No | Inherits from global Jira config |
| `rendered_fields` | List[String] | Project-specific rendered fields list. | No | Inherits from global Jira config |

## Authentication methods

You can either put credentials into the Jira reader config or provide the matching environment variables.

| auth_type | When to use it | Required values |
| --- | --- | --- |
| `basic` | Atlassian Cloud and many Jira Data Center instances that allow username + API token (or password). | Set `username` and `api_token` in config, or export `JIRA_USERNAME` and `JIRA_API_TOKEN`. |
| `token` | Jira Server/Data Center with Personal Access Tokens and basic auth disabled. | Set `token` in config, or export `JIRA_BEARER_TOKEN`. |
| `oauth` | Enterprise instances requiring OAuth 1.0a with consumer keys and certificates. | Set `access_token`, `access_token_secret`, `consumer_key`, `key_cert` in config, or export `JIRA_ACCESS_TOKEN`, `JIRA_ACCESS_TOKEN_SECRET`, `JIRA_CONSUMER_KEY`, `JIRA_KEY_CERT`. |

## Example configuration (inline TOML)

```toml
[testbench-requirement-service]
reader_class = "JiraRequirementReader"

[testbench-requirement-service.reader_config]
server_url = "https://example.atlassian.net/"
auth_type = "basic"          # or "token" / "oauth"

# Optional authentication directly in config (alternative to env vars)
# username = "my-user@example.com"
# api_token = "my-apitoken"

# Optional: global JQL / field configuration
baseline_field = "fixVersions"
baseline_jql = "project = '{project}' AND fixVersion = '{baseline}' AND issuetype in (\"Epic\", \"Story\", \"User Story\", \"Task\", \"Bug\")"
current_baseline_jql = "project = '{project}' AND issuetype in (\"Epic\", \"Story\", \"User Story\", \"Task\", \"Bug\")"
requirement_group_types = ["Epic"]
major_change_fields = ["fixVersions"]
minor_change_fields = ["summary", "description", "affectsVersions", "status"]
owner = "assignee"
rendered_fields = ["Support Ticket", "Technical criteria", "Acceptance criteria"]

[testbench-requirement-service.reader_config.projects."Project A"]
# Project specific overrides (all optional)
baseline_field = "fixVersions"
baseline_jql = "fixVersion = '{baseline}'"
current_baseline_jql = "project = '{project}' AND fixVersion = '{baseline}'"
requirement_group_types = ["Initiative"]
owner = "creator"
```

## Example `.env` file (basic)

```text
JIRA_USERNAME=my-user@example.com
JIRA_API_TOKEN=my-apitoken
```
