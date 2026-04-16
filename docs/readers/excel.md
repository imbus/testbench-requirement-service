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
├── ProjectA/                  # useExcelDirectly = true → Excel files only
│   ├── Baseline_v1.xlsx
│   └── Baseline_v2.xlsx
└── ProjectB/                  # useExcelDirectly = false → text files only
    ├── Requirements.csv
    └── Specs.tsv
```

:::caution One file type per project
Each project can use **either** Excel files (`.xlsx`, `.xls`) **or** text files (`.csv`, `.tsv`, `.txt`) — not both at the same time. This is controlled by the `useExcelDirectly` setting (globally or per project via a `.properties` file). Files of the wrong type are silently ignored.
:::

**Optional:** Place a project-specific `.properties` file (e.g. `ProjectA.properties`) inside a project directory to override the global configuration for that project.

## Required data layout

| Concept | Location |
|---------|----------|
| **Projects** | Top-level directories inside `requirementsDataPath` |
| **Baselines** | Excel or text files inside a project directory (also subfolders if `baselinesFromSubfolders=true`) |
| **Requirements** | Rows within a baseline file |
| **Project-specific config** | `<ProjectName>.properties` inside the project directory (optional) |

### File naming rules

- Baseline names are derived from file names without the extension. Keep baseline file names **unique within a project** — including across different extensions.
- If two files share the same stem (e.g. `Requirements.csv` and `Requirements.txt`), both will appear as a baseline named `Requirements` in the baseline list. When accessing that baseline, the **most recently modified** file takes precedence.

### Requirement data integrity

- **Required cells must not be blank.** Every row must have a non-blank value in the columns mapped to `requirement.id`, `requirement.version`, and `requirement.name`. Any blank values are reported as an error at load time, listing the affected row numbers.
- **IDs must be unique.** The `(id, version)` combination must be unique within a file. Duplicate pairs are detected and reported as an error.
- **Versions must change** whenever a requirement is edited. If TestBench has already imported a requirement and the ID reappears with the same version, it is treated as the unchanged requirement — even if the content was modified.
- **Hierarchy IDs must be unique.** If `requirement.hierarchyID` is configured, no two rows may share the same hierarchy ID value. Duplicates are reported as an error.

## Configuration

The Excel reader supports two configuration formats:

- **TOML**: inline under section `[testbench-requirement-service.reader_config]` inside of `config.toml`
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
| `columnSeparator` | Column separator in text files. Must not contain `"`, `\r`, or `\n`. | `;` |
| `arrayValueSeparator` | Separator within a list-valued cell. Must not contain `"`, `\r`, `\n`, or the same character as `columnSeparator`. | `,` |
| `baselineFileExtensions` | Comma-separated allowed file extensions (with dot) | `.tsv,.csv,.txt` |

### Optional settings

Can be set globally and overridden per project.

| Setting | Description | Default | Example |
|---------|-------------|---------|---------|
| `useExcelDirectly` | `true`: use `.xlsx`/`.xls` files.<br/>`false`: use text files | `false` | `true` |
| `baselinesFromSubfolders` | Search subfolders for baseline files | `false` | `true` |
| `worksheetName` | Worksheet name to use in Excel files (falls back to first sheet) | first sheet | `Tabelle1` |
| `dateFormat` | Date format for version dates. Accepts Java `SimpleDateFormat` (e.g. `yyyy-MM-dd HH:mm:ss`) or Python `strftime` (e.g. `%Y-%m-%d %H:%M:%S`). Auto-detected by presence of `%`. Falls back to `dateutil` auto-detection. | auto | `yyyy-MM-dd HH:mm:ss` |
| `header.rowIdx` | Row number of the header line (1-based) | `1` | `1` |
| `data.rowIdx` | Row number of the first data line (1-based). Must be greater than `header.rowIdx`. | `2` | `2` |
| `bufferMaxAgeMinutes` | Maximum idle age (minutes) before a cached dataframe is evicted. `0` = disable. | `1440` | `1440` |
| `bufferMaxSizeMiB` | Maximum total buffer size in MiB. When exceeded, least-recently used entries are evicted to 80%. `0` = disable. | `1024` | `1024` |
| `bufferCleanupIntervalMinutes` | Background cleanup interval (minutes) | `1` | `1` |

#### Dataframe buffering

The Excel reader caches parsed dataframes keyed by file path. A cached entry is reused when the source file's modification time matches. Each access refreshes the entry's age. Entries expire after `bufferMaxAgeMinutes`, and a background task cleans up every `bufferCleanupIntervalMinutes`. Set `bufferMaxSizeMiB=0` or `bufferMaxAgeMinutes=0` to disable buffering.

### Column mapping (attributes)

Column numbering starts at **1**. Mappings for `requirement.id`, `requirement.version`, and `requirement.name` are **mandatory**. All settings can be overridden per project.

| Setting | Description | Example |
|---------|-------------|---------|
| `requirement.id` | Column with the requirement ID (max 255 chars) | `1` |
| `requirement.version` | Column with the version (max 63 chars) | `6` |
| `requirement.name` | Column with the requirement name (max 255 chars) | `3` |
| `requirement.hierarchyID` | Column with the hierarchy ID | `2` |
| `requirement.owner` | Column with the responsible person (max 255 chars) | `4` |
| `requirement.status` | Column with the status (max 255 chars) | `5` |
| `requirement.priority` | Column with the priority (max 255 chars) | `15` |
| `requirement.comment` | Column with the comment (max 255 chars) | `14` |
| `requirement.date` | Column with the version date | `7` |
| `requirement.description.<n>` | Columns containing (parts of) the description | `requirement.description.1=8` |
| `requirement.references` | Column with file references (separated by `arrayValueSeparator`) | `13` |
| `requirement.type` | Column indicating folder vs. requirement | `10` |
| `requirement.folderPattern` | Regex to identify folders in the `type` column | `.*folder.*` |

:::note Character limits
Values that exceed the limits above are automatically **truncated** (with `...` appended) and a warning is logged. This matches TestBench's internal field length constraints. The `description` and `references` fields are not subject to length limits.
:::

### Hierarchy structure

When `requirement.hierarchyID` is configured, the reader builds a requirement tree. The hierarchy ID is a dot-separated string where each segment represents one level in the tree.

**Rules:**
- Requirements must be ordered according to their logical hierarchy position in the file (parent before children).
- Hierarchy IDs must be **unique** within a file.
- Do not use `0` as the last segment (e.g. prefer `2.1` over `2.1.0`).
- Choose **one style per tree**: either all-numeric segments (`1`, `1.1`, `1.1.1`) or consistently structured alphanumeric segments (`1`, `1.A`, `1.A.B`). Nodes at the same level must have the same segment type (all integers or all strings). Mixing `1.1` and `1.A` as siblings causes a sort error and is not supported.

**Examples:**

| Numeric nodes | Alphanumeric nodes |
|---|---|
| `1` | `1` |
| `1.1` | `1.A` |
| `1.1.1` | `1.A.B` |
| `2` | `2` |
| `2.1` | `2.A` |
| `2.1.1` | `2.A.B` |

**Placeholder nodes:** If a parent hierarchy ID is referenced but has no corresponding row in the file, the reader automatically inserts a placeholder node to preserve the tree structure. Placeholders are flagged in the logs and their IDs are prefixed with `__placeholder__`. When TestBench requests details for a placeholder, it receives a generated description explaining that the source data is missing a hierarchy level.

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
# config.toml
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

### Separate `.toml` file

```toml
# config.toml
[testbench-requirement-service]
reader_class = "ExcelRequirementReader"
reader_config_path = "excel_config.toml"
```

```toml
# excel_config.toml (no section prefix)
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

### Separate `.properties` file

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
   curl -u "ADMIN_USERNAME:PASSWORD" http://127.0.0.1:8020/projects
   ```

3. Confirm that the response lists your project directories.

### Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| `ModuleNotFoundError` | Missing `[excel]` dependencies | Run `pip install testbench-requirement-service[excel]` |
| Wrong data in response | Incorrect column separators or indices | Double-check `columnSeparator` and `requirement.*` column numbers |
| Path not found | Windows backslash escaping in `.properties` | Use forward slashes (`C:/...`) or double-escape (`C:\\\\...`) |
| Empty baselines | File extension mismatch | Ensure `baselineFileExtensions` includes the extensions of your files |
| Wrong worksheet data | `worksheetName` mismatch | Verify the name matches exactly (case-sensitive) or remove to use the first sheet |
