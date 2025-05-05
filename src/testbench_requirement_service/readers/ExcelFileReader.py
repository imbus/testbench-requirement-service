import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import javaproperties
import pandas as pd
from sanic.exceptions import NotFound

from testbench_requirement_service.models.requirement import (
    BaselineObjectNode,
    ExtendedRequirementObject,
    RequirementKey,
    RequirementObjectNode,
    RequirementVersionObject,
    UserDefinedAttribute,
    UserDefinedAttributes,
)
from testbench_requirement_service.readers.FileReader import FileReader
from testbench_requirement_service.utils.date_format import parse_date_string


class ExcelFileReader(FileReader):
    def __init__(self, config_path: str):
        self.config = self._load_and_validate_config_from_path(Path(config_path))

    @property
    def requirements_path(self) -> Path:
        return Path(self.config["requirementsDataPath"])

    def project_exists(self, project: str) -> bool:
        return self._get_project_path(project).exists()

    def baseline_exists(self, project: str, baseline: str) -> bool:
        return self._get_baseline_path(project, baseline).exists()

    def get_projects(self) -> list[str]:
        if not self.requirements_path.exists():
            return []
        return [p.name for p in self.requirements_path.iterdir() if p.is_dir()]

    def get_baselines(self, project: str) -> list[str]:
        allowed_suffixes = self._get_allowed_suffixes_for_project(project)
        files = self._get_files_in_project_path(project)
        return list({f.stem for f in files if f.suffix in allowed_suffixes})

    def get_requirements_root_node(self, project: str, baseline: str) -> BaselineObjectNode:
        baseline_path = self._get_baseline_path(project, baseline)
        config = self._get_config_for_project(project)

        df = self._read_data_frame_from_file_path(baseline_path, config)
        df = df.sort_values(by="hierarchyID")

        requirement_nodes: dict[str, RequirementObjectNode] = {}
        requirement_tree: list[RequirementObjectNode] = []
        hierarchy_id_mapping: dict[str, str] = {}

        for row in df.to_dict("records"):
            hierarchy: str = row["hierarchyID"]
            requirement_node = self._get_requirementobjectnode_from_row_data(row, config)

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
            repositoryID=f"{project}/{baseline}",
            children=requirement_tree,
        )

    def get_user_defined_attributes(self) -> list[UserDefinedAttribute]:
        udf_definitions: list[UserDefinedAttribute] = []
        for udf_config in self._get_user_defined_attribute_configs():
            udf_definitions.append(
                UserDefinedAttribute(name=udf_config["name"], valueType=udf_config["valueType"])
            )
        return udf_definitions

    def get_all_user_defined_attributes(
        self,
        project: str,
        baseline: str,
        requirement_keys: list[RequirementKey],
        attribute_names: list[str],
    ) -> list[UserDefinedAttributes]:
        if not requirement_keys:
            return []

        baseline_path = self._get_baseline_path(project, baseline)
        config = self._get_config_for_project(project)

        df = self._read_data_frame_from_file_path(baseline_path, config)

        keys_df = pd.DataFrame([key.model_dump() for key in requirement_keys])
        filtered_df = pd.merge(df, keys_df, on=["id", "version"], how="inner")

        udf_configs = {}
        for name in attribute_names:
            udf_config = self._get_config_for_user_defined_attribute(name)
            if udf_config is None:
                continue
            udf_configs[name] = udf_config

        udfs_list: list[UserDefinedAttributes] = []

        for row in filtered_df.to_dict(orient="records"):
            key = RequirementKey(id=row["id"], version=row["version"])
            user_defined_attributes: list[UserDefinedAttribute] = []

            for name, udf_config in udf_configs.items():
                if name not in row:
                    continue

                udf_value: str = row[name]

                if udf_config["valueType"] == "STRING":
                    udf_config["stringValue"] = udf_value
                if udf_config["valueType"] == "ARRAY":
                    sep = config.get("arrayValueSeparator")
                    udf_config["stringValues"] = udf_value.split(sep) if udf_value else []
                if udf_config["valueType"] == "BOOLEAN":
                    udf_config["booleanValue"] = udf_value == udf_config["trueValue"]

                user_defined_attributes.append(UserDefinedAttribute(**udf_config))

            udfs_list.append(
                UserDefinedAttributes(key=key, userDefinedAttributes=user_defined_attributes)
            )

        return udfs_list

    def get_extended_requirement(
        self, project: str, baseline: str, key: RequirementKey
    ) -> ExtendedRequirementObject:
        baseline_path = self._get_baseline_path(project, baseline)
        config = self._get_config_for_project(project)

        df = self._read_data_frame_from_file_path(baseline_path, config)

        filtered_df = df[(df["id"] == key.id) & (df["version"] == key.version)]
        if filtered_df.empty:
            raise NotFound("Requirement not found")
        row_data = filtered_df.iloc[0].to_dict()

        return self._get_extendedrequirementobject_from_row_data(row_data, config, baseline)

    def get_requirement_versions(
        self, project: str, baseline: str, key: RequirementKey
    ) -> list[RequirementVersionObject]:
        baseline_path = self._get_baseline_path(project, baseline)
        config = self._get_config_for_project(project)

        df = self._read_data_frame_from_file_path(baseline_path, config)

        filtered_df = df[df["id"] == key.id]

        requirement_versions: list[RequirementVersionObject] = []
        for row in filtered_df.to_dict(orient="records"):
            requirement_version = self._get_requirementversionobject_from_row_data(row, config)
            requirement_versions.append(requirement_version)

        return requirement_versions

    def _load_config_from_path(self, config_path: Path) -> dict[str, str]:
        if not config_path.exists():
            raise FileNotFoundError(f"Reader config file not found: '{config_path.resolve()}'.")
        try:
            with config_path.open("r") as config_file:
                return javaproperties.load(config_file)
        except Exception as e:
            raise ImportError(f"Importing reader config from '{config_path}' failed.") from e

    def _validate_required_settings_in_config(self, config: dict[str, str]):
        required_settings = [
            "requirementsDataPath",
            "columnSeparator",
            "arrayValueSeparator",
            "baselineFileExtensions",
            "requirement.id",
            "requirement.version",
            "requirement.name",
        ]
        for setting in required_settings:
            if setting not in config:
                raise KeyError(f"Missing required setting in reader config: '{setting}'.")
            if not config[setting]:
                raise ValueError(
                    f"Invalid value for '{setting}' in reader config: Value cannot be empty."
                )

        # validate required setting "requirementsDataPath"
        requirements_path = Path(config["requirementsDataPath"])
        if not requirements_path.exists():
            raise FileNotFoundError(
                "'requirementsDataPath' defined in reader config not found: "
                f"'{requirements_path.resolve()}'."
            )

        # validate required setting "columnSeparator"
        invalid_separators = {"\r", "\n", "\r\n", '"'}
        if any(char in config["columnSeparator"] for char in invalid_separators):
            raise ValueError(
                "Invalid value for 'columnSeparator' in reader config: "
                "Must not contain line feed characters ('\\r', '\\n', '\\r\\n')"
                " or double quotes ('\"')."
            )

        # validate required setting "arrayValueSeparator"
        if any(
            char in config["arrayValueSeparator"]
            for char in invalid_separators | {config["columnSeparator"]}
        ):
            raise ValueError(
                "Invalid value for 'arrayValueSeparator' in reader config: "
                "Cannot contain line feed characters ('\\r', '\\n', '\\r\\n'), "
                "double quotes ('\"') or the defined 'columnSeparator'"
                f"({config['columnSeparator']!r})."
            )

    def _validate_optional_settings_in_config(self, config: dict[str, str]):
        # validate optional boolean settings "useExcelDirectly" and "baselinesFromSubfolders"
        optional_bool_settings = ["useExcelDirectly", "baselinesFromSubfolders"]
        for setting in optional_bool_settings:
            if setting in config and config[setting].lower() not in {"true", "false"}:
                raise ValueError(
                    f"Invalid value for '{setting}' in reader config: "
                    f"Expected 'true' or 'false' (case insensitive), but got '{config[setting]}'."
                )

        # validate optional rowIdx settings "header.rowIdx" and "data.rowIdx"
        header_row_idx = config.get("header.rowIdx")
        data_row_idx = config.get("data.rowIdx")
        if header_row_idx is not None and (not header_row_idx.isdigit() or int(header_row_idx) < 1):
            raise ValueError(
                "Invalid value for 'header.rowIdx' in reader config: "
                "Expected a row index (starting from 1) as a positive integer, "
                f"but got '{header_row_idx}'."
            )
        if data_row_idx is not None:
            if not data_row_idx.isdigit() or int(data_row_idx) < 1:
                raise ValueError(
                    "Invalid value for 'data.rowIdx' in reader config: "
                    "Expected a row index (starting from 1) as a positive integer, "
                    f"but got '{data_row_idx}'."
                )
            if header_row_idx and int(data_row_idx) <= int(header_row_idx):
                raise ValueError(
                    "Invalid value for 'data.rowIdx' in reader config: "
                    "Expected a row index (starting from 1) greater than 'header.rowIdx'"
                    f"({header_row_idx}), but got {data_row_idx}."
                )

    def _validate_column_settings_in_config(self, config: dict[str, str]):
        column_settings = [
            "requirement.hierarchyID",
            "requirement.id",
            "requirement.version",
            "requirement.name",
            "requirement.owner",
            "requirement.status",
            "requirement.priority",
            "requirement.comment",
            "requirement.date",
            "requirement.references",
            "requirement.type",
        ]
        column_idx_mapping: dict[int, str] = {}
        for setting in column_settings:
            if setting not in config:
                continue
            if not config[setting].isdigit() or int(config[setting]) < 1:
                raise ValueError(
                    f"Invalid value for '{setting}' in reader config: "
                    "Expected a column index (starting from 1) as a positive integer, "
                    f"but got '{config[setting]}'."
                )
            column_idx = int(config[setting])
            if column_idx in column_idx_mapping:
                raise ValueError(
                    f"Invalid value for '{setting}' in reader config: "
                    f"Column index {column_idx} is already assigned to column "
                    f"'{column_idx_mapping[column_idx]}'."
                )
            column_idx_mapping[column_idx] = setting

        # validate optional column settings for description
        description_settings = [
            key
            for key in config
            if key.startswith("requirement.description.")
            and key.rpartition(".")[2].isdigit()
            and int(key.rpartition(".")[2]) >= 1
        ]
        description_settings.sort()
        description_columns = []
        for setting in description_settings:
            if not config[setting].isdigit() or int(config[setting]) < 1:
                raise ValueError(
                    f"Invalid value for '{setting}' in reader config: "
                    "Expected a column index (starting from 1) as a positive integer, "
                    f"but got '{config[setting]}'."
                )
            column_idx = int(config[setting])
            if column_idx in column_idx_mapping:
                raise ValueError(
                    f"Invalid value for '{setting}' in reader config: "
                    f"Column index {column_idx} is already assigned to column "
                    f"'{column_idx_mapping[column_idx]}'."
                )
            description_columns.append(str(column_idx))
        if description_columns:
            config["requirement.description"] = ",".join(description_columns)

    def _validate_udf_settings_in_config(self, config: dict[str, str]):
        if "udf.count" not in config:
            return

        udf_count_str = config["udf.count"]
        if not udf_count_str.isdigit() or int(udf_count_str) < 0:
            raise ValueError(
                "Invalid value for 'udf.count' in reader config: "
                f"Expected an integer, but got '{udf_count_str}'."
            )
        udf_count = int(udf_count_str)
        for i in range(1, udf_count + 1):
            udf_config = {
                "name": config.get(f"udf.attr{i}.name"),
                "type": config.get(f"udf.attr{i}.type"),
                "column": config.get(f"udf.attr{i}.column"),
                "trueValue": config.get(f"udf.attr{i}.trueValue"),
            }
            required_udf_settings = ["name", "type", "column"]
            if str(udf_config["type"]).upper() == "BOOLEAN":
                required_udf_settings.append("trueValue")
            for udf_setting in required_udf_settings:
                if udf_config[udf_setting] is None:
                    raise KeyError(
                        f"Missing required setting in reader config: 'udf.attr{i}.{udf_setting}'."
                    )
                if not udf_config[udf_setting]:
                    raise ValueError(
                        f"Invalid value for 'udf.attr{i}.{udf_setting}' in reader config: "
                        "Value cannot be empty."
                    )
            if not str(udf_config["column"]).isdigit() or int(str(udf_config["column"])) < 1:
                raise ValueError(
                    f"Invalid value for 'udf.attr{i}.column' in reader config: "
                    "Expected a column index (starting from 1) as a positive integer, "
                    f"but got '{udf_config['column']}'."
                )
            # column_idx = int(udf_config["column"])
            # if column_idx in column_idx_mapping:
            #     raise ValueError(
            #         f"Invalid value for 'udf.attr{i}.column' in reader config: "
            #         f"Column index {column_idx} is already assigned to column "
            #         f"'{column_idx_mapping[column_idx]}'."
            #     )
            # column_idx_mapping[column_idx] = f"udf.attr{i}.column"
            if str(udf_config["type"]).upper() not in {"STRING", "ARRAY", "BOOLEAN"}:
                raise ValueError(
                    f"Invalid value for 'udf.attr{i}.type' in reader config: "
                    "Expected 'string', 'array' or 'boolean' (case insensitive), "
                    f"but got '{udf_config['type']}'."
                )

    def _validate_config(
        self, config: dict[str, str], is_project_config: bool = False
    ) -> dict[str, str]:
        self._validate_required_settings_in_config(config)
        self._validate_optional_settings_in_config(config)
        self._validate_column_settings_in_config(config)
        if not is_project_config:
            self._validate_udf_settings_in_config(config)
        return config

    def _load_and_validate_config_from_path(self, config_path: Path) -> dict[str, str]:
        config = self._load_config_from_path(config_path)
        return self._validate_config(config)

    def _get_project_path(self, project: str) -> Path:
        return self.requirements_path / project

    def _get_baseline_path(self, project: str, baseline: str) -> Path:
        allowed_suffixes = self._get_allowed_suffixes_for_project(project)
        files = self._get_files_in_project_path(project, f"{baseline}.*")
        file_path: Path | None = next(
            (file for file in files if file.suffix in allowed_suffixes), None
        )
        if file_path is None:
            return self._get_project_path(project) / f"{baseline}{allowed_suffixes[0]}"
        return file_path

    def _get_config_for_project(self, project: str) -> dict[str, str]:
        project_config_path = self._get_project_path(project) / f"{project}.properties"
        if project_config_path.exists():
            project_config = self._load_config_from_path(project_config_path)
            return self._validate_config(self.config.copy() | project_config, True)
        return self.config

    def _get_allowed_suffixes_for_project(self, project: str) -> list:
        config = self._get_config_for_project(project)
        if config.get("useExcelDirectly", "").lower() == "true":
            return [".xls", ".xlsx"]
        return config["baselineFileExtensions"].split(",")

    def _get_files_in_project_path(self, project: str, pattern: str = "*"):
        config = self._get_config_for_project(project)
        if config.get("baselinesFromSubfolders", "").lower() == "true":
            return self._get_project_path(project).rglob(pattern)
        return self._get_project_path(project).glob(pattern)

    def _get_column_mapping_for_config(self, config: dict[str, str]) -> dict[int, str]:
        setting_column_mapping = {
            "requirement.hierarchyID": "hierarchyID",
            "requirement.id": "id",
            "requirement.version": "version",
            "requirement.name": "name",
            "requirement.owner": "owner",
            "requirement.status": "status",
            "requirement.priority": "priority",
            "requirement.comment": "comment",
            "requirement.date": "date",
            "requirement.references": "documents",
            "requirement.type": "type",
        }

        column_mapping = {}

        for setting, column in setting_column_mapping.items():
            if not config.get(setting):
                continue
            column_idx = int(config[setting]) - 1
            column_mapping[column_idx] = column

        for udf_config in self._get_user_defined_attribute_configs():
            column_idx = int(udf_config["column"]) - 1
            column_mapping[column_idx] = udf_config["name"]

        return column_mapping

    def _read_data_frame_from_file_path(
        self, file_path: Path, config: dict[str, str]
    ) -> pd.DataFrame:
        header_row_idx = int(config.get("header.rowIdx", "1")) - 1
        data_row_idx = int(config.get("data.rowIdx", "2")) - 1
        skiprows = list(range(header_row_idx + 1, data_row_idx))

        read_params = {"header": header_row_idx, "dtype": str, "skiprows": skiprows}

        if file_path.suffix in [".xls", ".xlsx"]:
            sheet_name = config.get("worksheetName", 0)
            engine: Literal["openpyxl", "xlrd"] = (
                "openpyxl" if file_path.suffix == ".xlsx" else "xlrd"
            )
            try:
                df = pd.read_excel(file_path, sheet_name=sheet_name, engine=engine, **read_params)
            except ValueError:
                df = pd.read_excel(file_path, sheet_name=0, engine=engine, **read_params)
        elif file_path.suffix in [".csv", ".tsv", ".txt"]:
            sep = "\t" if file_path.suffix == ".tsv" else config.get("columnSeparator")
            try:
                df = pd.read_csv(file_path, sep=sep, **read_params)
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, sep=sep, encoding="windows-1252", **read_params)
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")

        df = df.fillna("")

        column_mapping = self._get_column_mapping_for_config(config)
        columns_count = len(df.columns)
        for idx, column in column_mapping.items():
            if idx >= columns_count:
                raise ValueError(
                    f"Column '{column}' at index {idx + 1} (specified in the configuration) "
                    "does not exist in the provided file. "
                    "Please verify that the index is correct in your configuration. "
                    f"The file contains {columns_count} column{'s' if columns_count != 1 else ''}."
                )

        columns = {col: column_mapping.get(idx, col) for idx, col in enumerate(df.columns)}
        df = df.rename(columns=columns)

        if config.get("requirement.description"):
            description_columns = [
                int(idx) - 1 for idx in config["requirement.description"].split(",")
            ]
            description_columns = list(dict.fromkeys(description_columns))
            description_values = df.iloc[:, description_columns].apply(
                lambda row: " ".join(x for x in row if x), axis=1
            )
            df["description"] = description_values

        return df

    def _get_extendedrequirementobject_from_row_data(
        self, row_data: dict[str, Any], config: dict[str, str], baseline: str
    ) -> ExtendedRequirementObject:
        row_data["extendedID"] = row_data["id"]
        row_data["key"] = {"id": row_data["id"], "version": row_data["version"]}
        folder_pattern = config.get("requirement.folderPattern", ".*folder.*")
        row_data["requirement"] = re.fullmatch(folder_pattern, row_data.get("type", "")) is None
        sep = config.get("arrayValueSeparator")
        row_data["documents"] = (
            str(row_data.get("documents")).split(sep) if row_data.get("documents") else []
        )
        row_data["baseline"] = baseline

        return ExtendedRequirementObject(**row_data)

    def _get_requirementobjectnode_from_row_data(
        self, row_data: dict, config: dict[str, str]
    ) -> RequirementObjectNode:
        row_data["extendedID"] = row_data["id"]
        row_data["key"] = {"id": row_data["id"], "version": row_data["version"]}
        folder_pattern = config.get("requirement.folderPattern", ".*folder.*")
        row_data["requirement"] = re.fullmatch(folder_pattern, row_data.get("type", "")) is None

        return RequirementObjectNode(**row_data)

    def _get_requirementversionobject_from_row_data(
        self, row_data: dict, config: dict[str, str]
    ) -> RequirementVersionObject:
        date_string = row_data.get("date", "")
        date_format = config.get("dateFormat", "")
        date = parse_date_string(date_string, date_format)

        return RequirementVersionObject(
            name=row_data["version"],
            date=date,
            author=row_data.get("owner", ""),
            comment=row_data.get("comment", ""),
        )  # TODO: which data should be filled in ?

    def _get_user_defined_attribute_configs(self) -> list[dict[str, Any]]:
        udf_configs: list[dict[str, Any]] = []
        udf_count = int(self.config.get("udf.count", "0"))
        for i in range(1, udf_count + 1):
            udf_config = {
                "name": self.config.get(f"udf.attr{i}.name"),
                "valueType": self.config.get(f"udf.attr{i}.type", "").upper(),
                "column": self.config.get(f"udf.attr{i}.column"),
                "trueValue": self.config.get(f"udf.attr{i}.trueValue"),
            }
            udf_configs.append(udf_config)
        return udf_configs

    def _get_config_for_user_defined_attribute(self, name: str) -> dict[str, Any] | None:
        return next(
            (
                config
                for config in self._get_user_defined_attribute_configs()
                if config["name"] == name
            ),
            None,
        )
