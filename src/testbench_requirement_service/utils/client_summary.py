"""Summarise the configured requirement reader for the startup log."""

from collections.abc import Callable
import platform
from pathlib import Path, PurePath
import sys
from typing import Any

from pydantic import BaseModel

from testbench_requirement_service.config import AppConfig
from testbench_requirement_service.log import logger
from testbench_requirement_service.readers.excel.config import ExcelRequirementReaderConfig
from testbench_requirement_service.readers.jira.config import JiraRequirementReaderConfig
from testbench_requirement_service.readers.jsonl.config import JsonlRequirementReaderConfig

INDENT = "  "


def _jsonl_source(reader_config: JsonlRequirementReaderConfig) -> str:
    return Path(reader_config.requirements_path).as_posix()


def _excel_source(reader_config: ExcelRequirementReaderConfig) -> str:
    source = Path(reader_config.requirementsDataPath).as_posix()
    if reader_config.worksheetName:
        return f"{source} ({reader_config.worksheetName})"
    return source


def _jira_source(reader_config: JiraRequirementReaderConfig) -> str:
    return f"{reader_config.server_url} ({reader_config.auth_type})"


_READERS: tuple[tuple[type[BaseModel], str, Callable[[Any], str]], ...] = (
    (JsonlRequirementReaderConfig, "JSONL", _jsonl_source),
    (ExcelRequirementReaderConfig, "Excel", _excel_source),
    (JiraRequirementReaderConfig, "Jira", _jira_source),
)


def _reader_name_from_class_str(client_class: str) -> str:
    name = PurePath(client_class).name
    if name.endswith(".py"):
        return name[: -len(".py")]
    return name.rsplit(".", 1)[-1]


def _reader_fields(config: AppConfig) -> dict[str, str]:
    """Name the configured reader and, if it is a known one, where it reads from."""
    client_config = config.READER_CONFIG

    for config_class, reader_name, build_source in _READERS:
        if isinstance(client_config, config_class):
            return {"Reader": reader_name, "Source": build_source(client_config)}

    return {"Reader": _reader_name_from_class_str(config.READER_CLASS)}


def _config_fields(config: AppConfig) -> dict[str, str]:
    """Name the file the reader is configured in."""
    if config.READER_CONFIG_PATH:
        return {"Config": Path(config.READER_CONFIG_PATH).name}
    return {"Config": f"{Path(config.CONFIG_PATH).name} [reader_config]"}


def _runtime_fields() -> dict[str, str]:
    """Describe the interpreter and machine the service runs on."""
    system = " ".join(part for part in (platform.system(), platform.release()) if part)
    return {
        "Python": f"{platform.python_version()} ({platform.python_implementation()})",
        "Platform": f"{system or sys.platform} {platform.machine()}".strip(),
    }


def build_reader_summary(config: AppConfig) -> dict[str, str]:
    """Build the reader/source/config/runtime summary for the given app config."""
    return {
        **_reader_fields(config),
        **_config_fields(config),
        **_runtime_fields(),
    }


def log_reader_summary(config: AppConfig) -> None:
    """Log which reader is configured, where it reads from and where it is configured."""
    try:
        summary = build_reader_summary(config)
    except Exception:
        logger.debug("Could not build the reader summary", exc_info=True)
        return

    width = max(len(label) for label in summary) + 1
    for label, value in summary.items():
        logger.info("%s%s %s", INDENT, f"{label}:".ljust(width), value)
