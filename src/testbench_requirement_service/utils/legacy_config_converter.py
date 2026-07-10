from __future__ import annotations

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import importlib

# Python module name -> package name shown to end users.
REQUIRED_EXCEL_CONVERTER_MODULES: dict[str, str] = {
    "tomli_w": "tomli-w",
    "pandas": "pandas",
    "openpyxl": "openpyxl",
    "xlrd": "xlrd",
}


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _convert_scalar(value: str) -> bool | int | float | str:
    raw = _strip_quotes(value)
    normalized = raw.lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False

    try:
        return int(raw)
    except ValueError:
        pass

    try:
        return float(raw)
    except ValueError:
        return raw


def parse_legacy_jira_conf(file_path: Path) -> dict[str, str]:
    """Parse legacy JiraRest.conf files with key/value pairs separated by ':'."""
    config: dict[str, str] = {}
    with file_path.open("r", encoding="utf-8") as file_handle:
        for line in file_handle:
            stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith("#"):
                continue
            if ":" not in stripped_line:
                continue

            key, value = stripped_line.split(":", 1)
            config[key.strip()] = _strip_quotes(value)
    return config


def _build_change_fields(version_field: str) -> tuple[list[str], list[str]]:
    if version_field == "empty":
        return [], []

    major_change_fields = [version_field]
    default_minor_fields = ["summary", "description", "status"]
    minor_change_fields = [f for f in default_minor_fields if f != version_field]
    return major_change_fields, minor_change_fields


def convert_jira_conf_to_reader_config(jira_conf: dict[str, str]) -> dict[str, object]:
    """Convert a legacy JiraRest.conf dictionary into reader_config values."""
    version_field = jira_conf.get("version", "updated")
    major_change_fields, minor_change_fields = _build_change_fields(version_field)

    timeout_ms = _convert_scalar(jira_conf.get("socket_timeout_ms", "30000"))
    timeout_seconds = 30
    if isinstance(timeout_ms, int):
        timeout_seconds = max(1, int(timeout_ms / 1000))

    render_description = _convert_scalar(jira_conf.get("render_description", "false"))
    rendered_fields: list[str] = ["description"] if render_description is True else []

    return {
        "server_url": jira_conf.get("url", ""),
        "auth_type": "basic",
        "verify_ssl": True,
        "baseline_field": jira_conf.get("baseline", "fixVersions"),
        "baseline_jql": jira_conf.get(
            "baseline_jql",
            'project = "{project}" AND fixVersion = "{baseline}" AND issuetype in standardIssueTypes()',
        ),
        "current_baseline_jql": jira_conf.get(
            "current_baseline_jql",
            'project = "{project}" AND issuetype in standardIssueTypes()',
        ),
        "owner_field": jira_conf.get("owner", "assignee"),
        "timeout": timeout_seconds,
        "rendered_fields": rendered_fields,
        "major_change_fields": major_change_fields,
        "minor_change_fields": minor_change_fields,
    }


def build_base_service_config(
    reader_class: str, reader_config: dict[str, object]
) -> dict[str, object]:
    """Build a full base requirement-service configuration with reader config."""
    return {
        "testbench-requirement-service": {
            "reader_class": reader_class,
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


def load_toml(path: Path) -> dict[str, object]:
    """Load a TOML file into a dictionary."""
    with path.open("rb") as file_handle:
        return tomllib.load(file_handle)


def build_project_reader_config(
    reader_type: str,
    reader_config: dict[str, object],
) -> dict[str, object]:
    """Build project-level reader config from converted legacy reader config values."""
    project_config = dict(reader_config)
    if reader_type == "jira" and "owner_field" in project_config:
        project_config["owner"] = project_config.pop("owner_field")
    return project_config


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


def properties_to_reader_config(
    properties_file: Path,
    include_defaults: bool = True,
) -> dict[str, bool | int | float | str]:
    """Convert a .properties file into a reader_config dictionary."""
    props = parse_properties(properties_file)
    reader_config = {key: convert_val(raw_val) for key, raw_val in props.items()}

    if include_defaults:
        defaults: dict[str, float] = {
            "bufferMaxAgeMinutes": 1440.0,
            "bufferMaxSizeMiB": 1024.0,
            "bufferCleanupIntervalMinutes": 1.0,
        }
        for key, value in defaults.items():
            reader_config.setdefault(key, value)

    return reader_config


def properties_to_toml(
    properties_file: Path,
    toml_output_file: Path,
    include_base_template: bool = False,
) -> None:
    """Convert a .properties file into a TOML config file."""
    reader_config = properties_to_reader_config(
        properties_file,
        include_defaults=not include_base_template,
    )
    toml_dict = _build_toml_dict(reader_config, include_base_template)

    # Import at runtime so callers can preflight dependency checks gracefully.
    try:
        tomli_w_module = importlib.import_module("tomli_w")
    except ImportError as exc:
        raise ImportError("Missing dependency: tomli-w") from exc

    with toml_output_file.open("wb") as file_handle:
        tomli_w_module.dump(toml_dict, file_handle)
