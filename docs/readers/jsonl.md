---
sidebar_position: 2
title: JSONL Reader
---

# JSONL Reader

The JSONL reader is the **default reader**. It reads requirements from [JSON Lines](https://jsonlines.org/) (`.jsonl`) files stored on disk. No extra dependencies are required.

**When to use:** Your requirements are exported or generated as `.jsonl` files, or you want the simplest setup with no external dependencies.

## Installation

No extra dependencies required; it is included in the base package.

## Setup

1. Create a root directory for your requirements (e.g. `requirements/jsonl/`).
2. Inside it, create one subdirectory per **project**.
3. Place one or more `.jsonl` baseline files inside each project directory.
4. Place a `UserDefinedAttributes.json` file at the top level of the requirements directory.

**Directory layout example:**

```
requirements/jsonl/
├── UserDefinedAttributes.json
├── ProjectA/
│   ├── Baseline_v1.jsonl
│   └── Baseline_v2.jsonl
└── ProjectB/
    └── Release_1.0.jsonl
```

## Configuration

The configuration can be added directly to `config.toml` under `[testbench-requirement-service.reader_config]` (recommended) or in a separate `.toml` file without a section prefix.

### Configuration settings

| Setting | Type | Description | Required | Default |
|---------|------|-------------|----------|---------|
| `requirements_path` | String | Path to the directory containing the requirement files | Yes | (none) |

### Minimal configuration

```toml
# config.toml
[testbench-requirement-service]
reader_class = "JsonlRequirementReader"

[testbench-requirement-service.reader_config]
requirements_path = "requirements/jsonl/"
```

Or use a separate reader config file:

```toml
# config.toml
[testbench-requirement-service]
reader_class = "JsonlRequirementReader"
reader_config_path = "reader_config.toml"
```

```toml
# reader_config.toml
requirements_path = "requirements/jsonl/"
```

## Required data layout

| Concept | Location | Description |
|---------|----------|-------------|
| **Projects** | Top-level directories inside `requirements_path` | Each directory is a project |
| **Baselines** | `.jsonl` files inside a project directory | Each file is a baseline |
| **Requirements** | JSON objects (one per line) in a `.jsonl` file | Each line is a requirement or folder node |
| **User-defined attributes** | `UserDefinedAttributes.json` at the top of `requirements_path` | Defines available types of user defined fields (UDF)|

## Requirement JSON schema

Each line in a baseline `.jsonl` file is a JSON object representing either a requirement or a structural node (folder/group).

- If `"requirement"` is `true` → the object is an actual requirement.
- If `"requirement"` is `false` → the object is a folder/group in the tree.
- Root objects have `"parent"` set to `null`.

```json
{
    "name": "string",
    "extendedID": "string",
    "key": {
        "id": "string",
        "version": {
            "name": "string",
            "date": "string <date-time>",
            "author": "string",
            "comment": "string"
        }
    },
    "owner": "string",
    "status": "string",
    "priority": "string",
    "requirement": true,
    "description": "string",
    "documents": ["string"],
    "parent": "string | null",
    "userDefinedAttributes": [
        {
            "name": "string",
            "valueType": "STRING | ARRAY | BOOLEAN",
            "stringValue": "string",
            "stringValues": ["string"],
            "booleanValue": true
        }
    ]
}
```

### Fields reference

| Field | Type | Description |
|-------|------|-------------|
| `name` | String | Requirement name |
| `extendedID` | String | Extended ID |
| `key.id` | String | Unique identifier |
| `key.version` | Object | Version info: `name`, `date`, `author`, `comment` |
| `owner` | String | Responsible person |
| `status` | String | Requirement status |
| `priority` | String | Priority level |
| `requirement` | Boolean | `true` = requirement, `false` = folder/group |
| `description` | String | Requirement description |
| `documents` | List[String] | Attached document references |
| `parent` | String or null | Parent node ID (`null` for roots) |
| `userDefinedAttributes` | List[Object] | User-defined fields (see below) |

## UserDefinedAttributes.json

This file at the top level of `requirements_path` defines which UDFs exist and their value types:

```json
[
    { "name": "Risk", "valueType": "STRING" },
    { "name": "Units", "valueType": "ARRAY" },
    { "name": "In Scope", "valueType": "BOOLEAN" }
]
```

Supported `valueType` values: `STRING`, `ARRAY`, `BOOLEAN`.

## Testing

### Smoke test

1. Start the server:
   ```bash
   testbench-requirement-service start
   ```

2. Call the projects endpoint:
   ```bash
   curl -u "ADMIN_USERNAME:PASSWORD" http://127.0.0.1:8020/projects
   ```

3. Verify that your project directories are listed in the response.

### Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| Empty project list | Wrong `requirements_path` | Check that the path exists and contains project subdirectories. |
| 500 error on baselines | Missing `UserDefinedAttributes.json` | Create the file at the top level of `requirements_path`. |
| Malformed response | Invalid JSONL | Verify that each line is valid JSON matching the required schema. |
