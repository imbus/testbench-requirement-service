---
sidebar_position: 1
title: Config file
---

## Configuration precedence

Highest priority first:

1. Command-line flags (for example `start --host ... --port ... --reader-class ... --reader-config ...`)
2. `config.toml` (or legacy `config.py`)
3. Built-in defaults

## Minimal example (inline reader config)

```toml
[testbench-requirement-service]
reader_class = "JsonlRequirementReader"
host = "127.0.0.1"
port = 8000

[testbench-requirement-service.reader_config]
requirements_path = "requirements/jsonl/"
```

## Separate reader config file

If you want to keep reader configuration in a separate file, set `reader_config_path` and put the reader keys into that file without any section prefix.

## Logging

Optional sections:

- `[testbench-requirement-service.logging.console]`
- `[testbench-requirement-service.logging.file]`

## Related topics

- Authentication: [authentication.md](authentication.md)
- CLI reference: [../cli/commands.md](../cli/commands.md)
