import re
from pathlib import Path
from typing import Any, Literal

from testbench_requirement_service.models.requirement import (
    ExtendedRequirementObject,
    RequirementObjectNode,
    RequirementVersionObject,
)
from testbench_requirement_service.readers.excel.config import (
    ExcelRequirementReaderConfig,
    UserDefinedAttributeConfig,
)
from testbench_requirement_service.utils.date_format import parse_date_string

try:  # noqa: SIM105
    import pandas as pd
except ImportError:
    pass


def get_column_mapping_for_config(config: ExcelRequirementReaderConfig) -> dict[int, str]:
    setting_column_mapping = {
        setting: setting.split("_", 1)[1] for setting in config.column_settings
    }

    column_mapping: dict[int, str] = {}

    for setting, column in setting_column_mapping.items():
        setting_value = getattr(config, setting, None)
        if not setting_value or not isinstance(setting_value, int):
            continue
        column_idx = setting_value - 1
        column_mapping[column_idx] = column

    for udf_config in config.udf_configs:
        column_idx = udf_config.column - 1
        column_mapping[column_idx] = udf_config.name

    return column_mapping


def read_data_frame_from_file_path(
    file_path: Path, config: ExcelRequirementReaderConfig
) -> pd.DataFrame:
    header_row_idx = (config.header_rowIdx or 1) - 1
    data_row_idx = (config.data_rowIdx or 2) - 1
    skiprows = list(range(header_row_idx + 1, data_row_idx))

    read_params: dict[str, Any] = {"header": header_row_idx, "dtype": str, "skiprows": skiprows}

    if file_path.suffix in [".xls", ".xlsx"]:
        sheet_name = config.worksheetName or 0
        engine: Literal["openpyxl", "xlrd"] = "openpyxl" if file_path.suffix == ".xlsx" else "xlrd"
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name, engine=engine, **read_params)
        except ValueError:
            df = pd.read_excel(file_path, sheet_name=0, engine=engine, **read_params)
    elif file_path.suffix in [".csv", ".tsv", ".txt"]:
        sep = "\t" if file_path.suffix == ".tsv" else config.columnSeparator
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

    if config.requirement_description:
        description_columns = [idx - 1 for idx in config.requirement_description]
        description_values = df.iloc[:, description_columns].apply(
            lambda row: " ".join(x for x in row if x), axis=1
        )
        df["description"] = description_values

    return df


def build_extendedrequirementobject_from_row_data(
    row_data: dict, config: ExcelRequirementReaderConfig, baseline: str
) -> ExtendedRequirementObject:
    row_data["extendedID"] = row_data["id"]
    row_data["key"] = {"id": row_data["id"], "version": row_data["version"]}
    folder_pattern = config.requirement_folderPattern
    row_data["requirement"] = re.fullmatch(folder_pattern, row_data.get("type", "")) is None
    sep = config.arrayValueSeparator
    row_data["documents"] = (
        str(row_data.get("documents")).split(sep) if row_data.get("documents") else []
    )
    row_data["baseline"] = baseline

    return ExtendedRequirementObject(**row_data)


def build_requirementobjectnode_from_row_data(
    row_data: dict, config: ExcelRequirementReaderConfig
) -> RequirementObjectNode:
    row_data["extendedID"] = row_data["id"]
    row_data["key"] = {"id": row_data["id"], "version": row_data["version"]}
    folder_pattern = config.requirement_folderPattern
    row_data["requirement"] = re.fullmatch(folder_pattern, row_data.get("type", "")) is None

    return RequirementObjectNode(**row_data)


def build_requirementversionobject_from_row_data(
    row_data: dict, config: ExcelRequirementReaderConfig
) -> RequirementVersionObject:
    date_string = row_data.get("date", "")
    date_format = config.dateFormat or "yyyy-MM-dd HH:mm:ss"
    date = parse_date_string(date_string, date_format)

    return RequirementVersionObject(
        name=row_data["version"],
        date=date,
        author=row_data.get("owner", ""),
        comment=row_data.get("comment", ""),
    )  # TODO: which data should be filled in ?


def get_config_for_user_defined_attribute(
    name: str, config: ExcelRequirementReaderConfig
) -> UserDefinedAttributeConfig | None:
    return next(
        (udf_cfg for udf_cfg in config.udf_configs if udf_cfg.name == name),
        None,
    )
