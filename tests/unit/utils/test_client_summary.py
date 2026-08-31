import logging
from pathlib import Path

import pytest

from testbench_requirement_service.config import AppConfig
from testbench_requirement_service.readers.excel.config import ExcelRequirementReaderConfig
from testbench_requirement_service.readers.jira.config import JiraRequirementReaderConfig
from testbench_requirement_service.readers.jsonl.config import JsonlRequirementReaderConfig
from testbench_requirement_service.utils.client_summary import (
    build_reader_summary,
    log_reader_summary,
)


def make_app_config(reader_config: object, reader_class: str = "") -> AppConfig:
    """Build an AppConfig carrying only the attributes the summary reads."""
    config = AppConfig.__new__(AppConfig)
    config.READER_CLASS = reader_class
    config.READER_CONFIG = reader_config
    config.READER_CONFIG_PATH = Path("reader_config.toml")
    config.CONFIG_PATH = Path("config.toml")
    return config


def make_excel_config(
    data_path: Path, worksheet_name: str | None = None
) -> ExcelRequirementReaderConfig:
    return ExcelRequirementReaderConfig(
        requirementsDataPath=data_path,
        columnSeparator=";",
        arrayValueSeparator=",",
        baselineFileExtensions=[".csv"],
        worksheetName=worksheet_name,
        **{"requirement.id": 1, "requirement.version": 2, "requirement.name": 3},
    )


class TestBuildReaderSummary:
    def test_jsonl_source_is_the_requirements_path(self, tmp_path: Path) -> None:
        reader_config = JsonlRequirementReaderConfig(requirements_path=tmp_path)

        summary = build_reader_summary(make_app_config(reader_config))

        assert summary["Reader"] == "JSONL"
        assert summary["Source"] == tmp_path.as_posix()

    def test_excel_source_is_the_requirements_data_path(self, tmp_path: Path) -> None:
        reader_config = make_excel_config(tmp_path)

        summary = build_reader_summary(make_app_config(reader_config))

        assert summary["Reader"] == "Excel"
        assert summary["Source"] == tmp_path.as_posix()

    def test_excel_source_appends_the_worksheet_name(self, tmp_path: Path) -> None:
        reader_config = make_excel_config(tmp_path, worksheet_name="Tabelle1")

        summary = build_reader_summary(make_app_config(reader_config))

        assert summary["Source"] == f"{tmp_path.as_posix()} (Tabelle1)"

    def test_jira_source_is_the_server_url_and_auth_type(self) -> None:
        reader_config = JiraRequirementReaderConfig(
            server_url="https://jira.example.com", auth_type="token", token="secret"
        )

        summary = build_reader_summary(make_app_config(reader_config))

        assert summary["Reader"] == "Jira"
        assert summary["Source"] == "https://jira.example.com (token)"

    def test_unknown_reader_falls_back_to_the_class_name(self) -> None:
        config = make_app_config(
            object(), reader_class="testbench_requirement_service.readers.SqlRequirementReader"
        )

        summary = build_reader_summary(config)

        assert summary["Reader"] == "SqlRequirementReader"
        assert "Source" not in summary


class TestLogReaderSummary:
    def test_summary_is_logged_at_info_level(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        config = make_app_config(make_excel_config(tmp_path, worksheet_name="Tabelle1"))

        with caplog.at_level(logging.INFO, logger="testbench_requirement_service"):
            log_reader_summary(config)

        messages = [record.getMessage() for record in caplog.records]
        assert any("Reader:" in message and "Excel" in message for message in messages)
        assert any(tmp_path.as_posix() in message for message in messages)
        assert any("Config:" in message for message in messages)
