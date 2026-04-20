---
sidebar_position: 6
title: CLI Commands
---

# CLI Commands

The executable is `testbench-requirement-service`. All commands support `--help` for detailed usage.

```bash
testbench-requirement-service [COMMAND] [OPTIONS]
```

---

## Commands overview

| Command | Description |
|---|---|
| [`init`](#init) | Interactive wizard to create a new configuration file from scratch. |
| [`configure`](#configure) | Create or update an existing configuration interactively. |
| [`set-credentials`](#set-credentials) | Set the service username and password. |
| [`start`](#start) | Start the requirement service. |

---

## `init`

Create a new configuration file with an interactive wizard.

The wizard guides you through:
1. Service settings (host, port)
2. Credential setup (username, password)
3. Reader selection (JSONL, Excel, Jira, or Custom)
4. Reader-specific configuration

```bash
testbench-requirement-service init [--path PATH]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--path PATH` | Path to the configuration file to create | `config.toml` |

### Examples

```bash
# Create config.toml in the current directory
testbench-requirement-service init

# Create config at a custom path
testbench-requirement-service init --path /etc/requirement-service/config.toml
```

---

## `configure`

Update an existing configuration file interactively.

```bash
testbench-requirement-service configure [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--path PATH` | Path to the app configuration file (default: `config.toml`) |
| `--full` | Run the full configuration wizard (skip the menu) |
| `--service-only` | Configure service settings only (host, port, debug) |
| `--credentials-only` | Configure credentials only (username, password) |
| `--reader-only` | Configure reader settings only |
| `--view` | View the current configuration |

### Examples

```bash
# Interactive menu (default)
testbench-requirement-service configure

# Update only service settings
testbench-requirement-service configure --service-only

# View current configuration
testbench-requirement-service configure --view
```

---

## `set-credentials`

Set or update the HTTP Basic Auth credentials used to protect API endpoints. 
This command generates a secure password hash and salt and stores them in your configuration file.

```bash
testbench-requirement-service set-credentials [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--path PATH` | Path to the app configuration file (default: `config.toml`) |
| `--username TEXT` | Username (prompts interactively if not provided) |
| `--password TEXT` | Password (prompts interactively if not provided) |

### Examples

```bash
# Interactive (prompts for credentials)
testbench-requirement-service set-credentials

# Non-interactive
testbench-requirement-service set-credentials --username admin --password mypassword
```

---

## `start`

Start the TestBench Requirement Service.

```bash
testbench-requirement-service start [OPTIONS]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--config PATH` | Path to the app configuration file | `config.toml` |
| `--reader-class TEXT` | Reader class name or module path (overrides config) | from config |
| `--reader-config PATH` | Path to reader configuration file (overrides config) | from config |
| `--host HOST` | Host to bind to | `127.0.0.1` |
| `--port PORT` | Port to listen on | `8020` |
| `--dev` | Run in development mode (debug + auto reload) | off |
| `--ssl-cert PATH` | Path to SSL certificate file for HTTPS | — |
| `--ssl-key PATH` | Path to SSL private key file for HTTPS | — |
| `--ssl-ca-cert PATH` | Path to CA certificate file for client verification (mTLS) | — |

Command-line arguments take **precedence** over configuration file settings.

:::info[Built-in reader class names]
When using `--reader-class`, you can specify:
- `JsonlRequirementReader` — for JSONL files
- `ExcelRequirementReader` — for Excel/CSV files
- `JiraRequirementReader` — for Jira API

Or provide a custom reader (e.g. `custom_reader.py` or `custom_reader.CustomClass`).
:::

### Examples

```bash
# Start with defaults
testbench-requirement-service start

# Development mode
testbench-requirement-service start --dev

# Override host and port
testbench-requirement-service start --host 0.0.0.0 --port 9000

# Use a different reader
testbench-requirement-service start --reader-class JiraRequirementReader --reader-config jira_config.toml

# Use a custom reader class
testbench-requirement-service start --reader-class custom_reader.CustomRequirementReader

# Start with HTTPS
testbench-requirement-service start --ssl-cert certs/server.crt --ssl-key certs/server.key

# Start with mutual TLS (mTLS)
testbench-requirement-service start --ssl-cert certs/server.crt --ssl-key certs/server.key --ssl-ca-cert certs/ca.crt
```

---

## Getting help

```bash
# General help
testbench-requirement-service --help

# Help for a specific command
testbench-requirement-service start --help
testbench-requirement-service configure --help
```

