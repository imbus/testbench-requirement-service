"""Tests for tolerating baseline files that do not match the configured column structure.

Requests that scan *all* baseline files of a project (requirement versions, the
extended-requirement fallback search) must ignore files they cannot interpret
instead of failing the whole request.
"""

from pathlib import Path

import openpyxl
import pytest
from sanic.exceptions import NotFound

from testbench_requirement_service.models.requirement import RequirementKey
from testbench_requirement_service.readers.excel.config import ExcelRequirementReaderConfig
from testbench_requirement_service.readers.excel.reader import ExcelRequirementReader

GOOD_CONTENT = "id;version;name\nR1;1;First\n"
FOREIGN_CONTENT = "totally;different\na;b\n"


def write_xlsx(file_path: Path, rows: list[list[str]]) -> None:
    workbook = openpyxl.Workbook()
    for row in rows:
        workbook.active.append(row)
    workbook.save(file_path)
    workbook.close()


def make_reader(data_path: Path, *, use_excel_directly: bool = False) -> ExcelRequirementReader:
    config = ExcelRequirementReaderConfig.model_validate(
        {
            "requirementsDataPath": str(data_path),
            "columnSeparator": ";",
            "arrayValueSeparator": ",",
            "baselineFileExtensions": ".csv",
            "useExcelDirectly": use_excel_directly,
            "requirement.id": 1,
            "requirement.version": 2,
            "requirement.name": 3,
            "bufferMaxAgeMinutes": 0,
            "bufferCleanupIntervalMinutes": 0,
        }
    )
    return ExcelRequirementReader(config)


@pytest.fixture
def project_path(tmp_path: Path) -> Path:
    project = tmp_path / "P1"
    project.mkdir()
    (project / "good.csv").write_text(GOOD_CONTENT, encoding="utf-8")
    return project


class TestGetRequirementVersions:
    def test_ignores_file_with_unexpected_column_structure(self, tmp_path, project_path, caplog):
        (project_path / "foreign.csv").write_text(FOREIGN_CONTENT, encoding="utf-8")
        reader = make_reader(tmp_path)

        versions = reader.get_requirement_versions(
            "P1", "good", RequirementKey(id="R1", version="1")
        )

        assert [version.name for version in versions] == ["1"]
        assert "foreign.csv" in caplog.text

    def test_returns_versions_from_all_readable_files(self, tmp_path, project_path):
        (project_path / "foreign.csv").write_text(FOREIGN_CONTENT, encoding="utf-8")
        (project_path / "older.csv").write_text("id;version;name\nR1;0;First\n", encoding="utf-8")
        reader = make_reader(tmp_path)

        versions = reader.get_requirement_versions(
            "P1", "good", RequirementKey(id="R1", version="1")
        )

        assert sorted(version.name for version in versions) == ["0", "1"]


class TestGetExtendedRequirement:
    def test_ignores_file_with_unexpected_column_structure_during_fallback(
        self, tmp_path, project_path, caplog
    ):
        (project_path / "foreign.csv").write_text(FOREIGN_CONTENT, encoding="utf-8")
        reader = make_reader(tmp_path)

        requirement = reader.get_extended_requirement(
            "P1", "good", RequirementKey(id="R1", version="1")
        )

        assert requirement.extendedID == "R1"

    def test_still_reports_not_found_when_no_file_contains_the_requirement(
        self, tmp_path, project_path
    ):
        (project_path / "foreign.csv").write_text(FOREIGN_CONTENT, encoding="utf-8")
        reader = make_reader(tmp_path)

        with pytest.raises(NotFound):
            reader.get_extended_requirement("P1", "good", RequirementKey(id="NOPE", version="1"))


class TestExcelFiles:
    def test_ignores_xlsx_file_with_unexpected_column_structure(self, tmp_path, caplog):
        project = tmp_path / "P1"
        project.mkdir()
        write_xlsx(project / "good.xlsx", [["id", "version", "name"], ["R1", "1", "First"]])
        write_xlsx(project / "foreign.xlsx", [["totally", "different"], ["a", "b"]])
        reader = make_reader(tmp_path, use_excel_directly=True)

        versions = reader.get_requirement_versions(
            "P1", "good", RequirementKey(id="R1", version="1")
        )

        assert [version.name for version in versions] == ["1"]
        assert "foreign.xlsx" in caplog.text

    def test_ignores_corrupt_xlsx_file(self, tmp_path, caplog):
        project = tmp_path / "P1"
        project.mkdir()
        write_xlsx(project / "good.xlsx", [["id", "version", "name"], ["R1", "1", "First"]])
        (project / "broken.xlsx").write_bytes(b"not a workbook at all")
        reader = make_reader(tmp_path, use_excel_directly=True)

        versions = reader.get_requirement_versions(
            "P1", "good", RequirementKey(id="R1", version="1")
        )

        assert [version.name for version in versions] == ["1"]
        assert "broken.xlsx" in caplog.text
