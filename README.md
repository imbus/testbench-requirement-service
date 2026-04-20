# TestBench Requirement Service

[![PyPI version](https://img.shields.io/pypi/v/testbench-requirement-service)](https://pypi.org/project/testbench-requirement-service/)
[![Python versions](https://img.shields.io/pypi/pyversions/testbench-requirement-service)](https://pypi.org/project/testbench-requirement-service/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](https://github.com/imbus/testbench-requirement-service/blob/main/LICENSE)

A lightweight REST API service for [imbus TestBench](https://www.testbench.com) that provides unified access to requirements from multiple data sources: Jira, Excel, and JSONL.

## Features

- **Multiple readers**: JSONL files, Excel spreadsheets (`.xlsx`, `.xls`, `.csv`, `.tsv`, `.txt`), or Jira via REST API
- **Unified REST API**: one consistent API surface regardless of the underlying data source
- **Interactive setup wizard**: `testbench-requirement-service init` generates a complete configuration in seconds
- **Swagger UI**: built-in interactive API docs at `/docs`
- **HTTPS & mTLS**: optional TLS and mutual TLS for production deployments
- **Windows service support**: deploy as a service with NSSM, FireDaemon, or YAJSW
- **Extensible**: implement `AbstractRequirementReader` to connect any data source

## Installation

**With pip** (Python 3.10–3.14 required):

```bash
pip install testbench-requirement-service
```

Optional extras for additional readers:

| Reader | Data source | Install command |
|--------|-------------|-----------------|
| JSONL *(default)* | `.jsonl` files | included in base install |
| Excel | `.xlsx`, `.xls`, `.csv`, `.tsv`, `.txt` | `pip install testbench-requirement-service[excel]` |
| Jira | Jira REST API | `pip install testbench-requirement-service[jira]` |

**Standalone executable** — no Python required. Download the pre-built binary from the [GitHub releases page](https://github.com/imbus/testbench-requirement-service/releases).

## Quick start

```bash
# 1. Create a configuration interactively
testbench-requirement-service init

# 2. Start the service
testbench-requirement-service start
```

The service runs at `http://127.0.0.1:8020` by default. Open `/docs` for the interactive Swagger UI.

## Documentation

Full documentation is available on the [TestBench Ecosystem documentation site](https://imbus.github.io/testbench-ecosystem-documentation/testbench-requirement-service/intro):

- [Introduction](https://imbus.github.io/testbench-ecosystem-documentation/testbench-requirement-service/intro)
- [Installation](https://imbus.github.io/testbench-ecosystem-documentation/testbench-requirement-service/getting-started/installation)
- [Quickstart](https://imbus.github.io/testbench-ecosystem-documentation/testbench-requirement-service/getting-started/quickstart)
- [Configuration](https://imbus.github.io/testbench-ecosystem-documentation/testbench-requirement-service/configuration)
- [CLI Commands](https://imbus.github.io/testbench-ecosystem-documentation/testbench-requirement-service/cli-commands)
- [Readers overview](https://imbus.github.io/testbench-ecosystem-documentation/testbench-requirement-service/readers/)
- [TestBench Integration](https://imbus.github.io/testbench-ecosystem-documentation/testbench-requirement-service/testbench-integration)
- [Windows Service Installation](https://imbus.github.io/testbench-ecosystem-documentation/testbench-requirement-service/windows-service-installation)

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](https://github.com/imbus/testbench-requirement-service/blob/main/CONTRIBUTING.md) for setup instructions and guidelines.

## Changelog

See [CHANGELOG.md](https://github.com/imbus/testbench-requirement-service/blob/main/CHANGELOG.md) for release history.

## License

Apache 2.0 — see [LICENSE](https://github.com/imbus/testbench-requirement-service/blob/main/LICENSE) for details.
