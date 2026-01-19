import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sanic.exceptions import NotFound

from testbench_requirement_service.models.requirement import (
    BaselineObject,
    BaselineObjectNode,
    ExtendedRequirementObject,
    RequirementKey,
    RequirementObjectNode,
    RequirementVersionObject,
    UserDefinedAttribute,
    UserDefinedAttributeResponse,
)
from testbench_requirement_service.readers.abstract_reader import AbstractRequirementReader
from testbench_requirement_service.readers.jsonl.config import JsonlRequirementReaderConfig
from testbench_requirement_service.readers.jsonl.models import FileRequirementObjectNode
from testbench_requirement_service.readers.jsonl.utils import (
    build_extendedrequirementobject_from_file_object,
    build_requirementobject_from_file_object,
)
from testbench_requirement_service.readers.utils import load_reader_config_from_path


class JsonlRequirementReader(AbstractRequirementReader):
    def __init__(self, config_path: str):
        self.config = load_reader_config_from_path(
            config_path=Path(config_path),
            config_class=JsonlRequirementReaderConfig,
            config_prefix="jsonl",
        )

    def project_exists(self, project: str) -> bool:
        return self._get_project_path(project).exists()

    def baseline_exists(self, project: str, baseline: str) -> bool:
        return self._get_baseline_path(project, baseline).exists()

    def get_projects(self) -> list[str]:
        if not self.config.requirements_path.exists():
            return []
        return [p.name for p in self.config.requirements_path.iterdir() if p.is_dir()]

    def get_baselines(self, project: str) -> list[BaselineObject]:
        return [
            BaselineObject(
                name=f.stem,
                date=datetime.fromtimestamp(f.stat().st_ctime).astimezone(),
                type="UNLOCKED",
            )
            for f in self._get_project_path(project).iterdir()
            if f.suffix == ".jsonl"
        ]

    def get_requirements_root_node(self, project: str, baseline: str) -> BaselineObjectNode:
        baseline_path = self._get_baseline_path(project, baseline)
        requirement_nodes: dict[str, RequirementObjectNode] = {}
        requirement_tree: dict[str, RequirementObjectNode] = {}
        with baseline_path.open("r") as f:
            for line in f:
                file_node = FileRequirementObjectNode(**json.loads(line))
                requirement_node = build_requirementobject_from_file_object(file_node)
                if file_node.key.id in requirement_nodes:
                    continue
                requirement_nodes[file_node.key.id] = requirement_node
                if file_node.parent:
                    if file_node.parent not in requirement_nodes:
                        raise ValueError(
                            "Parent relation not in order!\n"
                            f"  key: {file_node.key.model_dump()}"
                            f"  parent: {file_node.parent}"
                        )
                    parent = requirement_nodes[file_node.parent]
                    if parent.children is None:
                        parent.children = [requirement_node]
                    else:
                        parent.children.append(requirement_node)
                else:
                    requirement_tree[file_node.key.id] = requirement_node
        return BaselineObjectNode(
            name=baseline,
            date=datetime.now(timezone.utc),
            type="CURRENT",
            children=list(requirement_tree.values()),
        )

    def get_user_defined_attributes(self) -> list[UserDefinedAttribute]:
        filepath = self.config.requirements_path / "UserDefinedAttributes.json"
        if not filepath.exists():
            return []
        with filepath.open("r") as f:
            udf_definitions = json.load(f)
            if not isinstance(udf_definitions, list):
                raise ValueError("UserDefinedAttributes.json must contain a list of definitions.")
            for udf in udf_definitions:
                if not isinstance(udf, dict):
                    raise ValueError(
                        "UserDefinedAttributes.json must contain a list of dictonaries."
                    )
                if "name" not in udf or "valueType" not in udf:
                    raise ValueError(
                        "UserDefinedAttributes.json must contain a list of definitions "
                        "with 'name' and 'valueType' keys."
                    )
            return [
                UserDefinedAttribute(name=udf["name"], valueType=udf["valueType"])
                for udf in udf_definitions
            ]

    def get_all_user_defined_attributes(
        self,
        project: str,
        baseline: str,
        requirement_keys: list[RequirementKey],
        attribute_names: list[str],
    ) -> list[UserDefinedAttributeResponse]:
        if not requirement_keys:
            return []

        baseline_path = self._get_baseline_path(project, baseline)
        keys: dict[str, dict[str, None]] = defaultdict(dict)
        for key in requirement_keys:
            keys[key.id][key.version] = None
        file_nodes: list[UserDefinedAttributeResponse] = []
        with baseline_path.open("r") as f:
            for line in f:
                file_node = FileRequirementObjectNode(**json.loads(line))
                if (
                    file_node.key.id in keys
                    and file_node.key.version.name in keys[file_node.key.id]
                ):
                    file_nodes.append(
                        UserDefinedAttributeResponse(
                            key=RequirementKey(
                                id=file_node.key.id, version=file_node.key.version.name
                            ),
                            userDefinedAttributes=list(
                                filter(
                                    lambda udf: udf.name in attribute_names,
                                    file_node.userDefinedAttributes,
                                )
                            ),
                        )
                    )
        return file_nodes

    def get_extended_requirement(
        self, project: str, baseline: str, key: RequirementKey
    ) -> ExtendedRequirementObject:
        baseline_path = self._get_baseline_path(project, baseline)
        with baseline_path.open("r") as f:
            for line in f:
                file_node = FileRequirementObjectNode(**json.loads(line))
                if file_node.key.id == key.id and file_node.key.version.name == key.version:
                    return build_extendedrequirementobject_from_file_object(file_node, baseline)
        raise NotFound("Requirement not found")

    def get_requirement_versions(
        self, project: str, baseline: str, key: RequirementKey
    ) -> list[RequirementVersionObject]:
        baseline_path = self._get_baseline_path(project, baseline)
        versions = []
        with baseline_path.open("r") as f:
            for line in f:
                file_node = FileRequirementObjectNode(**json.loads(line))
                if file_node.key.id == key.id:
                    versions.append(RequirementVersionObject(**file_node.key.version.model_dump()))
        return versions

    def _get_project_path(self, project: str) -> Path:
        return self.config.requirements_path / project

    def _get_baseline_path(self, project: str, baseline: str) -> Path:
        return self._get_project_path(project) / f"{baseline}.jsonl"
