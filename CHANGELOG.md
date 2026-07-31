# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-07-30

### Added
- Jira reader: OAuth 2.0 2LO (service account) authentication via `auth_type = "oauth2 2LO (service account)"`, using the `client_credentials` grant. Access tokens are minted from `oauth2_client_id`/`oauth2_client_secret` alone and re-minted automatically — no user consent, no refresh token and no token cache on disk.
- Jira reader: `proxy_url` setting to route all Jira API requests through a forward proxy (e.g. `http://proxy.example.com:8080`). The OAuth 2.0 token endpoint is not covered by it and honors the `HTTPS_PROXY` environment variable instead.
- Documentation for the 2LO flow, the complete set of OAuth 2.0 settings, and the proxy setting in `docs/readers/jira.md` and `examples/jira_config.toml`.
- Jira: OAuth 2.0 3LO support for Jira Data Center — automatic Data Center
  detection, token requests against `{server_url}/rest/oauth2/1.0/token`
  (form-encoded, PKCE authorization-code exchange in the setup wizard), and
  API requests sent directly to the configured server URL instead of the
  Atlassian gateway.
- Jira: the short `auth_type` values `"oauth2 2LO"` and `"oauth2 3LO"` are
  accepted as aliases for the descriptive long forms.
- Documentation for OAuth 2.0 on Jira Data Center (automatic detection, the
  wizard's authorization-code exchange, troubleshooting) and the short
  `auth_type` aliases in `docs/readers/jira.md` and `examples/jira_config.toml`.

### Changed
- Jira reader: the OAuth 2.0 `auth_type` value was split into `oauth2 2LO (service account)` and `oauth2 3LO (user account)`. The previous value `oauth2` is no longer accepted — existing configurations using it must be updated to `oauth2 3LO (user account)`.

### Fixed
- Jira reader: `proxy_url` was passed to the `jira` package as an `options` entry, which that package ignores, so the proxy was not applied to any Jira REST request. It is now passed as the `proxies` constructor argument.
- Jira reader: removed a reference to a non-existent `oauth2_access_token` config field that could raise `AttributeError` when connecting with OAuth 2.0.
- Configuration wizard: `oauth2_client_secret` and other `*client_secret*` keys are now masked in the "view configuration" output instead of being printed in plain text.
- Jira reader: the startup prompt for a missing OAuth 2.0 refresh token now triggers for the 3LO auth type (it compared against the obsolete `"oauth2"` value and therefore never fired).
- Configuration wizard: the prompts for `oauth2_client_id`, `oauth2_client_secret` and `oauth2_refresh_token` were skipped when one of the descriptive auth-type labels (`oauth2 2LO (service account)` / `oauth2 3LO (user account)`) was selected, so the wizard finished with "Jira OAuth2 client credentials must be provided". The prompts now fire for both the short and the descriptive labels.
- Configuration wizard: the OAuth 2.0 refresh-token wizard is now given the collected reader configuration, so the Jira Data Center authorization-code exchange can use the just-entered `server_url` and client credentials instead of always reporting that they are missing.

## [1.1.0] - 2026-07-27

### Added
- Jira reader: OAuth 2.0 (3LO) authentication for Jira Cloud, using a refresh token to obtain and rotate short-lived access tokens at runtime.
  - New config fields: `oauth2_client_id`, `oauth2_client_secret`, `oauth2_refresh_token` and `oauth2_expires_at`, each also settable via `JIRA_OAUTH2_*` environment variables.
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

[1.2.0]: https://github.com/imbus/testbench-requirement-service/releases/tag/v1.0.0
[1.1.0]: https://github.com/imbus/testbench-requirement-service/releases/tag/v1.0.0
[1.0.0]: https://github.com/imbus/testbench-requirement-service/releases/tag/v1.0.0
