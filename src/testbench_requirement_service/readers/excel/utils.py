import re
from pathlib import Path
from typing import Any, Literal

from testbench_requirement_service.models.requirement import (
    ExtendedRequirementObject,
    RequirementObjectNode,
    RequirementVersionObject,
)
from testbench_requirement_service.utils.date_format import parse_date_string

try:  # noqa: SIM105
    import pandas as pd
except ImportError:
    pass


def get_column_mapping_for_config(config: dict[str, str]) -> dict[int, str]:
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

    for udf_config in build_user_defined_attribute_configs(config):
        column_idx = int(udf_config["column"]) - 1
        column_mapping[column_idx] = udf_config["name"]

    return column_mapping


def read_data_frame_from_file_path(file_path: Path, config: dict[str, str]) -> pd.DataFrame:
    header_row_idx = int(config.get("header.rowIdx", "1")) - 1
    data_row_idx = int(config.get("data.rowIdx", "2")) - 1
    skiprows = list(range(header_row_idx + 1, data_row_idx))

    read_params: dict[str, Any] = {"header": header_row_idx, "dtype": str, "skiprows": skiprows}

    if file_path.suffix in [".xls", ".xlsx"]:
        sheet_name = config.get("worksheetName", 0)
        engine: Literal["openpyxl", "xlrd"] = "openpyxl" if file_path.suffix == ".xlsx" else "xlrd"
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

    column_mapping = get_column_mapping_for_config(config)
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
        description_columns = [int(idx) - 1 for idx in config["requirement.description"].split(",")]
        description_columns = list(dict.fromkeys(description_columns))
        description_values = df.iloc[:, description_columns].apply(
            lambda row: " ".join(x for x in row if x), axis=1
        )
        df["description"] = description_values

    return df


def build_extendedrequirementobject_from_row_data(
    row_data: dict[str, Any], config: dict[str, str], baseline: str
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


def build_requirementobjectnode_from_row_data(
    row_data: dict, config: dict[str, str]
) -> RequirementObjectNode:
    row_data["extendedID"] = row_data["id"]
    row_data["key"] = {"id": row_data["id"], "version": row_data["version"]}
    folder_pattern = config.get("requirement.folderPattern", ".*folder.*")
    row_data["requirement"] = re.fullmatch(folder_pattern, row_data.get("type", "")) is None

    return RequirementObjectNode(**row_data)


def build_requirementversionobject_from_row_data(
    row_data: dict, config: dict[str, str]
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


def build_user_defined_attribute_configs(config: dict[str, str]) -> list[dict[str, Any]]:
    udf_configs: list[dict[str, Any]] = []
    udf_count = int(config.get("udf.count", "0"))
    for i in range(1, udf_count + 1):
        udf_config = {
            "name": config.get(f"udf.attr{i}.name"),
            "valueType": config.get(f"udf.attr{i}.type", "").upper(),
            "column": config.get(f"udf.attr{i}.column"),
            "trueValue": config.get(f"udf.attr{i}.trueValue"),
        }
        udf_configs.append(udf_config)
    return udf_configs


def get_config_for_user_defined_attribute(
    name: str, config: dict[str, str]
) -> dict[str, Any] | None:
    return next(
        (cfg for cfg in build_user_defined_attribute_configs(config) if cfg["name"] == name),
        None,
    )
