---
sidebar_position: 5
title: Custom Reader
---

# Custom Reader

If none of the built-in readers fit your data source, you can create your own by subclassing `AbstractRequirementReader`.

Typical use cases:

- Integrating a requirements source that is not supported out of the box (e.g. a REST API, database, or proprietary format).
- Wrapping an internal requirements management system.
- Building an adapter over an existing reporting or analytics backend.

---

## How It Works

At startup the service reads `reader_class` from `config.toml`, imports the class by its path or fully qualified Python dotted path, and instantiates it with the validated `reader_config` section. As long as your class is importable and implements the interface, no other changes to the service are required.

---

## Setup

### 1. Define a config model

Create a Pydantic `BaseModel` for your reader's configuration. The service uses this class to validate the config before passing it to your reader:

```python
# custom_reader.py

from pydantic import BaseModel


class CustomReaderConfig(BaseModel):
    source_path: str
    some_option: bool = False
```

If your reader requires no configuration, you can skip this and leave `CONFIG_CLASS = None`.

### 2. Implement the reader class

Inherit from `AbstractRequirementReader`, set `CONFIG_CLASS`, and implement all abstract methods. Your `__init__` receives an already-validated instance of your config model — you do not need to load or parse any config file yourself:

```python
from testbench_requirement_service.readers.abstract_reader import AbstractRequirementReader


class CustomRequirementReader(AbstractRequirementReader):
    CONFIG_CLASS = CustomReaderConfig

    def __init__(self, config: CustomReaderConfig):
        self.config = config

    # Implement all abstract methods ...
```

#### Required Methods

| Method | Purpose |
|--------|---------|
| `__init__(config)` | Initialise the reader with the validated config object. |
| `project_exists(project)` | Return `True` if the project exists in the data source. |
| `baseline_exists(project, baseline)` | Return `True` if the baseline exists for the project. |
| `get_projects()` | Return a list of all available project identifiers. |
| `get_baselines(project)` | Return a list of baselines for the given project. |
| `get_requirements_root_node(project, baseline)` | Return the root node of the requirements tree. |
| `get_user_defined_attributes()` | Return global user-defined attribute definitions. |
| `get_all_user_defined_attributes(project, baseline, requirement_keys, attribute_names)` | Return UDA values for the specified requirements. |
| `get_extended_requirement(project, baseline, key)` | Return a single requirement with all its attributes. |
| `get_requirement_versions(project, baseline, key)` | Return the version history of a requirement. |

#### Exception Conventions

Raise the following Sanic exceptions consistently so the service translates them into the correct HTTP responses:

| Situation | Exception |
|-----------|-----------|
| Project or baseline not found | `sanic.exceptions.NotFound` |
| Backend or data source error | `sanic.exceptions.ServerError` |
| Invalid input data | `pydantic.ValidationError` |

### 3. Make the class importable

Place your reader somewhere on the Python path. The simplest options are:

**Use a single file** in the directory you run the service from. File-path loading requires no additional setup.

**Add the directory to `PYTHONPATH`:**

```bash
export PYTHONPATH="/path/to/my_reader:$PYTHONPATH"
```

**Install as a package alongside the service:**

```bash
pip install ./custom_reader
```

:::warning
The reader must be importable from the same Python environment as the Requirement Service. Installing it globally or in a different virtual environment will result in an `ImportError` at startup.
:::

### 4. Configure the service

Point `reader_class` at your class and add the matching `reader_config` section.

**Using a file path (recommended for single-file readers):**

```toml
[testbench-requirement-service]
reader_class = "custom_reader.py"

[testbench-requirement-service.reader_config]
source_path = "/data/requirements"
some_option = true
```

**Using a module string (recommended for packaged readers):**

```toml
[testbench-requirement-service]
reader_class = "my_package.my_module.CustomRequirementReader"

[testbench-requirement-service.reader_config]
source_path = "/data/requirements"
some_option = true
```

**Using a separate config file** (referenced via `reader_config_path`):

```toml
[testbench-requirement-service]
reader_class = "custom_reader.py"
reader_config_path = "custom_reader_config.toml"
```

The `reader_class` option accepts several formats:

| Format | Example |
|--------|--------|
| File path (with extension) | `"custom_reader.py"` |
| File path (without extension) | `"custom_reader"` |
| Absolute file path | `"/opt/readers/custom_reader.py"` |
| Module string | `"my_package.CustomReader"` |
| Full dotted module path | `"my_package.my_module.CustomReader"` |

File paths are resolved relative to the directory you start the service from. For file-path loading the class is discovered automatically — either by deriving the PascalCase class name from the filename (`custom_reader.py` → `CustomReader`), or by scanning the file for the single `AbstractRequirementReader` subclass defined in it.

The `reader_config` keys must match the fields defined in your config Pydantic model. The service validates the section on startup and raises an error if required fields are missing or have the wrong type.

**Via CLI flag:**

```bash
testbench-requirement-service start --reader-class custom_reader.py
```

---

## Tips

- **Look at the JSONL reader** — `testbench_requirement_service.readers.jsonl` is the simplest complete reference implementation.
- **Logging** — import and use `from testbench_requirement_service.log import logger` instead of the standard `logging` module so your output appears in the same structured log stream.
- **No config needed** — setting `CONFIG_CLASS = None` disables config validation entirely; use this only if your reader truly requires no configuration.

