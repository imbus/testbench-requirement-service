# TestBench Requirement Service - Python

A REST API service for imbus TestBench that provides unified access to requirements from multiple sources (Jira, Excel, JSONL).

## Table of contents

- [Installation](#installation)
- [Setup](#setup)
- [CLI Commands](#cli-commands)
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

You can install both extras at once:

```powershell
pip install testbench-requirement-service[excel,jira]
```

### 3. Verify the installation

Once installed, verify the installation by checking the version:

```powershell
testbench-requirement-service --version
```

If the installation was successful, this will output the installed version of the tool.

## Setup

> **New users?** Use [Option 1: Interactive Wizard](#option-1-quick-start-with-interactive-wizard-recommended) for the fastest setup.
> 
> **Advanced users?** See [Option 2: Manual Configuration](#option-2-manual-configuration) for full control.

### Option 1: Quick Start with Interactive Wizard (Recommended)

Run the interactive configuration wizard:

```powershell
testbench-requirement-service init
```

This **single command** guides you through:
- Service settings (host, port, debug mode)
- Credentials setup (username, password)
- Reader selection (JSONL, Excel, Jira, or Custom)
- Reader-specific configuration

The wizard creates a complete `config.toml` file with all settings.

**Then start the service:**

```powershell
testbench-requirement-service start
```

**That's it!** Your service is ready to use.

---

### Option 2: Manual Configuration

If you prefer manual setup or need to customize existing configuration:

#### Step 1: Install optional dependencies (if needed)

Choose based on your data source:

| Reader | Data Source | Install Command |
|--------|-------------|-----------------|
| **[JsonlRequirementReader](#jsonlrequirementreader-default)** *(default)* | `.jsonl` files | Included in base install |
| **[ExcelRequirementReader](#excelrequirementreader)** | `.xlsx`, `.xls`, `.csv`, `.tsv`, `.txt` files | `pip install testbench-requirement-service[excel]` |
| **[JiraRequirementReader](#jirarequirementreader)** | Jira REST API | `pip install testbench-requirement-service[jira]` |

#### Step 2: Create configuration file

Create `config.toml` with your reader configuration. See the [Configuration](#configuration) section for detailed options, or jump directly to your reader:
- [JsonlRequirementReader configuration](#jsonlrequirementreader-default)
- [ExcelRequirementReader configuration](#excelrequirementreader)
- [JiraRequirementReader configuration](#jirarequirementreader)

**Quick example** (JsonlRequirementReader):

```toml
[testbench-requirement-service]
reader_class = "JsonlRequirementReader"
host = "127.0.0.1"
port = 8020

[testbench-requirement-service.reader_config]
requirements_path = "requirements/jsonl/"
```

#### Step 3: Set credentials

```powershell
testbench-requirement-service set-credentials
```

This prompts for username and password and securely stores them in `config.toml`.

#### Step 4: Start the service

```powershell
testbench-requirement-service start
```

---

**Tip:** Use `testbench-requirement-service configure` to update specific parts of your configuration later without starting from scratch.

**Note:** The legacy `config.py` (Python) format is still supported but will be deprecated in a future release. New projects should use TOML.

## CLI Commands

The TestBench Requirement Service provides several CLI commands to manage configuration and run the service.

### `init`

Initialize a new configuration file interactively with a full configuration wizard.

```powershell
testbench-requirement-service init [--path PATH]
```

**Options:**
- `--path PATH`: Path to the configuration file (default: `config.toml`)

This command launches an interactive wizard that guides you through:
1. Service settings configuration (host, port, debug mode)
2. Credential setup (username and password)
3. Reader selection (JSONL, Excel, Jira, or Custom)
4. Reader-specific configuration

The wizard creates a complete `config.toml` file with all settings in one place by default, but also offers the option to use separate configuration files for readers.

### `configure`

Update existing configuration files interactively.

```powershell
testbench-requirement-service configure [OPTIONS]
```

**Options:**
- `--path PATH`: Path to the app configuration file (default: `config.toml`)
- `--full`: Run full configuration wizard (skip menu)
- `--service-only`: Configure service settings only (host, port, debug)
- `--credentials-only`: Configure service credentials only (username, password)
- `--reader-only`: Configure reader settings only
- `--view`: View current configuration

**Examples:**

Update service settings:
```powershell
testbench-requirement-service configure --service-only
```

Update reader configuration:
```powershell
testbench-requirement-service configure --reader-only
```

View current configuration:
```powershell
testbench-requirement-service configure --view
```

Interactive menu (default):
```powershell
testbench-requirement-service configure
```

### `set-credentials`

Set or update service credentials for Basic Authentication.

```powershell
testbench-requirement-service set-credentials [OPTIONS]
```

**Options:**
- `--path PATH`: Path to the app configuration file (default: `config.toml`)
- `--username TEXT`: Username (prompts if not provided)
- `--password TEXT`: Password (prompts if not provided)

This command generates a secure password hash and salt, and stores them in your configuration file.

**Examples:**

Interactive (prompts for credentials):
```powershell
testbench-requirement-service set-credentials
```

Non-interactive:
```powershell
testbench-requirement-service set-credentials --username admin --password mypassword
```

### `start`

Start the TestBench Requirement Service.

```powershell
testbench-requirement-service start [OPTIONS]
```

**Options:**
- `--config PATH`: Path to the app configuration file (default: `config.toml`)
- `--reader-class PATH`: Reader class name or module path (overrides config file)
- `--reader-config PATH`: Path to the reader configuration file (overrides config file)
- `--host HOST`: Host to run the service on (overrides config file, default: `127.0.0.1`)
- `--port PORT`: Port to run the service on (overrides config file, default: `8020`)
- `--dev`: Run the service in dev mode (debug + auto reload)

Command-line arguments take precedence over configuration file settings.

**Examples:**

Start with default configuration:
```powershell
testbench-requirement-service start
```

Start in development mode:
```powershell
testbench-requirement-service start --dev
```

Override host and port:
```powershell
testbench-requirement-service start --host 0.0.0.0 --port 9000
```

Use different reader and config:
```powershell
testbench-requirement-service start --reader-class JiraRequirementReader --reader-config jira_config.toml
```

## Configuration

Your service can be configured using a configuration file in **TOML** format. The configuration file allows you to control service settings, reader selection, reader configuration, authentication, and logging behavior.

**Note:** The legacy `config.py` (Python) format is still supported but will be deprecated in a future release.

### Configuration file format

The configuration file uses TOML format with `[testbench-requirement-service]` as the main section. By default, all configuration (including reader-specific settings) is stored in a single `config.toml` file. Here's an example configuration with inline reader settings:

```toml
[testbench-requirement-service]
reader_class = "JsonlRequirementReader"
host = "127.0.0.1"
port = 8020
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

# Reader configuration (inline - recommended)
[testbench-requirement-service.reader_config]
requirements_path = "requirements/jsonl/"
```

### Configuration sections

#### `[testbench-requirement-service]`

| Option                 | Type   | Description                                                                  | Required | Default                                                                      |
| ---------------------- | ------ | ---------------------------------------------------------------------------- | -------- | ---------------------------------------------------------------------------- |
| `reader_class`       | String | Reader class name or module path                                            | No       | `"testbench_requirement_service.readers.JsonlRequirementReader"`          |
| `reader_config_path` | String | Path to a separate reader configuration file (optional, for using separate config files) | No       | `None` (reads from inline config sections)                                  |
| `host`               | String | Host address to run the service on                                          | No       | `"127.0.0.1"`                                                              |
| `port`               | Integer | Port number to run the service on                                           | No       | `8020`                                                                      |
| `ssl_cert`           | String | Path to SSL certificate file for HTTPS (enables HTTPS when set with `ssl_key`) | No    | `None`                                                                      |
| `ssl_key`            | String | Path to SSL private key file for HTTPS (enables HTTPS when set with `ssl_cert`) | No    | `None`                                                                      |
| `ssl_ca_cert`        | String | Path to CA certificate for client verification (optional, for mutual TLS) | No       | `None`                                                                      |
| `proxies_count`      | Integer | Number of proxies for X-Forwarded-For depth (see [Reverse proxy deployment](#reverse-proxy-deployment)) | No | `None` |
| `real_ip_header`     | String | Custom header name for client IP (e.g., `"X-Real-IP"`, `"CF-Connecting-IP"`) | No | `None` |
| `forwarded_secret`   | String | Secret token for Forwarded header validation (recommended for security) | No       | `None`                                                                      |
| `password_hash`      | String | Hashed password for Basic Auth (generated by `set-credentials` command)    | No       | -                                                                            |
| `salt`               | String | Salt value for password hashing (generated by `set-credentials` command)   | No       | -                                                                            |

**Notes:** 
- `password_hash` and `salt` are automatically generated when you run `testbench-requirement-service set-credentials`. You can also set these via environment variables `PASSWORD_HASH` and `SALT`.
- By default, reader configuration is stored inline under `[testbench-requirement-service.reader_config]` in the same `config.toml` file (recommended). Use `reader_config_path` only if you want to keep reader settings in a separate file.
- When using `reader_config_path`, the separate file contains reader configuration directly without any section prefix.
- **HTTPS/TLS Support**: Set both `ssl_cert` and `ssl_key` to enable HTTPS. For local testing, use self-signed certificates. For production, use certificates from a trusted CA (e.g., Let's Encrypt).
- **Mutual TLS (mTLS)**: Add `ssl_ca_cert` to enable client certificate verification. When configured, all clients must present valid certificates signed by the specified CA.

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

### Reverse proxy deployment

When deploying behind a reverse proxy (e.g. Nginx or Apache), configure these settings to ensure the service correctly processes proxy headers.

#### Configuration options

| Option              | Type    | Description                                                                  | Required | Default |
| ------------------- | ------- | ---------------------------------------------------------------------------- | -------- | ------- |
| `proxies_count`     | Integer | Number of proxy layers (for X-Forwarded-For header depth)                   | No       | `None` |
| `real_ip_header`    | String  | Custom header name for client IP (e.g., `"X-Real-IP"`) | No      | `None` |
| `forwarded_secret`  | String  | Secret token for RFC 7239 Forwarded header validation (most secure)         | No       | `None` |

**Header priority:**
1. `Forwarded` header (RFC 7239) - **only if** `forwarded_secret` is configured AND secret matches (all other headers ignored when matched)
2. Custom IP header specified in `real_ip_header`
3. `X-Forwarded-For` + other X-Forwarded-* headers (if `proxies_count` is set)
4. Direct connection IP (default when no proxy config)

**Security note**: Without configuration, the service ignores all proxy headers.

#### When to use each option

- **`proxies_count = 1`**: Most common setup. Use with standard `X-Forwarded-*` headers
- **`real_ip_header = "X-Real-IP"`**: Use when proxy sends client IP in a custom header
- **`forwarded_secret = "token"`**: Maximum security. Use RFC 7239 `Forwarded` header with shared secret between proxy and service

#### Understanding Forwarded header behavior

The `Forwarded` header (RFC 7239) provides the **most secure** proxy configuration:

- **Without `forwarded_secret`**: The service completely ignores all `Forwarded` headers (prevents header spoofing)
- **With matching secret**: The service uses `Forwarded` header exclusively, ignoring all X-Forwarded-* headers
- **With wrong/missing secret**: Falls back to `real_ip_header` or `proxies_count` configuration

This prevents malicious clients from faking proxy headers since they can't provide the secret shared between your proxy and service.

#### Example: Nginx with standard headers

**Nginx configuration:**
```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    
    location / {
        proxy_pass http://127.0.0.1:8020;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Service configuration:**
```toml
[testbench-requirement-service]
host = "127.0.0.1"  # Bind to localhost (proxy is on same machine)
port = 8020
proxies_count = 1   # Trust one proxy layer
```

**For RFC 7239 Forwarded header (most secure)**, add to Nginx:
```nginx
proxy_set_header Forwarded "for=$remote_addr;proto=$scheme;secret=your-token";
```

And configure service:
```toml
forwarded_secret = "your-token"  # Must match proxy secret
```

#### Security considerations

- **Bind to localhost** (`127.0.0.1`) when proxy is on the same machine to prevent bypassing
- **Use firewall rules** to ensure only your proxy can reach the service port
- **Choose configuration carefully**: Without proxy config, headers are ignored; with config, headers are trusted
- **For mTLS**: Proxy can terminate SSL and pass client cert info via custom headers, or pass through to service

#### Windows limitations

When using mTLS (`ssl_ca_cert`), the service runs in single-process mode on Windows. For production with mTLS:
- Deploy on Linux/Unix for multi-process support, or
- Use proxy-terminated mTLS (proxy handles certificates, service runs HTTP)

### Command-line overrides

Configuration values can be overridden at startup using command-line flags. Command-line arguments take precedence over configuration file settings.

**Example:** Override multiple settings:

```powershell
testbench-requirement-service start --config custom_config.toml --host 0.0.0.0 --port 9000 --reader-class JiraRequirementReader --reader-config jira_config.toml
```

**Example:** Use separate reader config file:

```powershell
testbench-requirement-service start --reader-config jira_config.toml
```

**Note:** When you use `--reader-config`, it overrides any inline reader configuration in the main config file.

See [CLI Commands](#cli-commands) or run `testbench-requirement-service start --help` for all available options.

## Usage

Now that your service is set up, you can start the service through the command-line interface.

### Start the Service

The basic command to start the service is:

```powershell
testbench-requirement-service start
```

By default, the service will run locally on `127.0.0.1:8020`. If you'd like to run it on a different host or port, use the following options:

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
| `--port`          | Port to run the service on                        | `8020`                                                         |
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
If the server is running locally with default settings, you can access it at: [http://127.0.0.1:8020/docs](http://127.0.0.1:8020/docs)

Swagger UI allows you to test API endpoints directly, including authentication using the "Authorize" button.

### OpenAPI Specification

For the raw OpenAPI JSON schema, use the built-in endpoint `/docs/openapi.json`: [http://127.0.0.1:8020/docs/openapi.json](http://127.0.0.1:8020/docs/openapi.json)

## Built-in RequirementReader

The service includes built-in requirement reader classes that handle different file formats. Jump directly to a reader:

- [JsonlRequirementReader (default)](#jsonlrequirementreader-default)
- [ExcelRequirementReader](#excelrequirementreader)
- [JiraRequirementReader](#jirarequirementreader)

Below is a detailed description of each reader:

### JsonlRequirementReader *(Default)*

Reads requirement data from `.jsonl` (JSON Lines) files.

**When to use**: You have requirement data in `.jsonl` format or want the simplest reader with no external dependencies.

**Installation**: Included in base package (no extras needed).

#### Configuration:
The configuration can be added directly to `config.toml` under `[testbench-requirement-service.reader_config]` (recommended) or in a separate `.toml` file without a section prefix.

##### Configuration Settings

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

  > **Full JSON Schema**: For validation and detailed type information, see [`requirement_object_schema.json`](src/testbench_requirement_service/readers/jsonl/schemas/requirement_object_schema.json)

  If the `"requirement"` attribute is set to `true`, the object represents an actual requirement. Otherwise, it serves only as a node in the requirements tree structure.
  Root requirement objects have their `"parent"` attribute set to `null`.

- ***UserDefinedAttributes*** are specified in the `UserDefinedAttributes.json` file, located at the top level in `requirements_path`.
  This file defines available attribute types and follows this Schema:

  ```json
  [
      {
          "name": "string",
          "valueType": "STRING" | "ARRAY" | "BOOLEAN"
      }
  ]
  ```

  > **Full JSON Schema**: For validation, see [`user_defined_attributes_schema.json`](src/testbench_requirement_service/readers/jsonl/schemas/user_defined_attributes_schema.json)

#### Example Configuration:

**Option 1: Inline configuration in `config.toml` (recommended):**

```toml
[testbench-requirement-service]
reader_class = "JsonlRequirementReader"

[testbench-requirement-service.reader_config]
requirements_path = "requirements/jsonl/"
```

**Option 2: Separate configuration file:**

```toml
# config.toml
[testbench-requirement-service]
reader_class = "JsonlRequirementReader"
reader_config_path = "reader_config.toml"
```

```toml
# reader_config.toml (no section prefix needed)
requirements_path = "requirements/jsonl/"
```

### ExcelRequirementReader

Reads requirement data from various file formats: `.xlsx`, `.xls`, `.csv`, `.tsv`, and `.txt` files.

**When to use**: You have requirements in Excel spreadsheets or delimited text files (CSV/TSV).

**Installation**: Requires Excel extras:
```powershell
pip install testbench-requirement-service[excel]
```

#### Configuration:
The configuration can be added directly to `config.toml` under `[testbench-requirement-service.reader_config]` (recommended) or in a separate Java Properties `.properties` file without a section prefix. 

When using a `.properties` file, the reader uses a global `.properties` file, but if a project-specific `.properties` file is found, it can override the global configuration.

> **⚠️ IMPORTANT: Windows Paths in .properties Files**
> 
> Java `.properties` files treat backslashes (`\`) as escape characters, which causes **critical issues with Windows paths**:
> 
> - `C:\folder\file` → Parsed as `C:` + FORM-FEED + `older` + FORM-FEED + `ile` ❌
> - `\\server\temp\data` → Parsed as `\server` + TAB + `emp` + TAB + `ata` ❌
> 
> **Solutions** (choose one):
> 
> 1. **Use forward slashes** (recommended - simplest):
>    ```properties
>    requirementsDataPath = C:/path/to/folder
>    requirementsDataPath = //server/share/folder
>    ```
>    Windows accepts forward slashes in paths.
> 
> 2. **Double-escape backslashes** (4 backslashes = 1 actual backslash):
>    ```properties
>    requirementsDataPath = C:\\\\path\\\\to\\\\folder
>    requirementsDataPath = \\\\\\\\server\\\\share\\\\folder
>    ```
> 

**Dataframe buffering:** The Excel reader keeps a catalog of dataframes keyed by file path. A cached dataframe is reused if the source file modification time matches, and each access refreshes the entry age. Entries expire after `bufferMaxAgeMinutes`, and a background cleanup task runs every `bufferCleanupIntervalMinutes`. If the total buffer size exceeds `bufferMaxSizeMiB`, the reader evicts the least-recently accessed entries until the buffer is back to $80\%$ of the limit. Set `bufferMaxSizeMiB=0` or `bufferMaxAgeMinutes=0` to disable buffering entirely.
- **Global Settings**:
  The global settings are mandatory. They can only be configured in the global configuration file.

  | Global Setting           | Description                                     | Example                                     |
  | ------------------------ | ----------------------------------------------- | ------------------------------------------- |
  | `requirementsDataPath` | Path to the root directory for requirement data. **For .properties files:** Use forward slashes (`/`) or double-escape backslashes (`\\\\`) | `requirementsDataPath=C:/requirements/excel` or `requirementsDataPath=//server/share` |
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
  | `useExcelDirectly`        | `true`: Use Microsoft Excel files<br>`false`: Use text files like specified in `baselineFileExtensions`            | `useExcelDirectly=false`         |
  | `baselinesFromSubfolders` | `true`: Searches for baseline files in all subfolders<br>`false`: Does not search for baseline files in subfolders   | `baselinesFromSubfolders=true`   |
  | `worksheetName`           | Name of the worksheet to be used in the Excel files. If there is no corresponding worksheet, the first worksheet is used. | `worksheetName=Tabelle1`         |
  | `dateFormat`              | Date format for requirement version dates. Accepts **Java SimpleDateFormat** strings (e.g. `yyyy-MM-dd HH:mm:ss`) for backwards compatibility as well as **Python strftime** strings (e.g. `%Y-%m-%d %H:%M:%S`). The format type is detected automatically: strings containing `%` directives are treated as Python strftime; all other strings are treated as Java SimpleDateFormat. If the configured format cannot parse a date value, `dateutil` automatic detection is used as fallback and a warning is logged. | `dateFormat=yyyy-MM-dd HH:mm:ss` |
  | `header.rowIdx`           | Line number of the header line in the requirement documents. Numbering starts at 1.                                       | `header.rowIdx=1`                |
  | `data.rowIdx`             | Line number of the first requirement line. Numbering starts at 1.                                                         | `data.rowIdx=2`                  |
  | `bufferMaxAgeMinutes`       | Maximum idle age (in minutes) before a buffered dataframe is evicted. Set to `0` to disable buffering.                      | `bufferMaxAgeMinutes=1440`       |
  | `bufferMaxSizeMiB`          | Maximum total buffer size in MiB. When exceeded, least-recently accessed entries are evicted until $80\%$ of the limit is reached again. Set to $0$ to disable buffering. | `bufferMaxSizeMiB=1024`          |
  | `bufferCleanupIntervalMinutes` | Background cleanup interval in minutes for expiring cached dataframes.                                              | `bufferCleanupIntervalMinutes=1` |
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
  | `requirement.description.<number>` | List of all columns that contain (parts of the) requirement description                                                                                                                                                            | `requirement.description.1=8`<br>`requirement.description.2=9` |
  | `requirement.references`           | Column containing the file references of the requirement.<br>File references are separated from each other with the `arrayValueSeparator`                                                                                   | `requirement.references=13`                                    |
  | `requirement.type`                 | Column containing the information if entry is a folder or a requirement                                                                                                                                                            | `requirement.type=10`                                          |
  | `requirement.folderPattern`        | Defines the regular expression pattern used to identify folders in the data.<br>Any value in the specified column (`requirement.type`) that matches this pattern will be considered a folder.<br>Default: `.*folder.*` | `requirement.folderPattern=.*folder.*`                         |
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

**Note:** When using inline configuration in `config.toml`, the same properties can be configured under `[testbench-requirement-service.reader_config]` using TOML syntax. For example:

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
"requirement.name" = 3
# ... other settings
```

#### Required Schema:
- ***Projects*** are directories located at the top level inside `requirementsDataPath`.
- ***Baselines*** are excel files (`.xlsx` or `.xls`) or text files (`.tsv`, `.csv` or `.txt`) stored within a project directory. If the `baselinesFromSubfolders` setting is set to `true`, subfolders within the project directory are also searched for baseline files.
- ***Requirements*** are represented as separate lines within a baseline file.
- To use a ***project-specific configuration***, place a `.properties` file inside the project directory, named after the project. For example, if the project is named `Project1`, the configuration file must be named `Project1.properties`.

### JiraRequirementReader

Reads requirement data from a Jira instance using the Jira REST API.

**When to use**: Your requirements are managed in Jira issues (Stories, Epics, Tasks, etc.).

**Tested Jira instances**: Compatibility is ensured for the following Jira deployments. Other versions may work but are not officially supported.

| Deployment       | Version |
| ---------------- | ------- |
| Jira Cloud       | latest  |
| Jira Data Center | 11.3    |
| Jira Data Center | 10.3    |
| Jira Data Center | 9.4     |

**Installation**: Requires Jira extras:
```powershell
pip install testbench-requirement-service[jira]
```

**Authentication**: Create a `.env` file with your Jira credentials (see [Authentication methods](#authentication-methods) below) or configure credentials in `config.toml`.

#### Configuration:
The configuration can be added directly to `config.toml` under `[testbench-requirement-service.reader_config]` (recommended) or in a separate `.toml` file without a section prefix.

##### Configuration Settings

**Connection**

| Setting        | Type    | Description                                                                                                                                               | Required | Default  |
| -------------- | ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | -------- |
| `server_url` | String  | Base URL of the Jira instance (e.g. `https://your-company.atlassian.net`)                                                                               | Yes      | -        |
| `auth_type`  | String  | Authentication method to use (`basic`, `token`, `oauth1`). See [Authentication methods](#authentication-methods) to pick the right flow.               | No       | `basic`  |
| `timeout`    | Integer | HTTP request timeout in seconds for Jira API calls (1–300)                                                                                               | No       | `30`     |
| `max_retries`| Integer | Maximum number of retries for failed Jira API requests (0–10)                                                                                            | No       | `3`      |
| `cache_ttl`  | Float   | Time-to-live in seconds for all internal caches. Set to `0` to disable caching.                                                                         | No       | `300.0`  |

**Basic authentication** (`auth_type = "basic"` — Jira Cloud)

| Setting      | Type   | Description                                                  | Required | Env var          |
| ------------ | ------ | ------------------------------------------------------------ | -------- | ---------------- |
| `username`   | String | Jira account username (e-mail for Jira Cloud)                                                               | Yes      | `JIRA_USERNAME`  |
| `password`   | String | Password for basic auth. Use an API token on Jira Cloud, account password on Jira Data Center.       | Yes      | `JIRA_PASSWORD`  |

**Token authentication** (`auth_type = "token"` — Jira Server/Data Center)

| Setting   | Type   | Description                                       | Required | Env var              |
| --------- | ------ | ------------------------------------------------- | -------- | -------------------- |
| `token`   | String | Personal Access Token (PAT) (sensitive)           | Yes      | `JIRA_BEARER_TOKEN`  |

**OAuth1 authentication** (`auth_type = "oauth1"` — enterprise instances)

| Setting                       | Type   | Description                                                                                           | Required | Env var                           |
| ----------------------------- | ------ | ----------------------------------------------------------------------------------------------------- | -------- | --------------------------------- |
| `oauth1_access_token`         | String | OAuth1 access token (sensitive)                                                                       | Yes      | `JIRA_OAUTH1_ACCESS_TOKEN`        |
| `oauth1_access_token_secret`  | String | OAuth1 access token secret (sensitive)                                                                | Yes      | `JIRA_OAUTH1_ACCESS_TOKEN_SECRET` |
| `oauth1_consumer_key`         | String | OAuth1 consumer key                                                                                   | Yes      | `JIRA_OAUTH1_CONSUMER_KEY`        |
| `oauth1_key_cert_path`        | String | Path to the OAuth1 RSA private key file (`.pem`). The file content is read at startup.               | Yes     | `JIRA_OAUTH1_KEY_CERT_PATH`       |

**SSL verification** (all auth types, optional)

| Setting            | Type    | Description                                                                                                                                                          | Required | Default | Env var                  |
| ------------------ | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ------- | ------------------------ |
| `verify_ssl`       | Boolean | Enable SSL certificate verification. Set to `false` only in dev/test environments when a CA cert file cannot be provided. Disabling exposes the connection to MITM attacks. | No | `true`  | `JIRA_VERIFY_SSL`        |
| `ssl_ca_cert_path` | String  | Path to a CA certificate or bundle file (`.pem`/`.crt`) used to verify the Jira server's SSL certificate. Use this when Jira uses a self-signed or corporate CA certificate. | No | -       | `JIRA_SSL_CA_CERT_PATH`  |

**Mutual TLS (mTLS) client certificate** (all auth types, optional)

| Setting             | Type   | Description                                                                                                                      | Required | Env var                  |
| ------------------- | ------ | -------------------------------------------------------------------------------------------------------------------------------- | -------- | ------------------------ |
| `client_cert_path`  | String | Path to the client certificate file for mutual TLS (`.pem` or `.crt`). Can be a combined cert+key file.                         | No       | `JIRA_CLIENT_CERT_PATH`  |
| `client_key_path`   | String | Path to the client private key file (`.key` or `.pem`). Only required when the key is stored separately from the certificate.   | No       | `JIRA_CLIENT_KEY_PATH`   |

**Requirements & baselines**

| Setting                     | Type         | Description                                                                                                                                                                         | Required | Default                                                                                                                                  |
| --------------------------- | ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `baseline_field`            | String       | Jira field used to identify baselines/versions (e.g. `fixVersions`, `sprint`, or a custom field ID)                                                                                | No       | `fixVersions`                                                                                                                            |
| `baseline_jql`              | String       | JQL template for fetching issues of a specific baseline. Placeholders: `{project}`, `{baseline}`                                                                                   | No       | `project = "{project}" AND fixVersion = "{baseline}" AND issuetype in standardIssueTypes()`                                              |
| `current_baseline_jql`      | String       | JQL template for fetching the current/active baseline. Placeholder: `{project}`                                                                                                     | No       | `project = "{project}" AND issuetype in standardIssueTypes()`                                                                            |
| `requirement_group_types`   | List[String] | Issue types treated as requirement groups/folders (e.g. Epics)                                                                                                                      | No       | `["Epic"]`                                                                                                                               |
| `major_change_fields`       | List[String] | Fields whose changes count as a major version bump                                                                                                                                  | No       | `["fixVersions"]`                                                                                                                        |
| `minor_change_fields`       | List[String] | Fields whose changes count as a minor version bump                                                                                                                                  | No       | `["summary", "description", "affectsVersions", "status"]`                                                                               |
| `owner_field`               | String       | Jira field used as the requirement owner                                                                                                                                            | No       | `assignee`                                                                                                                               |
| `rendered_fields`           | List[String] | Fields to render as HTML in TestBench. The field must be of type *multiline text* in Jira.                                                                                          | No       | `[]`                                                                                                                                     |

##### Project-Specific Settings (`projects.<project>` subsection)

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
| `basic` | Jira Cloud and Jira Data Center instances using username + password. On Jira Cloud the password must be an API token. | Set `username` and `password` in the `[jira]` section or export `JIRA_USERNAME` and `JIRA_PASSWORD`. |
| `token` | Jira Server/Data Center that issues Personal Access Tokens and disallows basic auth. | Set `token` in the `[jira]` section or export `JIRA_BEARER_TOKEN`.|
| `oauth1` | Locked-down enterprise instances that require OAuth 1.0a with consumer keys and certificates. | Set `oauth1_access_token`, `oauth1_access_token_secret`, `oauth1_consumer_key`, `oauth1_key_cert_path` in the `[jira]` section or export `JIRA_OAUTH1_ACCESS_TOKEN`, `JIRA_OAUTH1_ACCESS_TOKEN_SECRET`, `JIRA_OAUTH1_CONSUMER_KEY`, `JIRA_OAUTH1_KEY_CERT_PATH`. |

#### Example Configuration:

**Option 1: Inline configuration in `config.toml` (recommended):**

```toml
[testbench-requirement-service]
reader_class = "JiraRequirementReader"

[testbench-requirement-service.reader_config]
server_url = "https://example.atlassian.net/"
auth_type = "basic"          # or "token" / "oauth1"

# Basic auth credentials (alternative to env vars JIRA_USERNAME / JIRA_PASSWORD)
# On Jira Cloud the password is an API token (generate at id.atlassian.com).
# username = "my-user@example.com"
# password = "my-api-token-or-password"

# Token auth credential (alternative to env var JIRA_BEARER_TOKEN)
# token = "my-personal-access-token"

# OAuth1 auth credentials (alternative to env vars)
# oauth1_access_token        = "my-access-token"
# oauth1_access_token_secret = "my-access-token-secret"
# oauth1_consumer_key        = "my-consumer-key"
# oauth1_key_cert_path       = "/path/to/private-key.pem"

# Mutual TLS client certificate (optional, all auth types)
# client_cert_path = "/path/to/client.crt"
# client_key_path  = "/path/to/client.key"

# Connection tuning (optional)
# timeout     = 30
# max_retries = 3
# cache_ttl   = 300.0

# Requirement & baseline configuration (optional)
baseline_field = "fixVersions"
baseline_jql = 'project = "{project}" AND fixVersion = "{baseline}" AND issuetype in standardIssueTypes()'
current_baseline_jql = 'project = "{project}" AND issuetype in standardIssueTypes()'
requirement_group_types = ["Epic"]
major_change_fields = ["fixVersions"]
minor_change_fields = ["summary", "description", "affectsVersions", "status"]
owner_field = "assignee"
rendered_fields = ["Acceptance Criteria", "Technical Specification"]

[testbench-requirement-service.reader_config.projects."Project A"]
# Project-specific overrides (all optional, inherit from global config when omitted)
baseline_field = "fixVersions"
baseline_jql = 'fixVersion = "{baseline}"'
current_baseline_jql = 'project = "{project}" AND fixVersion = "{baseline}"'
requirement_group_types = ["Initiative"]
owner = "creator"
```

**Option 2: Separate configuration file:**

```toml
# config.toml
[testbench-requirement-service]
reader_class = "JiraRequirementReader"
reader_config_path = "jira_config.toml"
```

```toml
# jira_config.toml (no section prefix needed)
server_url = "https://example.atlassian.net/"
auth_type = "basic"
# ... same settings as Option 1 above

[projects."Project A"]
# Project-specific overrides (all optional)
baseline_field = "fixVersions"
baseline_jql = 'fixVersion = "{baseline}"'
current_baseline_jql = 'project = "{project}" AND fixVersion = "{baseline}"'
requirement_group_types = ["Initiative"]
owner = "creator"
```

#### Example `.env` file:

```text
# Basic authentication (Jira Cloud)
JIRA_USERNAME=my-user@example.com
JIRA_PASSWORD=my-api-token

# Token authentication (Jira Server/Data Center)
# JIRA_BEARER_TOKEN=my-personal-access-token

# OAuth1 authentication
# JIRA_OAUTH1_ACCESS_TOKEN=my-access-token
# JIRA_OAUTH1_ACCESS_TOKEN_SECRET=my-access-token-secret
# JIRA_OAUTH1_CONSUMER_KEY=my-consumer-key
# JIRA_OAUTH1_KEY_CERT_PATH=/path/to/private-key.pem

# Mutual TLS client certificate (optional, all auth types)
# JIRA_CLIENT_CERT_PATH=/path/to/client.crt
# JIRA_CLIENT_KEY_PATH=/path/to/client.key
```

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
