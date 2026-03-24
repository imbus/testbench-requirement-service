---
sidebar_position: 1
title: Installation
---

## Requirements

- Python >= 3.10
- `pip`

## Install from PyPI

```bash
python -m pip install testbench-requirement-service
```

## Optional: install extras

Excel/text-file reader dependencies:

```bash
python -m pip install "testbench-requirement-service[excel]"
```

Jira reader dependencies:

```bash
python -m pip install "testbench-requirement-service[jira]"
```

Both:

```bash
python -m pip install "testbench-requirement-service[excel,jira]"
```

## Verify installation

```bash
testbench-requirement-service --help
```
