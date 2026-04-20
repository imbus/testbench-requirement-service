---
sidebar_position: 1
title: Readers
---

# Readers

A **reader** is a pluggable component that fetches projects, baselines, and requirements from a specific data source. The service ships with three built-in readers and supports [custom readers](custom.md).

## Built-in readers

| Reader | Data source | Extra dependencies | Best for |
|--------|------------|-------------------|----------|
| [**JSONL**](jsonl.md) | `.jsonl` files on disk | None (included in base install) | Simple file-based requirements, CI pipelines, testing |
| [**Excel**](excel.md) | `.xlsx`, `.xls`, `.csv`, `.tsv`, `.txt` files | `pip install testbench-requirement-service[excel]` | Spreadsheet-based requirement management |
| [**Jira**](jira.md) | Jira REST API | `pip install testbench-requirement-service[jira]` | Teams managing requirements in Jira as issues |

## Choosing a reader

### JSONL Reader

The **default reader**, so no extra installation is needed. Use this when:
- Your requirements are exported or generated as JSON Lines files.
- You want the simplest possible setup with no external dependencies.
- You need a well-defined JSON schema for automation.

**Get started:** [JSONL Reader](jsonl.md)

---

### Excel Reader

Reads from Excel workbooks and delimited text files. Use this when:
- Your requirements live in `.xlsx`, `.xls`, `.csv`, `.tsv`, or `.txt` files.
- You need flexible column mapping to match your spreadsheet layout.
- You want to be able to override the configuration for a project using `.properties` files.

Supports dataframe buffering for performance with large files.

**Get started:** [Excel Reader](excel.md)

---

### Jira Reader

Connects to Jira Cloud or Jira Data Center via the REST API. Use this when:
- Your requirements are managed as Jira issues (Epics, Stories, Tasks, etc.).
- You need live access to Jira without manual exports.
- You want per-project JQL customization and field mapping.

Supports multiple authentication methods (Basic, PAT, OAuth1) and SSL/mTLS.

**Get started:** [Jira Reader](jira.md)

---

### Custom Reader

None of the built-in readers fit? You can create your own by subclassing `AbstractRequirementReader`.

**Learn how:** [Custom Readers](custom.md)

## Configuring a reader

Set `reader_class` in your `config.toml` and provide reader-specific settings under `[testbench-requirement-service.reader_config]`:

```toml
# config.toml
[testbench-requirement-service]
reader_class = "JsonlRequirementReader"   # or ExcelRequirementReader, JiraRequirementReader

[testbench-requirement-service.reader_config]
# reader-specific settings go here
```

Alternatively, keep reader settings in a separate file using `reader_config_path`:

```toml
# config.toml
[testbench-requirement-service]
reader_class = "JiraRequirementReader"
reader_config_path = "jira_config.toml"
```

```toml
# jira_config.toml
# reader-specific settings go here
```

See the [Configuration](../configuration.md#service-settings) reference for details.
