---
sidebar_position: 2
title: Quickstart
---

## 1) Create a config

Use the interactive wizard (creates `config.toml`):

```bash
testbench-requirement-service init
```

If you prefer editing manually, start from the minimal config in the JSONL reader setup:

- JSONL: see [../readers/jsonl/setup.md](../readers/jsonl/setup.md)

## 2) Set credentials

The API uses HTTP Basic Auth for endpoints like `/projects`.

```bash
testbench-requirement-service set-credentials
```

## 3) Start the server

```bash
testbench-requirement-service start
```

Open Swagger UI at `http://127.0.0.1:8000/docs`.

## 4) Quick API check

```bash
curl -u "admin:mypassword" http://127.0.0.1:8000/projects
```

## Next steps

- Configuration reference: [../configuration/config-file.md](../configuration/config-file.md)
- Reader selection: [../readers/jsonl/setup.md](../readers/jsonl/setup.md), [../readers/excel/setup.md](../readers/excel/setup.md), [../readers/jira/setup.md](../readers/jira/setup.md)
