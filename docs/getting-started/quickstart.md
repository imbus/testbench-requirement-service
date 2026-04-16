---
sidebar_position: 2
title: Quickstart
---

# Quickstart

> **New users?** Use [Option 1: Interactive Wizard](#option-1-interactive-wizard-recommended) for the fastest setup.
>
> **Advanced users?** See [Option 2: Manual Configuration](#option-2-manual-configuration) for full control.

## Option 1: Interactive Wizard (Recommended)

### 1. Create a configuration

```bash
testbench-requirement-service init
```

This single command walks you through:
- [Service settings](../configuration.md#server) (host, port, debug mode)
- [Credentials setup](../configuration.md#authentication) (username, password)
- Reader selection ([JSONL](../readers/jsonl.md), [Excel](../readers/excel.md), [Jira](../readers/jira.md), or [Custom](../readers/custom.md))
- Reader-specific configuration (see the chosen reader's Configuration section)

It creates a complete `config.toml` when finished.

### 2. Start the service

```bash
testbench-requirement-service start
```

### 3. Open Swagger UI

Visit [http://127.0.0.1:8020/docs](http://127.0.0.1:8020/docs) to explore the API interactively.

### 4. Quick API check

```bash
curl -u "ADMIN_USERNAME:PASSWORD" http://127.0.0.1:8020/projects
```

**That's it!** Your service is ready to use.

---

## Option 2: Manual Configuration

### 1. Install optional dependencies (if needed)

Choose the extras for your data source. See [Installation](installation.md#from-pypi-online-recommended) for available options.

### 2. Create the configuration file

Create a new file called `config.toml` in the root directory of your installation. Start from this minimal example for the JSONL reader:

```toml
# config.toml
[testbench-requirement-service]
reader_class = "JsonlRequirementReader"
host = "127.0.0.1"
port = 8020

[testbench-requirement-service.reader_config]
requirements_path = "requirements/jsonl/"
```

For other readers see [JSONL](../readers/jsonl.md), [Excel](../readers/excel.md), or [Jira](../readers/jira.md).

### 3. Set credentials

The API uses HTTP Basic Auth. Generate a hashed password:

```bash
testbench-requirement-service set-credentials
```

This prompts for username and password and stores a secure hash in `config.toml`.

### 4. Start the service

```bash
testbench-requirement-service start
```

### 5. Open Swagger UI

Visit [http://127.0.0.1:8020/docs](http://127.0.0.1:8020/docs).

### 6. Quick API check

```bash
curl -u "ADMIN_USERNAME:PASSWORD" http://127.0.0.1:8020/projects
```

---

## API documentation endpoints

Once the service is running, these endpoints are available without authentication:

| Endpoint | Description |
|----------|-------------|
| `/docs` | Interactive Swagger UI |
| `/docs/openapi.json` | OpenAPI specification (JSON) |
| `/openapi.yaml` | OpenAPI specification (YAML) |

:::tip
Use `testbench-requirement-service configure` to update specific parts of your configuration later without starting from scratch.
:::

## Next steps

- Customize the service → [Configuration](../configuration.md)
- Learn about readers → [Readers overview](../readers/index.md)
- Connect TestBench → [TestBench Integration](../testbench-integration.md)
- Explore all CLI options → [CLI commands](../cli-commands.md)
