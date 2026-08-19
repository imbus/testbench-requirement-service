---
sidebar_position: 7
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
| [`migrate`](#migrate) | Convert a legacy `.conf` / `.properties` configuration into a TOML configuration. |
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

## `migrate`

Convert a legacy `.conf` / `.properties` configuration into a TOML configuration file.

The previous TestBench requirement wrappers were configured with a Jira `.conf` file or an
Excel `.properties` file. `migrate` reads one of those, asks for the settings the legacy
format never carried - how to authenticate against Jira, and the credentials that protect
the service's own API - and writes a ready-to-use configuration file.

The converted values are validated against the same reader models the service uses at
startup, so anything the service would reject is reported during the migration instead of
on the first start.

```bash
testbench-requirement-service migrate --from PATH [OPTIONS]
```

:::tip
The [Migration guide](migration.md) walks through the whole procedure — which legacy keys
are carried over, what you are asked for, and how to reconnect TestBench afterwards.
:::

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--from PATH` | Legacy `.conf` or `.properties` file to convert (required) | - |
| `--path PATH` | Path to the configuration file to write | `config.toml` |
| `--type [excel\|jira]` | Legacy source type | detected from the file extension |

The source type follows from the extension: `.conf` is a Jira wrapper configuration,
`.properties` an Excel one. Pass `--type` when the file has been renamed and the extension
no longer says which format it is.

### Examples

```bash
# Convert a legacy Jira wrapper configuration
testbench-requirement-service migrate --from jira.conf

# Convert a legacy Excel wrapper configuration to a custom path
testbench-requirement-service migrate --from genericexcel.properties --path /etc/requirement-service/config.toml

# Convert a wrapper file whose extension no longer identifies the format
testbench-requirement-service migrate --from wrapper.txt --type jira
```

:::info[Existing configurations]
If the target file already exists you are asked to confirm, and it is renamed to
`config.toml.backup` (timestamped when a backup is already present) before the new file is
written. The conversion runs to completion first, so cancelling any prompt leaves your
existing configuration exactly as it was.
:::

:::note
Only the Jira and Excel readers have a legacy wrapper format to migrate from. Configure the
JSONL and SQL readers with [`init`](#init) or [`configure`](#configure).
:::

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

