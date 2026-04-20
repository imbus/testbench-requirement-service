# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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
