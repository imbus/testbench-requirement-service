from __future__ import annotations

import importlib
from pathlib import Path

# Python module name -> package name shown to end users.
REQUIRED_EXCEL_CONVERTER_MODULES: dict[str, str] = {
    "tomli_w": "tomli-w",
    "pandas": "pandas",
    "openpyxl": "openpyxl",
    "xlrd": "xlrd",
}


def get_missing_dependencies(required_modules: dict[str, str]) -> list[str]:
    """Return a sorted list of missing package names for the given import map."""
    missing: list[str] = []
    for module_name, package_name in required_modules.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(package_name)
    return sorted(set(missing))


def parse_properties(file_path: Path) -> dict[str, str]:
    """Parse a .properties file into a dictionary."""
    properties: dict[str, str] = {}
    with file_path.open("r", encoding="utf-8") as file_handle:
        for line in file_handle:
            stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith(("#", "!")):
                continue

            if "=" not in stripped_line:
                continue

            key, value = stripped_line.split("=", 1)
            properties[key.strip()] = value.strip()
    return properties


def convert_val(value: str) -> bool | int | float | str:
    """Convert string values into bool, int, or float when possible."""
    normalized = value.lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False

    try:
        return int(value)
    except ValueError:
        pass

    try:
        return float(value)
    except ValueError:
        return value


def _build_toml_dict(
    reader_config: dict[str, bool | int | float | str],
    include_base_template: bool,
):
    if include_base_template:
        return {
            "testbench-requirement-service": {
                "reader_class": "testbench_requirement_service.readers.ExcelRequirementReader",
                "host": "127.0.0.1",
                "port": 8020,
                "debug": False,
                "password_hash": "a3d0339584abd7307e250b319d1126d967c2890e677a7b9b466cca08031c6be6",
                "salt": "fY9qE8wBo7VRRNJoDAy7qg==",
                "reader_config": reader_config,
                "logging": {
                    "console": {
                        "log_level": "INFO",
                        "log_format": "%(asctime)s %(levelname)8s: %(message)s",
                    },
                    "file": {
                        "log_level": "INFO",
                        "log_format": "%(asctime)s - %(levelname)8s - %(name)s - %(message)s",
                        "file_path": "testbench-requirement-service.log",
                    },
                },
                "server": {
                    "single_process": True,
                    "keep_alive_timeout": 5,
                    "run_kwargs": {},
                },
            }
        }

    defaults: dict[str, float] = {
        "bufferMaxAgeMinutes": 1440.0,
        "bufferMaxSizeMiB": 1024.0,
        "bufferCleanupIntervalMinutes": 1.0,
    }
    for key, value in defaults.items():
        reader_config.setdefault(key, value)

    return {"testbench-requirement-service": {"reader_config": reader_config}}


def properties_to_toml(
    properties_file: Path,
    toml_output_file: Path,
    include_base_template: bool = False,
) -> None:
    """Convert a .properties file into a TOML config file."""
    props = parse_properties(properties_file)
    reader_config = {key: convert_val(raw_val) for key, raw_val in props.items()}
    toml_dict = _build_toml_dict(reader_config, include_base_template)

    # Import at runtime so callers can preflight dependency checks gracefully.
    try:
        tomli_w_module = importlib.import_module("tomli_w")
    except ImportError as exc:
        raise ImportError("Missing dependency: tomli-w") from exc

    with toml_output_file.open("wb") as file_handle:
        tomli_w_module.dump(toml_dict, file_handle)
