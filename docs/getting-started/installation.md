---
sidebar_position: 1
title: Installation
---

# Installation

## Requirements

- **Python 3.10** or higher
- **pip** (included with Python)

## Install from PyPI

```bash
pip install testbench-requirement-service
```

This installs the base package with the [JSONL reader](../readers/jsonl.md), with no extra dependencies needed.

## Optional extras

Install additional dependency groups for the reader you need:

| Reader | Data source | Install command |
|--------|-------------|-----------------|
| [JSONL](../readers/jsonl.md) *(default)* | `.jsonl` files | Included in base install |
| [Excel](../readers/excel.md) | `.xlsx`, `.xls`, `.csv`, `.tsv`, `.txt` | `pip install testbench-requirement-service[excel]` |
| [Jira](../readers/jira.md) | Jira REST API | `pip install testbench-requirement-service[jira]` |

Install multiple extras at once:

```bash
pip install testbench-requirement-service[excel,jira]
```

## Verify the installation

```bash
testbench-requirement-service --version
```

If the installation was successful, this prints the installed version.

You can also run:

```bash
testbench-requirement-service --help
```

## Next steps

Head to the [Quickstart](quickstart.md) to configure and start the service.
