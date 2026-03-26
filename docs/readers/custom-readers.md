---
sidebar_position: 5
title: Custom Readers
---

# Custom Readers

If none of the built-in readers fit your data source, you can create your own by subclassing `AbstractRequirementReader`.

## Steps

### 1. Create a new class

Inherit from `AbstractRequirementReader` and implement all abstract methods:

```python
# custom_reader.py

from testbench_requirement_service.readers.abstract_reader import AbstractRequirementReader


class CustomRequirementReader(AbstractRequirementReader):
    def __init__(self, config_path: str):
        # Initialize your reader, load config, etc.
        ...

    # Implement all abstract methods:
    # - get_projects()
    # - get_baselines(project)
    # - get_requirements_tree(project, baseline)
    # - etc.
```

### 2. Ensure compatibility

- Your class **must implement** all required abstract methods defined in `AbstractRequirementReader`.
- Make sure your import paths are correct relative to where the service is started.

### 3. Start the service with your custom reader

Use the `--reader-class` flag with the **module path** to your class:

```bash
testbench-requirement-service start --reader-class custom_reader.CustomRequirementReader
```

Or set it in `config.toml`:

```toml
[testbench-requirement-service]
reader_class = "custom_reader.CustomRequirementReader"
```

:::tip
The module must be importable from the working directory where the service is started. Place your custom reader file in the same directory or add its location to `PYTHONPATH`.
:::
