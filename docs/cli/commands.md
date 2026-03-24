---
sidebar_position: 1
title: Commands
---

The executable is `testbench-requirement-service`.

## Common commands

- `init`: interactive wizard to create a config
- `configure`: update an existing config interactively
- `set-credentials`: set HTTP Basic Auth credentials
- `start`: run the server

## Examples

Create a new config:

```bash
testbench-requirement-service init
```

Start the server:

```bash
testbench-requirement-service start
```

Start with overrides:

```bash
testbench-requirement-service start --host 0.0.0.0 --port 9000
```

Show all options:

```bash
testbench-requirement-service --help
testbench-requirement-service start --help
```
