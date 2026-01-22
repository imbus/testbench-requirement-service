# TestBench Requirement Service - Python

A REST API service for imbus TestBench that provides unified access to requirements from multiple sources (Jira, Excel, JSONL).

## Table of contents

- [Installation](#installation)
- [Setup](#setup)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Built-in RequirementReader](#built-in-requirementreader)
- [Custom RequirementReader Classes](#custom-requirementreader-classes)
- [Contributing](#contributing)
- [License](#license)

## Installation

This tool requires **Python 3.10+** and **pip** installed.

### 1. Install the tool

If you have Python 3.10 or higher and pip installed, you can easily install the tool by running:

```powershell
pip install testbench-requirement-service
```

This will install the base version of the tool.

### 2. Optional: Install extras

If you need additional readers, you can install optional dependency groups.

#### Excel support (optional)

If you need support for reading requirements from Excel or text files ([ExcelRequirementReader](#excelrequirementreader)), install the Excel/text-file extras:

```powershell
pip install testbench-requirement-service[excel]
```

This installs the dependencies required by the [ExcelRequirementReader](#excelrequirementreader) (for reading `.xlsx`, `.xls`, `.csv`, `.tsv`, `.txt` files).

#### Jira support (optional)

If you need support for reading requirements from Jira ([JiraRequirementReader](#jirarequirementreader)), install the Jira extras:

```powershell
pip install testbench-requirement-service[jira]
```

This installs the Python Jira client and HTML parsing library required by the [JiraRequirementReader](#jirarequirementreader) (packages: `jira`, `beautifulsoup4`).

#### SQL support (optional)

If you need support for reading requirements from SQL databases ([SqlRequirementReader](#sqlrequirementreader)), install the SQL extras:

```powershell
pip install testbench-requirement-service[sql]
```

This installs SQLAlchemy. You must also install the DB driver for your database (e.g., `pymysql` or `mariadb` for MariaDB/MySQL, `oracledb` for Oracle).

You can install multiple extras at once:

```powershell
pip install testbench-requirement-service[excel,jira,sql]
```

### 3. Verify the installation

Once installed, verify the installation by checking the version:

```powershell
testbench-requirement-service --version
```

If the installation was successful, this will output the installed version of the tool.

## Setup

Before starting the service, you need to configure authentication and choose a requirement reader.

### Step 1: Create a configuration file

The service requires a configuration file in **TOML** format.

You can generate a default configuration file by running:

```powershell
testbench-requirement-service init
```

This will create a default configuration file (`config.toml`) in your current working directory.

**Note:** The legacy `config.py` (Python) format is still supported but will be deprecated in a future release. New projects should use TOML.

### Step 2: Set up your service credentials

Set credentials for Basic Auth by running:

```powershell
testbench-requirement-service set-credentials
```

This prompts for username and password and updates your configuration file with hashed credentials. Alternatively, specify them directly:

```powershell
testbench-requirement-service set-credentials --username USERNAME --password PASSWORD
```

### Step 3: Choose and configure your requirement reader

The service supports four built-in readers. Choose one based on your data source:

| Reader | Data Source | Config File Format | Install Command |
|--------|-------------|-------------------|-----------------|
| **[JsonlRequirementReader](#jsonlrequirementreader-default)** *(default)* | `.jsonl` files | `.toml` | Included in base install |
| **[ExcelRequirementReader](#excelrequirementreader)** | `.xlsx`, `.xls`, `.csv`, `.tsv`, `.txt` files | `.properties` | `pip install testbench-requirement-service[excel]` |
| **[JiraRequirementReader](#jirarequirementreader)** | Jira REST API | `.toml` + credentials | `pip install testbench-requirement-service[jira]` |
| **[SqlRequirementReader](#sqlrequirementreader)** | SQL databases via SQLAlchemy | `.toml` | `pip install testbench-requirement-service[sql]` |

Edit your `config.toml` file to specify which reader to use:

```toml
[testbench-requirement-service]
reader_class = "JsonlRequirementReader"
reader_config_path = "reader_config.toml"
# For other readers, change the values above accordingly
```

Refer to the [Configuration](#configuration) section for detailed configuration options and advanced settings.

**Note:** You can override configuration settings at startup using command-line flags:

```powershell
testbench-requirement-service start --reader-class JiraRequirementReader --reader-config jira_config.toml
```

### Step 4: Create your reader configuration file

Create the configuration file specified in `reader_config_path` (or via `--reader-config`).

#### For JsonlRequirementReader (default):

Create `reader_config.toml`:

```toml
[jsonl]
requirements_path = "requirements/jsonl/"
```

See [JsonlRequirementReader](#jsonlrequirementreader-default) for full schema and requirements.

#### For ExcelRequirementReader:

Create `excel_config.properties`:

```properties
requirementsDataPath=requirements/excel/
columnSeparator=;
arrayValueSeparator=,
baselineFileExtensions=.tsv,.csv,.txt
# ... additional settings
```

See [ExcelRequirementReader](#excelrequirementreader) for complete configuration options.

#### For JiraRequirementReader:

Create `jira_config.toml`:

```toml
[jira]
server_url = "https://your-jira.atlassian.net/"
auth_type = "basic"
# ... additional settings
```

Create a `.env` file with credentials:

```text
JIRA_USERNAME=your-email@example.com
JIRA_API_TOKEN=your-api-token
```

See [JiraRequirementReader](#jirarequirementreader) for authentication methods and full configuration.

#### For SqlRequirementReader:

Create `sql_config.toml`:

```toml
[sql]
database_url = "mariadb+pymysql://USER:PASSWORD@HOST:3306/DBNAME"
echo = false
pool_pre_ping = true
```

Example database URLs:

- MariaDB (PyMySQL): `mariadb+pymysql://user:pass@host:3306/dbname`
- MariaDB (MariaDB Connector): `mariadb+mariadbconnector://user:pass@host:3306/dbname`
- Oracle (python-oracledb): `oracle+oracledb://user:pass@host:1521/?service_name=ORCLCDB`

See [SqlRequirementReader](#sqlrequirementreader) for configuration details.

---

**You're now ready to start the service!** See the [Usage](#usage) section below.

## Configuration

Your service can be configured using a configuration file in **TOML** format. The configuration file allows you to control service settings, reader selection, authentication, and logging behavior.

**Note:** The legacy `config.py` (Python) format is still supported but will be deprecated in a future release.

### Configuration file format

The configuration file uses TOML format with `[testbench-requirement-service]` as the main section. Here's an example configuration:

```toml
[testbench-requirement-service]
reader_class = "JsonlRequirementReader"
reader_config_path = "reader_config.toml"
host = "127.0.0.1"
port = 8000
password_hash = "your_generated_hash"
salt = "your_generated_salt"

# Console logging configuration
[testbench-requirement-service.logging.console]
log_level = "INFO"
log_format = "%(asctime)s %(levelname)8s: %(message)s"

# File logging configuration
[testbench-requirement-service.logging.file]
log_level = "INFO"
log_format = "%(asctime)s - %(levelname)8s - %(name)s - %(message)s"
file_path = "testbench-requirement-service.log"
```

### Configuration sections

#### `[testbench-requirement-service]`

| Option                 | Type   | Description                                                                  | Required | Default                                                                      |
| ---------------------- | ------ | ---------------------------------------------------------------------------- | -------- | ---------------------------------------------------------------------------- |
| `reader_class`       | String | Reader class name or module path                                            | No       | `"testbench_requirement_service.readers.JsonlRequirementReader"`          |
| `reader_config_path` | String | Path to the reader configuration file                                       | No      | -                                                                            |
| `host`               | String | Host address to run the service on                                          | No       | `"127.0.0.1"`                                                              |
| `port`               | Integer | Port number to run the service on                                           | No       | `8000`                                                                      |
| `password_hash`      | String | Hashed password for Basic Auth (generated by `set-credentials` command)    | No       | -                                                                            |
| `salt`               | String | Salt value for password hashing (generated by `set-credentials` command)   | No       | -                                                                            |

**Note:** `password_hash` and `salt` are automatically generated when you run `testbench-requirement-service set-credentials`. You can also set these via environment variables `PASSWORD_HASH` and `SALT`.

#### `[testbench-requirement-service.logging.console]`

| Option         | Type   | Description                                                                                                  | Required | Default                                      |
| -------------- | ------ | ------------------------------------------------------------------------------------------------------------ | -------- | -------------------------------------------- |
| `log_level`  | String | Minimum severity level to log to console ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")           | No       | `"INFO"`                                   |
| `log_format` | String | Format string for console log messages,<br />using Python's standard logging format syntax                  | No       | `"%(asctime)s %(levelname)8s: %(message)s"` |

#### `[testbench-requirement-service.logging.file]`

| Option         | Type   | Description                                                                                                  | Required | Default                                                              |
| -------------- | ------ | ------------------------------------------------------------------------------------------------------------ | -------- | -------------------------------------------------------------------- |
| `log_level`  | String | Minimum severity level to log to file ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")             | No       | `"INFO"`                                                           |
| `log_format` | String | Format string for file log messages,<br />using Python's standard logging format syntax                     | No       | `"%(asctime)s - %(levelname)8s - %(name)s - %(message)s"`          |
| `file_path`  | String | Path to the log file where messages will be written                                                         | No       | `"testbench-requirement-service.log"`                              |

### Command-line overrides

Configuration values can be overridden at startup using command-line flags. Command-line arguments take precedence over configuration file settings:

```powershell
testbench-requirement-service start --config custom_config.toml --host 0.0.0.0 --port 9000 --reader-class JiraRequirementReader --reader-config jira_config.toml
```

See `testbench-requirement-service start --help` for all available options.

## Usage

Now that your service is set up, you can start the service through the command-line interface.

### Start the Service

The basic command to start the service is:

```powershell
testbench-requirement-service start
```

By default, the service will run locally on `127.0.0.1:8000`. If you'd like to run it on a different host or port, use the following options:

```powershell
testbench-requirement-service start --host HOST --port PORT
```

For example, to run the service on host `127.0.0.2` and port `8002`:

```powershell
testbench-requirement-service start --host 127.0.0.2 --port 8002
```

### Available Options

| Option              | Description                                       | Default                                                          |
| ------------------- | ------------------------------------------------- | ---------------------------------------------------------------- |
| `--config`        | Path to the app configuration file                | `config.toml`                                                    |
| `--reader-class`  | Path or module string to the reader class         | `testbench_requirement_service.readers.JsonlRequirementReader` |
| `--reader-config` | Path to the reader configuration file             | `reader_config.toml`                                           |
| `--host`          | Host to run the service on                        | `127.0.0.1`                                                    |
| `--port`          | Port to run the service on                        | `8000`                                                         |
| `--dev`           | Run the service in dev mode (debug + auto reload) | Not set                                                          |

You can also see the available options and their descriptions by running:

```powershell
testbench-requirement-service start --help
```

### Example Usage

- **Start the service with custom host and port**
  ```powershell
  testbench-requirement-service start --host 127.0.0.2 --port 8001
  ```
- **Start the service in dev mode (debug + auto reload)**
  ```powershell
  testbench-requirement-service start --dev
  ```
- **Use a custom config path**
  ```powershell
  testbench-requirement-service start --config path/to/config.toml
  ```
- **Use a custom reader class**
  ```powershell
  testbench-requirement-service start --reader-class custom_reader.CustomRequirementReader
  ```

## API Documentation

Once your service is running, you can explore the available API documentation and OpenAPI specification using built-in endpoints.

### Interactive API Docs

The interactive API documentation is available at `/docs` and is powered by **Swagger UI**.
If the server is running locally with default settings, you can access it at: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Swagger UI allows you to test API endpoints directly, including authentication using the "Authorize" button.

### OpenAPI Specification

For the raw OpenAPI JSON schema, use the built-in endpoint `/docs/openapi.json`: [http://127.0.0.1:8000/docs/openapi.json](http://127.0.0.1:8000/docs/openapi.json)

## Built-in RequirementReader

The service includes built-in requirement reader classes that handle different file formats. Jump directly to a reader:

- [JsonlRequirementReader (default)](#jsonlrequirementreader-default)
- [ExcelRequirementReader](#excelrequirementreader)
- [JiraRequirementReader](#jirarequirementreader)
- [SqlRequirementReader](#sqlrequirementreader)

Below is a detailed description of each reader:

### JsonlRequirementReader *(Default)*

Reads requirement data from `.jsonl` (JSON Lines) files.

#### Prerequisites:

1. **Install the base package:**
   ```powershell
   pip install testbench-requirement-service
   ```
   The JsonlRequirementReader is included in the base installation.

2. **Set up credentials** (if not already done):
   ```powershell
   testbench-requirement-service set-credentials
   ```

3. **Configure in your app configuration file** (`config.toml`):
   ```toml
   [testbench-requirement-service]
   reader_class = "JsonlRequirementReader"
   reader_config_path = "reader_config.toml"
   ```
   See [Setup](#setup) for detailed configuration instructions.

4. **Create reader configuration file** (see [Configuration](#configuration) below)

#### Configuration:
The configuration for the reader is read from a `.toml` file with a `[jsonl]` table as the main section.

##### `[jsonl]`

| Setting               | Type   | Description                                             | Required | Default |
| --------------------- | ------ | ------------------------------------------------------- | -------- | ------- |
| `requirements_path` | String | Path to the directory containing the requirement files. | Yes      | -       |

#### Required Schema:

- ***Projects*** are directories located at the top level inside `requirements_path`.
- ***Baselines*** are `.jsonl` files stored within a project directory.
- ***Requirements*** are JSON objects, each represented as a separate line in a baseline `.jsonl` file.
  A requirement follows this Schema:

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
      "requirement": boolean,
      "description": "string",
      "documents": ["string"],
      "parent": "string" | null,
      "userDefinedAttributes": [
          {
              "name": "string",
              "valueType": "STRING" | "ARRAY" | "BOOLEAN",
              "stringValue": "string",
              "stringValues": ["string"],
              "booleanValue": boolean
          }
      ]
  }
  ```

  If the `"requirement"` attribute is set to `true`, the object represents an actual requirement. Otherwise, it serves only as a node in the requirements tree structure.
  Root requirement objects have their `"parent"` attribute set to `null`.
- ***UserDefinedAttributes*** are specified in the `UserDefinedAttributes.json` file, located at the top level in `requirements_path`.
  This file follows the Schema below:

  ```json
  [
      {
          "name": "string",
          "valueType": "STRING" | "ARRAY" | "BOOLEAN"
      }
  ]
  ```

#### Example Configuration:
Here's an example of how to configure the `JsonlRequirementReader` in the `.toml` configuration file:

```toml
# reader_config.toml
[jsonl]
requirements_path = "requirements/"
```

### ExcelRequirementReader

Reads requirement data from various file formats, including `.xlsx`, `.xls`, `.csv`, `.tsv`, and `.txt` files. The reader allows for flexible configuration to handle either Microsoft Excel formats (`.xlsx` or `.xls`) or CSV/Text files (`.csv`, `.tsv` or `.txt`).

#### Prerequisites:

1. **Install Excel extras:**
   ```powershell
   pip install testbench-requirement-service[excel]
   ```
   This installs dependencies for reading `.xlsx`, `.xls`, `.csv`, `.tsv`, and `.txt` files.

2. **Set up credentials** (if not already done):
   ```powershell
   testbench-requirement-service set-credentials
   ```

3. **Configure in your app configuration file** (`config.toml`):
   ```toml
   [testbench-requirement-service]
   reader_class = "ExcelRequirementReader"
   reader_config_path = "excel_config.properties"
   ```
   See [Setup](#setup) for detailed configuration instructions.

4. **Create reader configuration file** (see [Configuration](#configuration-1) below)

#### Configuration:
The configuration for the reader is read from a Java Properties `.properties` file. By default, the reader uses a global `.properties` file, but if a project-specific `.properties` file is found, it can override the global configuration.
- **Global Settings**:
  The global settings are mandatory. They can only be configured in the global configuration file.

  | Global Setting           | Description                                     | Example                                     |
  | ------------------------ | ----------------------------------------------- | ------------------------------------------- |
  | `requirementsDataPath` | Path to the root directory for requirement data | `requirementsDataPath=requirements/excel` |
- **Mandatory Settings**:
  All mandatory settings should be configured in the global configuration file. They can be overwritten by values in project-specific configuration files.

  | Mandatory Setting          | Description                                                        | Example                                   |
  | -------------------------- | ------------------------------------------------------------------ | ----------------------------------------- |
  | `columnSeparator`        | Column separator in text files                                     | `columnSeparator=;`                     |
  | `arrayValueSeparator`    | Separator within a list of values                                  | `arrayValueSeparator=,`                 |
  | `baselineFileExtensions` | Comma-separated list of allowed file extensions preceded by a dot. | `baselineFileExtensions=.tsv,.csv,.txt` |
- **Optional Settings**:
  Optional settings can be specified in the global configuration file and can be overwritten by values in project-specific configuration files.

  | Optional Setting            | Description                                                                                                               | Example                            |
  | --------------------------- | ------------------------------------------------------------------------------------------------------------------------- | ---------------------------------- |
  | `useExcelDirectly`        | `true`: Use Microsoft Excel files `<br>false`: Use text files like specified in `baselineFileExtensions`            | `useExcelDirectly=false`         |
  | `baselinesFromSubfolders` | `true`: Searches for baseline files in all subfolders `<br>false`: Does not search for baseline files in subfolders   | `baselinesFromSubfolders=true`   |
  | `worksheetName`           | Name of the worksheet to be used in the Excel files. If there is no corresponding worksheet, the first worksheet is used. | `worksheetName=Tabelle1`         |
  | `dateFormat`              | Date format in documents as Javas SimpleDateFormat                                                                        | `dateFormat=yyyy-MM-dd HH:mm:ss` |
  | `header.rowIdx`           | Line number of the header line in the requirement documents. Numbering starts at 1.                                       | `header.rowIdx=1`                |
  | `data.rowIdx`             | Line number of the first requirement line. Numbering starts at 1.                                                         | `data.rowIdx=2`                  |
- **Column Mapping: Attributes**:
  The column mapping of attributes configured in the global configuration file can be overwritten by values in project-specific configuration files. The column mapping for the attributes `íd`, `version` and `name` is mandatory. Column numbering starts at 1.

  | Column Mapping                       | Description                                                                                                                                                                                                                        | Example                                                          |
  | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
  | `requirement.hierarchyID`          | Column containing the hierarchy ID of the requirement                                                                                                                                                                              | `requirement.hierarchyID=2`                                    |
  | `requirement.id`                   | Column containing the requirement id                                                                                                                                                                                               | `requirement.id=1`                                             |
  | `requirement.version`              | Column containing the version of the requirement                                                                                                                                                                                   | `requirement.version=6`                                        |
  | `requirement.name`                 | Column containing the name of the requirement                                                                                                                                                                                      | `requirement.name=3`                                           |
  | `requirement.owner`                | Column containing the name of the person responsible for the requirement                                                                                                                                                           | `requirement.owner=4`                                          |
  | `requirement.status`               | Column containing the status of the requirement                                                                                                                                                                                    | `requirement.status=5`                                         |
  | `requirement.priority`             | Column containing the priority of the requirement                                                                                                                                                                                  | `requirement.priority=15`                                      |
  | `requirement.comment`              | Column containing the comment of the requirement                                                                                                                                                                                   | `requirement.comment=14`                                       |
  | `requirement.date`                 | Column containing the version date of the requirement                                                                                                                                                                              | `requirement.date=7`                                           |
  | `requirement.description.<number>` | List of all columns that contain (parts of the) requirement description                                                                                                                                                            | `requirement.description.1=8<br>``requirement.description.2=9` |
  | `requirement.references`           | Column containing the file references of the requirement.`<br>` File references are separated from each other with the `arrayValueSeparator`                                                                                   | `requirement.references=13`                                    |
  | `requirement.type`                 | Column containing the information if entry is a folder or a requirement                                                                                                                                                            | `requirement.type=10`                                          |
  | `requirement.folderPattern`        | Defines the regular expression pattern used to identify folders in the data.`<br>`Any value in the specified column (`requirement.type`) that matches this pattern will be considered a folder.`<br>`Default: `.*folder.*` | `requirement.folderPattern=.*folder.*`                         |
- **Settings for User defined fields**:
  The settings for user defined fields (UDF) can only be configured in the global configuration file.

  | UDF Setting             | Description                                                                                   | Example                    |
  | ----------------------- | --------------------------------------------------------------------------------------------- | -------------------------- |
  | `udf.count`           | Number of user defined fields to be used                                                      | `udf.count=2`            |
  | `udf.attr#.name`      | Name of the user defined field used in the TestBench                                          | `udf.attr1.name=Risiko`  |
  | `udf.attr#.column`    | Column containing the user defined field                                                      | `udf.attr1.column=11`    |
  | `udf.attr#.type`      | Type of the user defined field. Can be `string`, `array` or `boolean`, case-insensitive | `udf.attr1.type=String`  |
  | `udf.attr#.trueValue` | Attribute value that corresponds to TRUE. All other attribute values are interpreted as FALSE | `udf.attr2.trueValue=ja` |

#### Example Configuration:

```properties
# reader_config.properties

# Global Settings
requirementsDataPath=requirements/excel/

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

#### Required Schema:
- ***Projects*** are directories located at the top level inside `requirementsDataPath`.
- ***Baselines*** are excel files (`.xlsx` or `.xls`) or text files (`.tsv`, `.csv` or `.txt`) stored within a project directory. If the `baselinesFromSubfolders` setting is set to `true`, subfolders within the project directory are also searched for baseline files.
- ***Requirements*** are represented as separate lines within a baseline file.
- To use a ***project-specific configuration***, place a `.properties` file inside the project directory, named after the project. For example, if the project is named `Project1`, the configuration file must be named `Project1.properties`.

### JiraRequirementReader

Reads requirement data from a Jira instance using the Jira REST API. The connection is configured via a `.toml` file.

#### Prerequisites:

1. **Install Jira extras:**
   ```powershell
   pip install testbench-requirement-service[jira]
   ```
   This installs the Jira Python client and HTML parsing libraries (`jira`, `beautifulsoup4`).

2. **Set up credentials** (if not already done):
   ```powershell
   testbench-requirement-service set-credentials
   ```

3. **Configure in your app configuration file** (`config.toml`):
   ```toml
   [testbench-requirement-service]
   reader_class = "JiraRequirementReader"
   reader_config_path = "jira_config.toml"
   ```
   See [Setup](#setup) for detailed configuration instructions.

4. **Set up Jira authentication:**
   - Create a `.env` file with your Jira credentials (see [Authentication methods](#authentication-methods) below)
   - Or configure credentials directly in the `.toml` file

5. **Create reader configuration file** (see [Configuration](#configuration-2) below)

#### Configuration:
The configuration for the reader is read from a `.toml` file with a `[jira]` table as the main section.

##### `[jira]`

| Setting                     | Type         | Description                                                                                                                                                                         | Required | Default                                                                                                                 |
| --------------------------- | ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ----------------------------------------------------------------------------------------------------------------------- |
| `server_url`              | String       | Base URL of the Jira REST API Server                                                                                                                                                | Yes      | -                                                                                                                       |
| `auth_type`               | String       | Authentication method to use (`basic`, `token`, `oauth`). See [Authentication methods](#authentication-methods) to pick the right flow.                                   | Yes      | `basic`                                                                                                               |
| `username`                | String       | Username for Jira authentication (only for `basic` auth when not using environment variables)                                                                                     | No       | -                                                                                                                       |
| `api_token`               | String       | API token or password for Jira authentication (only for `basic` auth when not using environment variables)                                                                        | No       | -                                                                                                                       |
| `baseline_field`          | String       | Field used to identify baselines in Jira                                                                                                                                            | No       | `fixVersions`                                                                                                         |
| `baseline_jql`            | String       | JQL query template used to select issues that belong to a specific baseline.<br />Available Placeholders:<br />• `{project}`: project name<br />• `{baseline}`: baseline name | No       | `project = "{project}" AND fixVersion = "{baseline}" AND issuetype in ("Epic", "Story", "User Story", "Task", "Bug")` |
| `current_baseline_jql`    | String       | JQL query template used to resolve the active/current baseline.<br />Available Placeholders:<br />• `{project}`: project name<br />• `{baseline}`: baseline name              | No       | `project = "{project}" AND issuetype in ("Epic", "Story", "User Story", "Task", "Bug")`                               |
| `requirement_group_types` | List[String] | List of Jira issue types considered as requirement groups                                                                                                                           | No       | `["Epic"]`                                                                                                            |
| `major_change_fields`     | List[String] | List of Jira fields where changes are treated as major changes (e.g. used for highlighting or reporting)                                                                   | No       | `["fixVersions"]`                                                                                                     |
| `minor_change_fields`     | List[String] | List of Jira fields where changes are treated as minor changes                                                                                                             | No       | `["summary", "description", "affectsVersions", "status"]`                                                             |
| `owner`                   | String       | Field used for the owner                                                                                                                                                            | No       | `assignee`                                                                                                            |
| `rendered_fields`         | List[String] | List of UDF fields that should be shown as rendered fields in the TestBench Client.<br />*Note*: Field has to be of type multiline text in order to be shown rendered             | No       | `[]`                                                                                                                  |

##### `[jira.projects.<project>]`

| Setting                     | Type         | Description                                                                                                                                                                                          | Required | Default                  |
| --------------------------- | ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ------------------------ |
| `baseline_field`          | String       | Project-specific field used to identify baselines in Jira                                                                                                                                            | No       | Inherits from `[jira]` |
| `baseline_jql`            | String       | Project-specific JQL query template used to select issues that belong to a specific baseline.<br />Available Placeholders:<br />• `{project}`: project name<br />• `{baseline}`: baseline name | No       | Inherits from `[jira]` |
| `current_baseline_jql`    | String       | Project-specific JQL query template used to resolve the active/current baseline.<br />Available Placeholders:<br />• `{project}`: project name<br />• `{baseline}`: baseline name              | No       | Inherits from `[jira]` |
| `requirement_group_types` | List[String] | Project-specific list of Jira issue types considered as requirement groups                                                                                                                           | No       | Inherits from `[jira]` |
| `major_change_fields`     | List[String] | List of Jira fields where changes are treated as major changes (e.g. used for highlighting or reporting)                                                                                    | No       | Inherits from `[jira]` |
| `minor_change_fields`     | List[String] | List of Jira fields where changes are treated as minor changes                                                                                                                            | No       | Inherits from `[jira]` |
| `owner`                   | String       | Project-specific field used for the owner                                                                                                                                                            | No       | Inherits from `[jira]` |
| `rendered_fields`         | List[String] | Project-specific list of UDF fields that should be shown as rendered fields in the TestBench Client.<br />*Note*: Field has to be of type multiline text in order to be shown rendered             | No       | Inherits from `[jira]` |

#### Authentication methods:
Pick the auth flow that matches your Jira deployment; the reader enforces the required secrets at startup using the same conventions as the [`jira` Python package](https://jira.readthedocs.io/examples.html#authentication). You can either place credentials in `[jira]` directly or provide the matching environment variables shown below.

| auth_type | When to use it | Required values |
| --- | --- | --- |
| `basic` | Atlassian Cloud and most Jira Data Center instances that still allow username + API token (or password). This is typically the simplest option. | Set `username` and `api_token` in the `[jira]` section or export `JIRA_USERNAME` and `JIRA_API_TOKEN`. |
| `token` | Jira Server/Data Center that issues Personal Access Tokens and disallows basic auth. | Set `token` in the `[jira]` section or export `JIRA_BEARER_TOKEN`.|
| `oauth` | Locked-down enterprise instances that require OAuth 1.0a with consumer keys and certificates. | Set `access_token`, `access_token_secret`, `consumer_key`, `key_cert` in the `[jira]` section or export `JIRA_ACCESS_TOKEN`, `JIRA_ACCESS_TOKEN_SECRET`, `JIRA_CONSUMER_KEY`, `JIRA_KEY_CERT`. |

#### Example Configuration:
```toml
# reader_config.toml

[jira]
server_url = "https://example.atlassian.net/"
auth_type = "basic"          # or "token" / "oauth"

# Optional authentication directly in config (alternative to env vars)
# username = "my-user@example.com"
# api_token = "my-apitoken"

# Optional: global JQL / field configuration
baseline_field = "fixVersions"
baseline_jql = "project = '{project}' AND fixVersion = '{baseline}' AND issuetype in (\"Epic\", \"Story\", \"User Story\", \"Task\", \"Bug\")"
current_baseline_jql = "project = '{project}' AND issuetype in (\"Epic\", \"Story\", \"User Story\", \"Task\", \"Bug\")"
requirement_group_types = ["Epic"]
major_change_fields = ["fixVersions"]
minor_change_fields = ["summary", "description", "affectsVersions", "status"]
owner = "assignee"
rendered_fields = ["Support Ticket", "Technical criteria", "Acceptance criteria"]

[jira.projects."Project A"]
# Project specific overrides (all optional)
baseline_field = "fixVersions"
baseline_jql = "fixVersion = '{baseline}'"
current_baseline_jql = "project = '{project}' AND fixVersion = '{baseline}'"
requirement_group_types = ["Initiative"]
owner = "creator"
```

#### Example `.env` file for basic authentication:

```text
JIRA_USERNAME=my-user@example.com
JIRA_API_TOKEN=my-apitoken
```

### SqlRequirementReader

Reads requirement data from SQL databases using SQLAlchemy and the provided ORM.

#### Prerequisites:

1. **Install SQL extras:**
  ```powershell
  pip install testbench-requirement-service[sql]
  ```
  This installs SQLAlchemy.

2. **Install a database driver** compatible with SQLAlchemy:
  - MariaDB/MySQL: `pymysql` or `mariadb`
  - Oracle: `oracledb`
  - SQLite: no extra driver required (built into Python)

3. **Configure in your app configuration file** (`config.toml`):
  ```toml
  [testbench-requirement-service]
  reader_class = "SqlRequirementReader"
  reader_config_path = "sql_config.toml"
  ```
  See [Setup](#setup) for detailed configuration instructions.

#### Configuration:
The configuration for the reader is read from a `.toml` file with a `[sql]` table as the main section.

##### `[sql]`

| Setting          | Type   | Description                                                                 | Required | Default |
| ---------------- | ------ | --------------------------------------------------------------------------- | -------- | ------- |
| `database_url` | String | SQLAlchemy database URL (includes user, password, host, port, and database) | Yes      | -       |
| `echo`         | Boolean | Enable SQLAlchemy SQL logging                                              | No       | `false` |
| `pool_pre_ping`| Boolean | Validate pooled connections before use                                     | No       | `true`  |

#### Example Configuration:
```toml
# sql_config.toml

[sql]
database_url = "mariadb+pymysql://USER:PASSWORD@HOST:3306/DBNAME"
echo = false
pool_pre_ping = true
```

Example database URLs:

- MariaDB (PyMySQL): `mariadb+pymysql://user:pass@host:3306/dbname`
- MariaDB (MariaDB Connector): `mariadb+mariadbconnector://user:pass@host:3306/dbname`
- Oracle (python-oracledb): `oracle+oracledb://user:pass@host:1521/?service_name=ORCLCDB`
- SQLite (relative file path): `sqlite:///./data/requirements.db`
- SQLite (absolute file path): `sqlite:////absolute/path/to/requirements.db`

## Custom RequirementReader Classes

If you want to implement your own custom requirement reader, you need to create a subclass of the [AbstractRequirementReader](src/testbench_requirement_service/readers/abstract_reader.py) class and implement all its abstract methods.

## Steps to create a custom RequirementReader class

**1. Create a new class**

- Inherit the [AbstractRequirementReader](src/testbench_requirement_service/readers/abstract_reader.py) class.
  ```python
  # custom_reader.py

  from testbench_requirement_service.readers.abstract_reader import AbstractRequirementReader

  class CustomRequirementReader(AbstractRequirementReader):
      def __init__(self, config_path: str):
          ...

      ...
  ```
- Implement all required abstract methods.

**2. Ensure compatibility**

- Your custom RequirementReader class **must implement** all required abstract methods.
- Make sure your import paths are **correct** based on your project structure.

**3. Start the service with your custom reader**

- To use your custom requirement reader, start the service with the `--reader-class` option, specifying the **import path** (module path) to the class.
  ```powershell
  testbench-requirement-service start --reader-class custom_reader.CustomRequirementReader
  ```

## Contributing

We welcome contributions! See [CONTRIBUTING](CONTRIBUTING.md) for details.

## License

This project is licensed under the Apache 2.0 License. See the [LICENSE](LICENSE) file for details.
