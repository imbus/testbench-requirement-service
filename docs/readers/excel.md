---
sidebar_position: 3
title: Excel Reader
---

# Excel Reader

Reads requirements from Excel workbooks (`.xlsx`, `.xls`) and delimited text files (`.csv`, `.tsv`, `.txt`).

**When to use:** Your requirements are stored in spreadsheets or delimited text files and you need flexible column mapping.

## Installation

Install the Excel extra:

```bash
pip install testbench-requirement-service[excel]
```

## Setup

1. Create a root directory for your requirements (e.g. `requirements/excel/`).
2. Inside it, create one subdirectory per **project**.
3. Place baseline files (`.xlsx`, `.xls`, `.csv`, `.tsv`, or `.txt`) inside each project directory.
4. Provide reader configuration with column mappings, either inline in `config.toml` or via a `.properties` file.

**Directory layout example:**

```
requirements/excel/
├── ProjectA/
│   ├── Baseline_v1.xlsx
│   └── Baseline_v2.csv
└── ProjectB/
    └── Requirements.tsv
```

**Optional:** Place a project-specific `.properties` file (e.g. `ProjectA.properties`) inside a project directory to override the global configuration for that project.

## Required data layout

| Concept | Location |
|---------|----------|
| **Projects** | Top-level directories inside `requirementsDataPath` |
| **Baselines** | Excel or text files inside a project directory (also subfolders if `baselinesFromSubfolders=true`) |
| **Requirements** | Rows within a baseline file |
| **Project-specific config** | `<ProjectName>.properties` inside the project directory (optional) |

## Configuration

The Excel reader supports two configuration formats:

- **TOML**: inline under `[testbench-requirement-service.reader_config]` in `config.toml`
- **Java `.properties`**: a separate file with global settings, optionally overridden per project

:::caution Windows paths in `.properties` files
Java `.properties` files treat backslashes (`\`) as escape characters:

- `C:\folder\file` → parsed incorrectly ❌
- `\\server\temp` → parsed incorrectly ❌

**Use forward slashes** (recommended):
```properties
requirementsDataPath = C:/path/to/folder
requirementsDataPath = //server/share/folder
```

Or double-escape backslashes:
```properties
requirementsDataPath = C:\\\\path\\\\to\\\\folder
```
:::

### Global settings (mandatory)

These can only be set in the global configuration.

| Setting | Description | Example |
|---------|-------------|---------|
| `requirementsDataPath` | Path to the root directory for requirement data | `C:/requirements/excel` |

### Mandatory settings

Must be in the global config. Can be overridden per project.

| Setting | Description | Example |
|---------|-------------|---------|
| `columnSeparator` | Column separator in text files | `;` |
| `arrayValueSeparator` | Separator within a list of values | `,` |
| `baselineFileExtensions` | Comma-separated allowed file extensions (with dot) | `.tsv,.csv,.txt` |

### Optional settings

Can be set globally and overridden per project.

| Setting | Description | Default | Example |
|---------|-------------|---------|---------|
| `useExcelDirectly` | `true`: use `.xlsx`/`.xls` files. `false`: use text files | `false` | `true` |
| `baselinesFromSubfolders` | Search subfolders for baseline files | `false` | `true` |
| `worksheetName` | Worksheet name to use in Excel files (falls back to first sheet) | first sheet | `Tabelle1` |
| `dateFormat` | Date format for version dates. Accepts Java `SimpleDateFormat` (e.g. `yyyy-MM-dd HH:mm:ss`) or Python `strftime` (e.g. `%Y-%m-%d %H:%M:%S`). Auto-detected by presence of `%`. Falls back to `dateutil` auto-detection. | auto | `yyyy-MM-dd HH:mm:ss` |
| `header.rowIdx` | Row number of the header line (1-based) | `1` | `1` |
| `data.rowIdx` | Row number of the first data line (1-based) | `2` | `2` |
| `bufferMaxAgeMinutes` | Max idle age (minutes) before a cached dataframe is evicted. `0` = disable. | `1440` | `1440` |
| `bufferMaxSizeMiB` | Max total buffer size in MiB. When exceeded, least-recently used entries are evicted to 80%. `0` = disable. | `1024` | `1024` |
| `bufferCleanupIntervalMinutes` | Background cleanup interval (minutes) | `1` | `1` |

#### Dataframe buffering

The Excel reader caches parsed dataframes keyed by file path. A cached entry is reused when the source file's modification time matches. Each access refreshes the entry's age. Entries expire after `bufferMaxAgeMinutes`, and a background task cleans up every `bufferCleanupIntervalMinutes`. Set `bufferMaxSizeMiB=0` or `bufferMaxAgeMinutes=0` to disable buffering.

### Column mapping (attributes)

Column numbering starts at **1**. Mappings for `requirement.id`, `requirement.version`, and `requirement.name` are **mandatory**. Can be overridden per project.

| Setting | Description | Example |
|---------|-------------|---------|
| `requirement.id` | Column with the requirement ID | `1` |
| `requirement.version` | Column with the version | `6` |
| `requirement.name` | Column with the requirement name | `3` |
| `requirement.hierarchyID` | Column with the hierarchy ID | `2` |
| `requirement.owner` | Column with the responsible person | `4` |
| `requirement.status` | Column with the status | `5` |
| `requirement.priority` | Column with the priority | `15` |
| `requirement.comment` | Column with the comment | `14` |
| `requirement.date` | Column with the version date | `7` |
| `requirement.description.<n>` | Columns containing (parts of) the description | `requirement.description.1=8` |
| `requirement.references` | Column with file references (separated by `arrayValueSeparator`) | `13` |
| `requirement.type` | Column indicating folder vs. requirement | `10` |
| `requirement.folderPattern` | Regex to identify folders in the `type` column | `.*folder.*` |

### User-defined fields (UDF)

UDF settings can only be configured globally.

| Setting | Description | Example |
|---------|-------------|---------|
| `udf.count` | Number of user-defined fields | `2` |
| `udf.attr#.name` | UDF name as shown in TestBench | `udf.attr1.name=Risiko` |
| `udf.attr#.column` | Column containing the UDF | `udf.attr1.column=11` |
| `udf.attr#.type` | Value type: `string`, `array`, or `boolean` | `udf.attr1.type=String` |
| `udf.attr#.trueValue` | Value that maps to `TRUE` (for booleans) | `udf.attr2.trueValue=ja` |

### Project-specific overrides

For `.properties` files: place a file named `<ProjectName>.properties` inside the project directory. It can override any mandatory, optional, or column-mapping setting from the global config.

## Example configurations

### Inline TOML

When configuring inline in `config.toml`, keys containing dots must be **quoted**:

```toml
[testbench-requirement-service]
reader_class = "ExcelRequirementReader"

[testbench-requirement-service.reader_config]
requirementsDataPath = "requirements/excel/"
columnSeparator = ";"
arrayValueSeparator = ","
baselineFileExtensions = ".tsv,.csv,.txt"
useExcelDirectly = false
"requirement.id" = 1
"requirement.version" = 6
"requirement.name" = 3
"requirement.owner" = 4
"requirement.status" = 5
```

### `.properties` file

```properties
# reader_config.properties

# Global Settings
# IMPORTANT: Use forward slashes for Windows paths!
requirementsDataPath=C:/requirements/excel/
# Or for UNC paths: requirementsDataPath=//server/share/requirements/

# Mandatory Settings
columnSeparator=;
arrayValueSeparator=,
baselineFileExtensions=.tsv,.csv,.txt

# Optional Settings
useExcelDirectly=false
baselinesFromSubfolders=false
worksheetName=Tabelle1
dateFormat=yyyy-MM-dd HH:mm:ss
header.rowIdx=1
data.rowIdx=2
bufferMaxAgeMinutes=1440
bufferMaxSizeMiB=1024
bufferCleanupIntervalMinutes=1

# Column Mapping
requirement.hierarchyID=2
requirement.id=1
requirement.version=6
requirement.name=3
requirement.owner=4
requirement.status=5
requirement.priority=15
requirement.comment=14
requirement.date=7
requirement.description.1=8
requirement.description.2=9
requirement.type=10
requirement.folderPattern=.*folder.*

# User Defined Fields
udf.count=3

udf.attr1.name=Risiko
udf.attr1.type=string
udf.attr1.column=11

udf.attr2.name=Project Groups
udf.attr2.type=boolean
udf.attr2.trueValue=true
udf.attr2.column=16

udf.attr3.name=Units
udf.attr3.type=array
udf.attr3.column=17
```

## Testing

### Smoke test

1. Start the server:
   ```bash
   testbench-requirement-service start
   ```

2. Verify projects and baselines are discovered:
   ```bash
   curl -u "admin:mypassword" http://127.0.0.1:8020/projects
   ```

3. Confirm the response lists your project directories.

### Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| `ModuleNotFoundError` | Missing `[excel]` dependencies | Run `pip install testbench-requirement-service[excel]` |
| Wrong data in response | Incorrect column separators or indices | Double-check `columnSeparator` and `requirement.*` column numbers |
| Path not found | Windows backslash escaping in `.properties` | Use forward slashes (`C:/...`) or double-escape (`C:\\\\...`) |
| Empty baselines | File extension mismatch | Ensure `baselineFileExtensions` includes the extensions of your files |
| Wrong worksheet data | `worksheetName` mismatch | Verify the name matches exactly (case-sensitive) or remove to use the first sheet |
