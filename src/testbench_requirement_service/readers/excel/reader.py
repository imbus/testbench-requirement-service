from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:  # noqa: SIM105
    import pandas as pd  # type: ignore
except ImportError:
    pass
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
from testbench_requirement_service.readers.excel.config import (
    ExcelRequirementReaderConfig,
    ExcelRequirementReaderProjectConfig,
    UserDefinedAttributeConfig,
)
from testbench_requirement_service.readers.excel.utils import (
    build_extendedrequirementobject_from_row_data,
    build_requirementobjectnode_from_row_data,
    build_requirementversionobject_from_row_data,
    get_config_for_user_defined_attribute,
    read_data_frame_from_file_path,
)
from testbench_requirement_service.readers.utils import load_reader_config_from_path


class ExcelRequirementReader(AbstractRequirementReader):
    def __init__(self, config_path: str):
        self.config = load_reader_config_from_path(Path(config_path), ExcelRequirementReaderConfig)

    def project_exists(self, project: str) -> bool:
        return self._get_project_path(project).exists()

    def baseline_exists(self, project: str, baseline: str) -> bool:
        return self._get_baseline_path(project, baseline).exists()

    def get_projects(self) -> list[str]:
        if not self.config.requirementsDataPath.exists():
            return []
        return [p.name for p in self.config.requirementsDataPath.iterdir() if p.is_dir()]

    def get_baselines(self, project: str) -> list[BaselineObject]:
        allowed_suffixes = self._get_allowed_suffixes_for_project(project)
        files = self._get_files_in_project_path(project)
        baselines = []
        for file in files:
            if file.suffix not in allowed_suffixes:
                continue
            stat_result = file.stat()
            creation_timestamp = getattr(stat_result, "st_birthtime", stat_result.st_ctime)
            baseline = BaselineObject(
                name=file.stem,
                date=datetime.fromtimestamp(creation_timestamp, timezone.utc),
                type="UNLOCKED",
            )
            baselines.append(baseline)
        return baselines

    def get_requirements_root_node(self, project: str, baseline: str) -> BaselineObjectNode:
        baseline_path = self._get_baseline_path(project, baseline)
        config = self._get_config_for_project(project)

        df = read_data_frame_from_file_path(baseline_path, config)
        df = df.sort_values(by="hierarchyID")

        requirement_nodes: dict[str, RequirementObjectNode] = {}
        requirement_tree: list[RequirementObjectNode] = []
        hierarchy_id_mapping: dict[str, str] = {}

        for row in df.to_dict("records"):
            hierarchy: str = row["hierarchyID"]
            requirement_node = build_requirementobjectnode_from_row_data(row, config)

            requirement_id = requirement_node.key.id
            hierarchy_id_mapping[hierarchy] = requirement_id

            parent_hierarchy = hierarchy.rpartition(".")[0]
            parent_id = hierarchy_id_mapping.get(parent_hierarchy)
            if parent_id:
                parent = requirement_nodes[parent_id]
                parent.children = parent.children or []
                parent.children.append(requirement_node)
            else:
                requirement_tree.append(requirement_node)

            requirement_nodes[requirement_id] = requirement_node

        return BaselineObjectNode(
            name=baseline,
            date=datetime.now(timezone.utc),
            type="CURRENT",
            children=requirement_tree,
        )

    def get_user_defined_attributes(self) -> list[UserDefinedAttribute]:
        udf_definitions: list[UserDefinedAttribute] = []
        for udf_config in self.config.udf_configs:
            udf_definitions.append(
                UserDefinedAttribute(name=udf_config.name, valueType=udf_config.type)
            )
        return udf_definitions

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
        config = self._get_config_for_project(project)

        df = read_data_frame_from_file_path(baseline_path, config)

        keys_df = pd.DataFrame([key.model_dump() for key in requirement_keys])
        filtered_df = pd.merge(df, keys_df, on=["id", "version"], how="inner")

        udf_configs: dict[str, UserDefinedAttributeConfig] = {}
        for name in attribute_names:
            udf_config = get_config_for_user_defined_attribute(name, config)
            if udf_config is None:
                continue
            udf_configs[name] = udf_config

        udfs_list: list[UserDefinedAttributeResponse] = []

        for row in filtered_df.to_dict(orient="records"):
            key = RequirementKey(id=row["id"], version=row["version"])
            user_defined_attributes: list[UserDefinedAttribute] = []

            for name, udf_config in udf_configs.items():
                if name not in row:
                    continue

                udf: dict[str, Any] = {"name": name, "valueType": udf_config.type}

                udf_value: str = row[name]

                if udf["valueType"] == "STRING":
                    udf["stringValue"] = udf_value
                if udf["valueType"] == "ARRAY":
                    sep = config.arrayValueSeparator
                    udf["stringValues"] = udf_value.split(sep) if udf_value else []
                if udf["valueType"] == "BOOLEAN":
                    udf["booleanValue"] = udf_value == udf_config.trueValue

                user_defined_attributes.append(UserDefinedAttribute(**udf))

            udfs_list.append(
                UserDefinedAttributeResponse(key=key, userDefinedAttributes=user_defined_attributes)
            )

        return udfs_list

    def get_extended_requirement(
        self, project: str, baseline: str, key: RequirementKey
    ) -> ExtendedRequirementObject:
        baseline_path = self._get_baseline_path(project, baseline)
        config = self._get_config_for_project(project)

        df = read_data_frame_from_file_path(baseline_path, config)

        filtered_df = df[(df["id"] == key.id) & (df["version"] == key.version)]
        if filtered_df.empty:
            raise NotFound("Requirement not found")
        row_data = filtered_df.iloc[0].to_dict()

        return build_extendedrequirementobject_from_row_data(row_data, config, baseline)

    def get_requirement_versions(
        self, project: str, baseline: str, key: RequirementKey
    ) -> list[RequirementVersionObject]:
        baseline_path = self._get_baseline_path(project, baseline)
        config = self._get_config_for_project(project)

        df = read_data_frame_from_file_path(baseline_path, config)

        filtered_df = df[df["id"] == key.id]

        requirement_versions: list[RequirementVersionObject] = []
        for row in filtered_df.to_dict(orient="records"):
            requirement_version = build_requirementversionobject_from_row_data(row, config)
            requirement_versions.append(requirement_version)

        return requirement_versions

    def _get_project_path(self, project: str) -> Path:
        return self.config.requirementsDataPath / project

    def _get_baseline_path(self, project: str, baseline: str) -> Path:
        allowed_suffixes = self._get_allowed_suffixes_for_project(project)
        files = self._get_files_in_project_path(project, f"{baseline}.*")
        file_path: Path | None = next(
            (file for file in files if file.suffix in allowed_suffixes), None
        )
        if file_path is None:
            return self._get_project_path(project) / f"{baseline}{allowed_suffixes[0]}"
        return file_path

    def _get_config_for_project(self, project: str) -> ExcelRequirementReaderConfig:
        project_config_path = self._get_project_path(project) / f"{project}.properties"
        if project_config_path.exists():
            project_config = load_reader_config_from_path(
                project_config_path, ExcelRequirementReaderProjectConfig
            )
            return self.config.model_copy(update=project_config.model_dump(exclude_unset=True))
        return self.config

    def _get_allowed_suffixes_for_project(self, project: str) -> list:
        config = self._get_config_for_project(project)
        if config.useExcelDirectly:
            return [".xls", ".xlsx"]
        return config.baselineFileExtensions

    def _get_files_in_project_path(self, project: str, pattern: str = "*"):
        config = self._get_config_for_project(project)
        if config.baselinesFromSubfolders:
            return self._get_project_path(project).rglob(pattern)
        return self._get_project_path(project).glob(pattern)
