"""Summarise the configured defect reader for the startup log."""

from collections.abc import Callable
from pathlib import Path, PurePath
from typing import Any

from pydantic import BaseModel

from testbench_requirement_service.config import AppConfig
from testbench_requirement_service.log import logger
from testbench_requirement_service.readers.excel.config import ExcelRequirementReaderConfig
from testbench_requirement_service.readers.jira.config import JiraRequirementReaderConfig
from testbench_requirement_service.readers.jsonl.config import JsonlRequirementReaderConfig


def _jsonl_source(reader_config: JsonlRequirementReaderConfig) -> str:
    return Path(reader_config.defects_path).as_posix()


def _excel_source(reader_config: ExcelRequirementReaderConfig) -> str:
    source = Path(reader_config.excel_file_path).as_posix()
    if reader_config.worksheet_name:
        return f"{source} ({reader_config.worksheet_name})"
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


def build_reader_summary(config: AppConfig) -> dict[str, str]:
    """Build the reader/source/config summary for the given app config."""
    reader_config = config.CLIENT_CONFIG

    for config_class, reader_name, build_source in _READERS:
        if isinstance(reader_config, config_class):
            summary = {
                "reader": reader_name,
                "source": build_source(reader_config),
            }
            break
    else:
        summary = {
            "reader": _reader_name_from_class_str(config.READER_CLASS),
        }

    if config.READER_CONFIG_PATH:
        summary["config"] = Path(config.READER_CONFIG_PATH).name
    else:
        summary["config"] = f"{Path(config.CONFIG_PATH).name} [reader_config]"

    return summary


def log_reader_summary(config: AppConfig) -> None:
    """Log which reader is configured, where it reads from and where it is configured."""
    try:
        summary = build_reader_summary(config)
    except Exception:
        logger.debug("Could not build the reader summary", exc_info=True)
        return

    for label, value in summary.items():
        logger.info("%s: %s", label, value)
