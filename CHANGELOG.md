# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0] - 2026-07-27

### Added
- Jira reader: OAuth 2.0 (3LO) authentication (`auth_type = "oauth2"`) for Jira Cloud, using a refresh token to obtain and rotate short-lived access tokens at runtime.
  - New config fields: `oauth2_client_id`, `oauth2_client_secret`, `oauth2_refresh_token`, `oauth2_access_token` (legacy), and `oauth2_expires_at`, each also settable via `JIRA_OAUTH2_*` environment variables.
  - Setup wizard prompts for the OAuth2 refresh token and stores it in a runtime cache (`tmp/oauth2_tokens.toml`) rather than in `config.toml`; only the client ID/secret are persisted in configuration.
  - The service prompts for a missing refresh token on startup when OAuth2 is configured and no token is cached.
  - Automatic access-token refresh against `https://auth.atlassian.com/oauth/token`, with token cache persisted atomically to disk and a clear error prompting re-authorization when the refresh token is expired or revoked.
- Jira reader: support for Jira scoped API tokens via the Atlassian API gateway (`https://api.atlassian.com/ex/jira/{cloud_id}`), including automatic Cloud ID resolution.
- Jira reader: mutual TLS client-certificate support (`client_cert_path`, `client_key_path` / `JIRA_CLIENT_CERT_PATH`, `JIRA_CLIENT_KEY_PATH`) across all auth types.
- Documentation for OAuth 2.0 (3LO) setup, required scopes, and the client-certificate options in `docs/readers/jira.md`.
- Unit tests for the Jira OAuth2 token handling (`tests/unit/readers/jira/test_jira_oauth.py`).

### Changed
- Jira reader: requirement links now use the connected Jira site URL (`jira_client.site_url`) instead of the raw configured `server_url`, so links are correct when connecting through the gateway.
- Jira reader: added progress and diagnostic debug logging when processing user-defined attributes.

[1.1.0]: https://github.com/imbus/testbench-requirement-service/compare/v1.0.0...v1.1.0

## [1.0.0] - 2026-04-20

### Added
- JSONL reader — serve requirements from `.jsonl` files (included in base install)
- Excel reader — supports `.xlsx`, `.xls`, `.csv`, `.tsv`, `.txt` (optional extra: `[excel]`)
- Jira reader — connects to Jira REST API (optional extra: `[jira]`)
- Unified REST API surface regardless of the underlying data source
- Interactive setup wizard (`testbench-requirement-service init`) for guided configuration generation
- `configure` CLI command to update an existing configuration interactively
- `set-credentials` CLI command to manage HTTP Basic Auth username and password
- CLI entry point `testbench-requirement-service start` with `--help` on all commands
- HTTP Basic Auth support
- HTTPS and mutual TLS (mTLS) support for production deployments
- Extensible reader interface — implement `RequirementReader` to connect any custom data source
- Built-in Swagger UI at `/docs` for interactive API exploration
- Windows service installation support
- Initial documentation under `docs/`

[1.0.0]: https://github.com/imbus/testbench-requirement-service/releases/tag/v1.0.0
