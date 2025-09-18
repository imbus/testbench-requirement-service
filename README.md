# TestBench Requirement Service - Python

A simple CLI tool to start and configure a TestBench Requirement Service.

## Table of contents

- [Installation](#installation)
- [Setup](#setup)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Built-in FileReader](#built-in-filereader)
- [Custom FileReader Classes](#custom-filereader-classes)
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

### 2. Optional: Install Excel functionality

If you need support for reading Excel files (`ExcelFileReader`), you should install the tool with the optional Excel dependencies:

```powershell
pip install testbench-requirement-service[excel]
```

This will install additional libraries like `pandas`, `openpyxl` and `xlrd`, which are required for handling Excel files.

### 3. Verify the installation

Once installed, verify the installation by checking the version:

```powershell
testbench-requirement-service --version
```

If the installation was successful, this will output the installed version of the tool.

## Setup

Before starting the service, you need to configure it.

### Step 1: Set up your service credentials

First, you need to set the credentials for your service in a configuration file. Use the integrated command `set-credentials`, which will automatically create a `config.py` in your current working directory. This file stores your credentials as a hashed password with a salt.

The server will verify requests using *Basic Auth*, comparing the username and password in incoming requests with the hash and salt stored in the `config.py` file.

If you'd like to store the configuration file elsewhere, you can specify the path with the `--config` option. However, remember that this config file is required for your service, and you will need to provide this path when starting the service if you change the default location.

You can run the following command without options, which will prompt you to enter your username and password:

```powershell
testbench-requirement-service set-credentials
```
Alternatively, you can specify the username and password directly in the command:

```powershell
testbench-requirement-service set-credentials --username USERNAME --password PASSWORD
```
If successful, a `config.py` file will be created with `PASSWORD_HASH` and `SALT` as the content.

### Step 2: Set up the file reader configuration

You will also need to configure the file reader that the service will use.

Create a `reader_config.py` file in your current working directory and define the necessary settings for the file reader. If you prefer to store the configuration file elsewhere, you can specify a custom path, but remember to provide this path when starting the service.

The file reader will receive the path to this configuration file as a parameter in its constructor, allowing it to load and work with your settings.

For the default file reader, `JsonlFileReader`, you must define at least the `BASE_DIR` setting in your `reader_config.py`. This should be the path to the directory containing the requirement files for your service.

Here’s an example of the minimum configuration for `JsonlFileReader`:

```python
# reader_config.py

BASE_DIR = "requirements/"
```

Once the configuration is complete, you're ready to start the service.

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

| Option            | Description | Default |
| ----------------- | ----------- | --------|
| `--config`        | Path to the app configuration file  | `config.py` |
| `--reader-class`  | Path or module string to the reader class | `testbench_requirement_service.readers.JsonlFileReader` |
| `--reader-config` | Path to the reader configuration file | `reader_config.py` |
| `--host`          | Host to run the service on | `127.0.0.1` |
| `--port`          | Port to run the service on | `8000` |
| `--dev`           | Run the service in dev mode (debug + auto reload) | Not set |

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
    testbench-requirement-service start --config path/to/config.py
    ```
- **Use a custom reader class**
    ```powershell
    testbench-requirement-service start --reader-class custom_readers/CustomFileReader.py
    ```

## API Documentation

Once your service is running, you can explore the available API documentation and OpenAPI specification using built-in endpoints.

### Interactive API Docs

The interactive API documentation is available at `/docs` and is powered by **Swagger UI**.
If the server is running locally with default settings, you can access it at: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Swagger UI allows you to test API endpoints directly, including authentication using the "Authorize" button.

### OpenAPI Specification

For the raw OpenAPI JSON schema, use the built-in endpoint `/docs/openapi.json`: [http://127.0.0.1:8000/docs/openapi.json](http://127.0.0.1:8000/docs/openapi.json)

## Built-in FileReader

The service includes built-in file reader classes that handle different file formats. Below is a list of the currently available readers:

### [JsonlFileReader](src/testbench_requirement_service/readers/JsonlFileReader.py) *(Default)*

- **Description**: Reads requirement data from `.jsonl` (JSON Lines) files. The configuration for the reader is specified in a Python `.py` file.
- **Required Configuration**:
    - `BASE_DIR`: Path to the directory containing the requirement files.
- **Required Schema**:
    - ***Projects*** are directories located at the top level inside `BASE_DIR`.
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
    - ***UserDefinedAttributes*** are specified in the `UserDefinedAttributes.json` file, located at the top level in `BASE_DIR`.
    This file follows the Schema below:
        ```json
        [
            {
                "name": "string", 
                "valueType": "STRING" | "ARRAY" | "BOOLEAN"
            }
        ]
        ```
- **Example Configuration**:
    Here's an example of how to configure the `JsonlFileReader` in the `.py` configuration file:
    ```python
    # reader_config.py
    BASE_DIR = "requirements/"
    ```


### [ExcelFileReader](src/testbench_requirement_service/readers/ExcelFileReader.py)

- **Description**: Reads requirement data from various file formats, including `.xlsx`, `.xls`, `.csv`, `.tsv`, and `.txt` files. The reader allows for flexible configuration to handle either Microsoft Excel formats (`.xlsx` or `.xls`) or CSV/Text files (`.csv`, `.tsv` or `.txt`).
- **Configuration**:
    The configuration for the reader is read from a Java Properties `.properties` file. By default, the reader uses a global `.properties` file, but if a project-specific `.properties` file is found, it can override the global configuration.
    - **Global Settings**:
        The global settings are mandatory. They can only be configured in the global configuration file.
        | Global Setting | Description | Example |
        | ----------------- | ----------- | ---- |
        | `requirementsDataPath` | Path to the root directory for requirement data  | `requirementsDataPath=requirements/excel`|
    - **Mandatory Settings**:
        All mandatory settings should be configured in the global configuration file. They can be overwritten by values in project-specific configuration files.
        | Mandatory Setting | Description | Example |
        | ----------------- | ----------- | ---- |
        | `columnSeparator` | Column separator in text files  | `columnSeparator=;`| 
        | `arrayValueSeparator` | Separator within a list of values | `arrayValueSeparator=,`|
        | `baselineFileExtensions` | Comma-separated list of allowed file extensions preceded by a dot. | `baselineFileExtensions=.tsv,.csv,.txt`|
    - **Optional Settings**:
        Optional settings can be specified in the global configuration file and can be overwritten by values in project-specific configuration files.
        | Optional Setting | Description | Example |
        | ----------------- | ----------- | ---- |
        | `useExcelDirectly` | `true`: Use Microsoft Excel files<br>`false`: Use text files like specified in `baselineFileExtensions` | `useExcelDirectly=false`| 
        | `baselinesFromSubfolders` | `true`: Searches for baseline files in all subfolders<br>`false`: Does not search for baseline files in subfolders | `baselinesFromSubfolders=true`|
        | `worksheetName` | Name of the worksheet to be used in the Excel files. If there is no corresponding worksheet, the first worksheet is used. | `worksheetName=Tabelle1`|
        | `dateFormat` | Date format in documents as Javas SimpleDateFormat | `dateFormat=yyyy-MM-dd HH:mm:ss`|
        | `header.rowIdx` | Line number of the header line in the requirement documents. Numbering starts at 1. | `header.rowIdx=1`|
        | `data.rowIdx` | Line number of the first requirement line. Numbering starts at 1. | `data.rowIdx=2`|
    - **Column Mapping: Attributes**:
        The column mapping of attributes configured in the global configuration file can be overwritten by values in project-specific configuration files. The column mapping for the attributes `íd`, `version` and `name` is mandatory. Column numbering starts at 1.
        | Column Mapping | Description | Example |
        | ----------------- | ----------- | ---- |
        | `requirement.hierarchyID` | Column containing the hierarchy ID of the requirement | `requirement.hierarchyID=2`|
        | `requirement.id` | Column containing the requirement id | `requirement.id=1`|
        | `requirement.version` | Column containing the version of the requirement | `requirement.version=6`|
        | `requirement.name` | Column containing the name of the requirement | `requirement.name=3`|
        | `requirement.owner` | Column containing the name of the person responsible for the requirement | `requirement.owner=4`|
        | `requirement.status` | Column containing the status of the requirement | `requirement.status=5`|
        | `requirement.priority` | Column containing the priority of the requirement | `requirement.priority=15`|
        | `requirement.comment` | Column containing the comment of the requirement | `requirement.comment=14`|
        | `requirement.date` | Column containing the version date of the requirement | `requirement.date=7`|
        | `requirement.description.<number>` | List of all columns that contain (parts of the) requirement description | `requirement.description.1=8`<br>`requirement.description.2=9`|
        | `requirement.references` | Column containing the file references of the requirement. <br> File references are separated from each other with the `arrayValueSeparator` | `requirement.references=13`|
        | `requirement.type` | Column containing the information if entry is a folder or a requirement | `requirement.type=10`|
        | `requirement.folderPattern` | Defines the regular expression pattern used to identify folders in the data.<br>Any value in the specified column (`requirement.type`) that matches this pattern will be considered a folder.<br>Default: `.*folder.*` | `requirement.folderPattern=.*folder.*`|
    - **Settings for User defined fields**:
        The settings for user defined fields (UDF) can only be configured in the global configuration file.
        | UDF Setting | Description | Example |
        | ----------------- | ----------- | ---- |
        | `udf.count` | Number of user defined fields to be used | `udf.count=2`|
        | `udf.attr#.name` | Name of the user defined field used in the TestBench | `udf.attr1.name=Risiko`|
        | `udf.attr#.column` | Column containing the user defined field | `udf.attr1.column=11`|
        | `udf.attr#.type` | Type of the user defined field. Can be `string`, `array` or `boolean`, case-insensitive | `udf.attr1.type=String`|
        | `udf.attr#.trueValue` | Attribute value that corresponds to TRUE. All other attribute values are interpreted as FALSE | `udf.attr2.trueValue=ja`|

    - **Example Configuration**:
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
- **Required Schema**:
    - ***Projects*** are directories located at the top level inside `requirementsDataPath`.
    - ***Baselines*** are excel files (`.xlsx` or `.xls`) or text files (`.tsv`, `.csv` or `.txt`) stored within a project directory. If the `baselinesFromSubfolders` setting is set to `true`, subfolders within the project directory are also searched for baseline files.
    - ***Requirements*** are represented as separate lines within a baseline file.
    - To use a ***project-specific configuration***, place a `.properties` file inside the project directory, named after the project. For example, if the project is named `Project1`, the configuration file must be named `Project1.properties`.

## Custom FileReader Classes

If you want to implement your own custom file reader, you need to create a subclass of the [AbstractFileReader](src/testbench_requirement_service/readers/abstract_file_reader.py) class and implement all its abstract methods.

## Steps to create a custom FileReader class

**1. Create a new class**
- Inherit the [AbstractFileReader](src/testbench_requirement_service/readers/abstract_file_reader.py) class.
    ```python
    # CustomFileReader.py

    from testbench_requirement_service.readers.abstract_file_reader import AbstractFileReader

    class CustomFileReader(AbstractFileReader):
        def __init__(self, config_path: str):
            ...
        
        ...
    ```
- Implement all required abstract methods.

**2. Ensure compatibility**
- Your custom FileReader class **must implement** all required abstract methods.
- Make sure your import paths are **correct** based on your project structure.

**3. Start the service with your custom reader**
- To use your custom file reader, start the service with the `--reader-class` option, specifying the **import path** (module path) to the class.
    ```powershell
    testbench-requirement-service start --reader-class path/to/CustomFileReader.py
    ```

## Contributing

We welcome contributions! See [CONTRIBUTING](CONTRIBUTING.md) for details.

## License

This project is licensed under the ... License – see the [LICENSE](LICENSE) file for details.
