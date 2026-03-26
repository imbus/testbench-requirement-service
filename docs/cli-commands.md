---
sidebar_position: 6
title: CLI Commands
---

# CLI Commands

The executable is `testbench-requirement-service`. All commands support `--help` for detailed usage.

## `init`

Initialize a new configuration file with an interactive wizard.

```bash
testbench-requirement-service init [--path PATH]
```

| Option | Description | Default |
|--------|-------------|---------|
| `--path PATH` | Path to the configuration file to create | `config.toml` |

The wizard guides you through:
1. Service settings (host, port, debug mode)
2. Credential setup (username, password)
3. Reader selection (JSONL, Excel, Jira, or Custom)
4. Reader-specific configuration

## `configure`

Update an existing configuration file interactively.

```bash
testbench-requirement-service configure [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--path PATH` | Path to the app configuration file (default: `config.toml`) |
| `--full` | Run the full configuration wizard (skip the menu) |
| `--service-only` | Configure service settings only (host, port, debug) |
| `--credentials-only` | Configure credentials only (username, password) |
| `--reader-only` | Configure reader settings only |
| `--view` | View the current configuration |

**Examples:**

```bash
# Interactive menu (default)
testbench-requirement-service configure

# Update only service settings
testbench-requirement-service configure --service-only

# View current configuration
testbench-requirement-service configure --view
```

## `set-credentials`

Set or update the HTTP Basic Auth credentials used to protect API endpoints.

```bash
testbench-requirement-service set-credentials [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--path PATH` | Path to the app configuration file (default: `config.toml`) |
| `--username TEXT` | Username (prompts interactively if not provided) |
| `--password TEXT` | Password (prompts interactively if not provided) |

This command generates a secure password hash and salt and stores them in your configuration file.

**Examples:**

```bash
# Interactive (prompts for credentials)
testbench-requirement-service set-credentials

# Non-interactive
testbench-requirement-service set-credentials --username admin --password mypassword
```

## `start`

Start the TestBench Requirement Service.

```bash
testbench-requirement-service start [OPTIONS]
```

| Option | Description | Default |
|--------|-------------|---------|
| `--config PATH` | Path to the app configuration file | `config.toml` |
| `--reader-class TEXT` | Reader class name or module path (overrides config) | from config |
| `--reader-config PATH` | Path to reader configuration file (overrides config) | from config |
| `--host HOST` | Host to bind to | `127.0.0.1` |
| `--port PORT` | Port to listen on | `8020` |
| `--dev` | Run in development mode (debug + auto reload) | off |

Command-line arguments take **precedence** over configuration file settings.

**Examples:**

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
```

## Quick reference

| Command | Purpose |
|---------|---------|
| `init` | Create a new config from scratch |
| `configure` | Update parts of an existing config |
| `set-credentials` | Set HTTP Basic Auth username & password |
| `start` | Run the service |
| `--version` | Print the installed version |
| `--help` | Show top-level help |
