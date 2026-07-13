from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from typing import Any, Literal

import tomli_w

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

# Python module name -> package name shown to end users.
REQUIRED_EXCEL_CONVERTER_MODULES: dict[str, str] = {
    "tomli_w": "tomli-w",
    "pandas": "pandas",
    "openpyxl": "openpyxl",
    "xlrd": "xlrd",
}

MIN_QUOTED_LENGTH = 2


class ConfConversionError(ValueError):
    """Raised when legacy config conversion cannot be completed."""


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= MIN_QUOTED_LENGTH and value[0] == value[-1] and value[0] in {'"', "'"}:
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


def parse_conf_file(file_path: Path) -> dict[str, str]:
    """Parse a Jira-style .conf file into a flat dictionary."""
    try:
        return parse_legacy_jira_conf(file_path)
    except OSError as exc:
        raise ConfConversionError(f"Could not read conf file '{file_path}': {exc}") from exc


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
            (
                'project = "{project}" AND fixVersion = "{baseline}" '
                "AND issuetype in standardIssueTypes()"
            ),
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


def generate_base_toml(conf_data: dict[str, str]) -> dict[str, object]:
    """Generate a complete base TOML payload from Jira conf data."""
    reader_config = convert_jira_conf_to_reader_config(conf_data)
    return build_base_service_config(
        "testbench_requirement_service.readers.JiraRequirementReader",
        reader_config,
    )


def load_toml(path: Path) -> dict[str, object]:
    """Load a TOML file into a dictionary."""
    with path.open("rb") as file_handle:
        return tomllib.load(file_handle)


def _load_toml_file(file_path: Path) -> dict[str, Any]:
    """Load TOML content from disk, returning an empty dict when file is missing."""
    if not file_path.exists():
        return {}

    try:
        data = load_toml(file_path)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfConversionError(f"Could not read TOML file '{file_path}': {exc}") from exc

    if not isinstance(data, dict):
        raise ConfConversionError(f"Invalid TOML root in '{file_path}'")
    return data


def _write_toml_file(file_path: Path, data: dict[str, Any]) -> None:
    """Write TOML content using tomli_w."""
    try:
        with file_path.open("wb") as toml_file:
            tomli_w.dump(data, toml_file)
    except OSError as exc:
        raise ConfConversionError(f"Could not write TOML file '{file_path}': {exc}") from exc


def build_project_reader_config(
    reader_type: str,
    reader_config: dict[str, object],
) -> dict[str, object]:
    """Build project-level reader config from converted legacy reader config values."""
    project_config = dict(reader_config)
    if reader_type == "jira" and "owner_field" in project_config:
        project_config["owner"] = project_config.pop("owner_field")
    return project_config


def _validate_project_name(project_name: str) -> str:
    value = project_name.strip()
    if not value:
        raise ConfConversionError("Project name cannot be empty")
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", value):
        raise ConfConversionError(
            "Project name must contain only letters, digits, underscore, or hyphen"
        )
    return value


def generate_project_toml(conf_data: dict[str, str], project_name: str) -> dict[str, object]:
    """Generate project-specific Jira reader config payload from conf data."""
    validated_name = _validate_project_name(project_name)
    reader_config = convert_jira_conf_to_reader_config(conf_data)
    return {validated_name: build_project_reader_config("jira", reader_config)}


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


def parse_properties_file(file_path: Path) -> dict[str, str]:
    """Parse a Java .properties file into a flat dictionary."""
    try:
        return parse_properties(file_path)
    except OSError as exc:
        raise ConfConversionError(f"Could not read properties file '{file_path}': {exc}") from exc


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


def generate_excel_base_toml(properties: dict[str, str]) -> dict[str, object]:
    """Generate a complete base TOML payload for the Excel reader."""
    return build_base_service_config(
        "testbench_requirement_service.readers.ExcelRequirementReader",
        properties_to_reader_config_dict(properties),
    )


def generate_excel_project_toml(properties: dict[str, str], project_name: str) -> dict[str, object]:
    """Generate Excel reader project config payload from properties file."""
    validated_name = _validate_project_name(project_name)
    return {
        validated_name: build_project_reader_config(
            "excel",
            properties_to_reader_config_dict(properties),
        )
    }


def properties_to_reader_config_dict(
    properties: dict[str, str],
) -> dict[str, bool | int | float | str]:
    """Convert parsed properties values to reader config scalars with defaults."""
    reader_config = {key: convert_val(raw_val) for key, raw_val in properties.items()}
    defaults: dict[str, float] = {
        "bufferMaxAgeMinutes": 1440.0,
        "bufferMaxSizeMiB": 1024.0,
        "bufferCleanupIntervalMinutes": 1.0,
    }
    for key, value in defaults.items():
        reader_config.setdefault(key, value)
    return reader_config


def extract_common_fields(conf_data: dict[str, str]) -> tuple[str, str, str, str, int]:
    """Extract shared Jira reader settings from parsed conf data."""
    reader_config = convert_jira_conf_to_reader_config(conf_data)
    return (
        str(reader_config.get("server_url", "")),
        str(reader_config.get("baseline_field", "fixVersions")),
        str(reader_config.get("baseline_jql", "")),
        str(reader_config.get("owner_field", "assignee")),
        int(reader_config.get("timeout", 30)),
    )


def convert_jira_conf(
    input_file: Path,
    output_file: Path,
    mode: Literal["overwrite", "add-project"],
    project_name: str | None = None,
) -> str:
    """Convert JiraRest.conf into base TOML or append a project section."""
    conf_data = parse_conf_file(input_file)

    if mode == "overwrite":
        payload = generate_base_toml(conf_data)
        _write_toml_file(output_file, payload)
        return f"Successfully wrote mapped TOML to {output_file}"

    if mode == "add-project":
        if project_name is None:
            raise ConfConversionError("Project name is required when mode is 'add-project'")

        payload = _load_toml_file(output_file)
        app_cfg = payload.setdefault("testbench-requirement-service", {})
        if not isinstance(app_cfg, dict):
            raise ConfConversionError("Invalid TOML shape for [testbench-requirement-service]")
        reader_cfg = app_cfg.setdefault("reader_config", {})
        if not isinstance(reader_cfg, dict):
            raise ConfConversionError(
                "Invalid TOML shape for [testbench-requirement-service.reader_config]"
            )
        projects_cfg = reader_cfg.setdefault("projects", {})
        if not isinstance(projects_cfg, dict):
            raise ConfConversionError(
                "Invalid TOML shape for [testbench-requirement-service.reader_config.projects]"
            )

        projects_cfg.update(generate_project_toml(conf_data, project_name))
        _write_toml_file(output_file, payload)
        return f"Successfully appended project '{project_name}' to {output_file}"

    raise ConfConversionError(f"Unsupported conversion mode: {mode}")


def convert_excel_properties(
    input_file: Path,
    output_file: Path,
    mode: Literal["overwrite", "add-project"],
    project_name: str | None = None,
) -> str:
    """Convert ExcelWrapper.properties into base TOML or append a project section."""
    properties = parse_properties_file(input_file)

    if mode == "overwrite":
        payload = generate_excel_base_toml(properties)
        _write_toml_file(output_file, payload)
        return f"Successfully wrote mapped TOML to {output_file}"

    if mode == "add-project":
        if project_name is None:
            raise ConfConversionError("Project name is required when mode is 'add-project'")

        payload = _load_toml_file(output_file)
        app_cfg = payload.setdefault("testbench-requirement-service", {})
        if not isinstance(app_cfg, dict):
            raise ConfConversionError("Invalid TOML shape for [testbench-requirement-service]")
        reader_cfg = app_cfg.setdefault("reader_config", {})
        if not isinstance(reader_cfg, dict):
            raise ConfConversionError(
                "Invalid TOML shape for [testbench-requirement-service.reader_config]"
            )
        projects_cfg = reader_cfg.setdefault("projects", {})
        if not isinstance(projects_cfg, dict):
            raise ConfConversionError(
                "Invalid TOML shape for [testbench-requirement-service.reader_config.projects]"
            )

        projects_cfg.update(generate_excel_project_toml(properties, project_name))
        _write_toml_file(output_file, payload)
        return f"Successfully appended project '{project_name}' to {output_file}"

    raise ConfConversionError(f"Unsupported conversion mode: {mode}")
