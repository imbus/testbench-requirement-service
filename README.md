# TestBench Requirement Service

A lightweight REST API service for [imbus TestBench](https://www.imbus.de/en/testbench) that provides unified access to requirements from multiple data sources — Jira, Excel, and JSONL.

## Features

- **Multiple readers** — read from JSONL files, Excel spreadsheets (`.xlsx`, `.xls`, `.csv`, `.tsv`, `.txt`), or Jira via REST API
- **Unified REST API** — single API surface regardless of the underlying data source
- **Interactive setup wizard** — generate a complete config in seconds with `testbench-requirement-service init`
- **Swagger UI** — built-in interactive API docs at `/docs`
- **HTTPS & mTLS** — optional TLS termination and mutual TLS for production deployments
- **Extensible** — implement your own `RequirementReader` to connect any data source

## Requirements

- Python 3.10+

## Installation

```bash
pip install testbench-requirement-service
```

Install optional extras for your data source:

| Reader | Data source | Install command |
|--------|-------------|-----------------|
| JSONL *(default)* | `.jsonl` files | included in base install |
| Excel | `.xlsx`, `.xls`, `.csv`, `.tsv`, `.txt` | `pip install testbench-requirement-service[excel]` |
| Jira | Jira REST API | `pip install testbench-requirement-service[jira]` |

You can combine extras: `pip install testbench-requirement-service[excel,jira]`

## Quick start

**1. Create a configuration** (interactive wizard):

```bash
testbench-requirement-service init
```

The wizard guides you through service settings, credentials, and reader selection, and creates a complete `config.toml`.

**2. Start the service:**

```bash
testbench-requirement-service start
```

The service runs at `http://127.0.0.1:8020` by default. Open `/docs` for the interactive Swagger UI.

## CLI reference

| Command | Purpose |
|---------|---------|
| `init` | Create a new config from scratch |
| `configure` | Update an existing config interactively |
| `set-credentials` | Set HTTP Basic Auth username & password |
| `start` | Run the service |
| `--version` | Print the installed version |

Run any command with `--help` for full usage details.

## Documentation

Full documentation is available in the [`docs/`](docs/) folder:

- [Introduction](docs/intro.md)
- [Installation](docs/getting-started/installation.md)
- [Quickstart](docs/getting-started/quickstart.md)
- [Configuration](docs/configuration.md)
- [CLI Commands](docs/cli-commands.md)
- [Readers overview](docs/readers/index.md) — JSONL, Excel, Jira, Custom
- [TestBench Integration](docs/testbench-integration.md)
- [Windows Service Installation](docs/windows-service-installation/index.md)

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
