---
sidebar_position: 2
title: JSONL Reader — Configuration
---

The JSONL reader is the default reader. It reads requirements from JSON Lines (`.jsonl`) files on disk.

## Configuration keys

| Setting | Type | Description | Required | Default |
| --- | --- | --- | --- | --- |
| `requirements_path` | String | Path to the directory containing the requirement files. | Yes | - |

## Required data layout

- **Projects** are directories located at the top level inside `requirements_path`.
- **Baselines** are `.jsonl` files stored within a project directory.
- **Requirements** are JSON objects, each represented as a separate line in a baseline `.jsonl` file.
- **User-defined attributes** are defined in `UserDefinedAttributes.json` at the top level of `requirements_path`.

### Requirement objects (high-level schema)

Each line in a baseline file is a JSON object.

- If `requirement` is `true`, the object represents an actual requirement.
- If `requirement` is `false`, the object is a structural node (folder/group) in the requirements tree.
- Root objects have `parent` set to `null`.

Common fields:

- `name`: string
- `extendedID`: string
- `key.id`: string
- `key.version`: object with `name`, `date`, `author`, `comment`
- `owner`, `status`, `priority`: string
- `description`: string
- `documents`: array of strings
- `parent`: string or null
- `userDefinedAttributes`: array of UDF objects (`name`, `valueType`, and the matching value field)

### UserDefinedAttributes.json

This file defines which UDFs exist and their value type.

Example:

```json
[
	{ "name": "Risk", "valueType": "STRING" },
	{ "name": "Units", "valueType": "ARRAY" },
	{ "name": "In Scope", "valueType": "BOOLEAN" }
]
```

