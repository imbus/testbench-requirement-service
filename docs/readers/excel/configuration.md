---
sidebar_position: 2
title: Excel Reader — Configuration
---

## Configuration formats

- Inline TOML under `[testbench-requirement-service.reader_config]`
- Java `.properties` file (global + optional per-project override)

## Path note (Windows + .properties)

Java `.properties` treats backslashes as escapes. Prefer forward slashes (`C:/...`) or double-escape (`C:\\\\...`).

## Configuration reference

### Data root (global settings)

The global settings are mandatory and can only be configured in the global configuration.

| Global setting | Description | Example |
| --- | --- | --- |
| `requirementsDataPath` | Path to the root directory for requirement data. For `.properties` files on Windows: use forward slashes (`/`) or double-escape backslashes (`\\`). | `requirementsDataPath=C:/requirements/excel` or `requirementsDataPath=//server/share` |

### Mandatory settings

All mandatory settings should be configured in the global configuration. They can be overwritten by values in project-specific configuration files.

| Mandatory setting | Description | Example |
| --- | --- | --- |
| `columnSeparator` | Column separator in text files. | `columnSeparator=;` |
| `arrayValueSeparator` | Separator within a list of values. | `arrayValueSeparator=,` |
| `baselineFileExtensions` | Comma-separated list of allowed file extensions preceded by a dot. | `baselineFileExtensions=.tsv,.csv,.txt` |

### Optional settings

Optional settings can be specified in the global configuration and can be overwritten by values in project-specific configuration files.

| Optional setting | Description | Example |
| --- | --- | --- |
| `useExcelDirectly` | `true`: Use Microsoft Excel files. `false`: Use text files as specified in `baselineFileExtensions`. | `useExcelDirectly=false` |
| `baselinesFromSubfolders` | `true`: Search for baseline files in all subfolders. `false`: Do not search in subfolders. | `baselinesFromSubfolders=true` |
| `worksheetName` | Name of the worksheet to be used in Excel files. If missing, the first worksheet is used. | `worksheetName=Tabelle1` |
| `dateFormat` | Date format in documents as Java `SimpleDateFormat`. | `dateFormat=yyyy-MM-dd HH:mm:ss` |
| `header.rowIdx` | Line number of the header line in the requirement documents. Numbering starts at 1. | `header.rowIdx=1` |
| `data.rowIdx` | Line number of the first requirement line. Numbering starts at 1. | `data.rowIdx=2` |
| `bufferMaxAgeMinutes` | Maximum idle age (in minutes) before a buffered dataframe is evicted. | `bufferMaxAgeMinutes=1440` |
| `bufferMaxSizeMiB` | Maximum total buffer size in MiB. When exceeded, least-recently accessed entries are evicted until the buffer is back to $80\%$ of the limit. Set to `0` to disable buffering. | `bufferMaxSizeMiB=1024` |
| `bufferCleanupIntervalMinutes` | Background cleanup interval in minutes for expiring cached dataframes. | `bufferCleanupIntervalMinutes=1` |

### Column mapping (attributes)

The column mapping configured in the global configuration can be overwritten by values in project-specific configuration files.

The mapping for `requirement.id`, `requirement.version` and `requirement.name` is mandatory. Column numbering starts at 1.

| Column mapping | Description | Example |
| --- | --- | --- |
| `requirement.hierarchyID` | Column containing the hierarchy ID of the requirement. | `requirement.hierarchyID=2` |
| `requirement.id` | Column containing the requirement id. | `requirement.id=1` |
| `requirement.version` | Column containing the version of the requirement. | `requirement.version=6` |
| `requirement.name` | Column containing the name of the requirement. | `requirement.name=3` |
| `requirement.owner` | Column containing the name of the person responsible for the requirement. | `requirement.owner=4` |
| `requirement.status` | Column containing the status of the requirement. | `requirement.status=5` |
| `requirement.priority` | Column containing the priority of the requirement. | `requirement.priority=15` |
| `requirement.comment` | Column containing the comment of the requirement. | `requirement.comment=14` |
| `requirement.date` | Column containing the version date of the requirement. | `requirement.date=7` |
| `requirement.description.<number>` | List of all columns that contain (parts of the) requirement description. | `requirement.description.1=8` |
| `requirement.references` | Column containing the file references of the requirement. File references are separated from each other with `arrayValueSeparator`. | `requirement.references=13` |
| `requirement.type` | Column containing the information if entry is a folder or a requirement. | `requirement.type=10` |
| `requirement.folderPattern` | Regular expression used to identify folders in the data. Any value in the `requirement.type` column that matches this pattern is considered a folder. Default: `.*folder.*` | `requirement.folderPattern=.*folder.*` |

### Settings for user-defined fields (UDF)

UDF settings can only be configured in the global configuration file.

| UDF setting | Description | Example |
| --- | --- | --- |
| `udf.count` | Number of user defined fields to be used. | `udf.count=2` |
| `udf.attr#.name` | Name of the user defined field used in the TestBench client. | `udf.attr1.name=Risiko` |
| `udf.attr#.column` | Column containing the user defined field. | `udf.attr1.column=11` |
| `udf.attr#.type` | Type of the user defined field. Can be `string`, `array` or `boolean` (case-insensitive). | `udf.attr1.type=String` |
| `udf.attr#.trueValue` | Attribute value that corresponds to TRUE. All other values are interpreted as FALSE. | `udf.attr2.trueValue=ja` |

## Example `.properties` configuration

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

# Column Mapping: Attributes
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

# Settings for User defined fields
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

## TOML notes

If you configure the Excel reader inline in `config.toml`, keys that contain dots must be quoted.

Example:

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
```

