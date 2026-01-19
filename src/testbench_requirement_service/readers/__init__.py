from testbench_requirement_service.readers.abstract_reader import AbstractRequirementReader
from testbench_requirement_service.readers.jsonl.reader import JsonlRequirementReader
from testbench_requirement_service.utils.dependencies import (
    check_excel_dependencies,
    check_jira_dependencies,
)

__all__ = [
    "AbstractRequirementReader",
    "JsonlRequirementReader",
]

if not check_excel_dependencies(raise_on_missing=False):
    from testbench_requirement_service.readers.excel.reader import ExcelRequirementReader

    __all__ += ["ExcelRequirementReader"]

if not check_jira_dependencies(raise_on_missing=False):
    from testbench_requirement_service.readers.jira.reader import JiraRequirementReader

    __all__ += ["JiraRequirementReader"]
