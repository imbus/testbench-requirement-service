---
sidebar_position: 5
title: Custom Readers
---

# Custom Readers

If none of the built-in readers fit your data source, you can create your own by subclassing `AbstractRequirementReader`.

## Steps

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

### 2. Create a new reader class

Inherit from `AbstractRequirementReader`, set `CONFIG_CLASS`, and implement all abstract methods. Your `__init__` receives an already-validated instance of your config model — you do not need to load or parse any config file yourself:

```python
from testbench_requirement_service.readers.abstract_reader import AbstractRequirementReader


class CustomRequirementReader(AbstractRequirementReader):
    CONFIG_CLASS = CustomReaderConfig

    def __init__(self, config: CustomReaderConfig):
        self.config = config

    # Implement all abstract methods:
    # - project_exists(project)
    # - baseline_exists(project, baseline)
    # - get_projects()
    # - get_baselines(project)
    # - get_requirements_root_node(project, baseline)
    # - get_user_defined_attributes()
    # - get_all_user_defined_attributes(project, baseline, requirement_keys, attribute_names)
    # - get_extended_requirement(project, baseline, key)
    # - get_requirement_versions(project, baseline, key)
```

### 3. Provide configuration

The service validates your `CONFIG_CLASS` against the reader config before starting. You can supply it inline or in a separate file.

**Inline in `config.toml`:**

```toml
[testbench-requirement-service]
reader_class = "custom_reader.py"

[testbench-requirement-service.reader_config]
source_path = "/data/requirements"
some_option = true
```

**As a separate config file** (referenced via `reader_config_path`):

```toml
[testbench-requirement-service]
reader_class = "custom_reader.py"
reader_config_path = "custom_reader_config.toml"
```

```toml
# custom_reader_config.toml
source_path = "/data/requirements"
some_option = true
```

### 4. Ensure compatibility

- Your class **must implement** all required abstract methods defined in `AbstractRequirementReader`.
- `CONFIG_CLASS` must be a subclass of `pydantic.BaseModel`. Setting it to `None` disables config validation (use only if your reader truly needs no configuration).
- Make sure your reader file or module is accessible from the directory where the service is started.

### 5. Start the service with your custom reader

The `reader_class` option (and the matching `--reader-class` CLI flag) accepts several formats:

| Format | Example |
|--------|---------|
| File path (recommended) | `"custom_reader.py"` |
| File path without extension | `"custom_reader"` |
| Absolute file path | `"/opt/readers/custom_reader.py"` |
| Module string | `"my_package.CustomReader"` |
| Full dotted path | `"my_package.my_module.CustomReader"` |

File paths are resolved relative to the directory you start the service from. Module strings are imported via `importlib` — the module must be on `PYTHONPATH` or in the working directory.

**Via CLI flag:**

```bash
testbench-requirement-service start --reader-class custom_reader.py
```

**Via `config.toml`:**

```toml
[testbench-requirement-service]
reader_class = "custom_reader.py"
```

:::tip
Place your custom reader file in the directory you run the service from, or pass an absolute path. For module-string imports, add the reader's directory to `PYTHONPATH` before starting:

```bash
PYTHONPATH=/path/to/readers testbench-requirement-service start
```
:::
