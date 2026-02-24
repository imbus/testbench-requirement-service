import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from testbench_requirement_service.log import logger
from testbench_requirement_service.models.requirement import (
    ExtendedRequirementObject,
    RequirementKey,
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


def get_column_mapping_for_config(config: ExcelRequirementReaderConfig) -> dict[int, list[str]]:
    """Return a mapping from 0-based column index to a list of field names.

    Multiple fields may share the same column index (e.g. 'id' and 'name' both
    reading from column 4).  The first entry in each list is used as the primary
    rename target; additional entries become copies of that column so that all
    downstream code can look up any field name by its logical key.
    """
    setting_column_mapping = {
        setting: setting.split("_", 1)[1] for setting in config.column_settings
    }

    column_mapping: dict[int, list[str]] = {}

    for setting, column in setting_column_mapping.items():
        setting_value = getattr(config, setting, None)
        if not setting_value or not isinstance(setting_value, int):
            continue
        column_idx = setting_value - 1
        column_mapping.setdefault(column_idx, []).append(column)

    for udf_config in config.udf_configs:
        column_idx = udf_config.column - 1
        column_mapping.setdefault(column_idx, []).append(udf_config.name)

    return column_mapping


def _load_dataframe(file_path: Path, config: ExcelRequirementReaderConfig) -> pd.DataFrame:
    """Read raw file data into a DataFrame with all values coerced to strings."""
    header_row_idx = (config.header_rowIdx or 1) - 1
    data_row_idx = (config.data_rowIdx or 2) - 1
    read_params: dict[str, Any] = {
        "header": header_row_idx,
        "dtype": str,
        "skiprows": list(range(header_row_idx + 1, data_row_idx)),
    }

    if file_path.suffix in (".xls", ".xlsx"):
        sheet_name = config.worksheetName or 0
        engine: Literal["openpyxl", "xlrd"] = "openpyxl" if file_path.suffix == ".xlsx" else "xlrd"
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name, engine=engine, **read_params)
        except ValueError:
            df = pd.read_excel(file_path, sheet_name=0, engine=engine, **read_params)
    elif file_path.suffix in (".csv", ".tsv", ".txt"):
        sep = "\t" if file_path.suffix == ".tsv" else config.columnSeparator
        try:
            df = pd.read_csv(file_path, sep=sep, **read_params)
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, sep=sep, encoding="windows-1252", **read_params)
    else:
        raise ValueError(f"Unsupported file format: {file_path.suffix}")

    return df.fillna("")  # type: ignore[no-any-return]


def _apply_column_mapping(
    df: pd.DataFrame,
    column_mapping: dict[int, list[str]],
    config: ExcelRequirementReaderConfig,
) -> pd.DataFrame:
    """Rename physical columns to their logical field names.

    Validates that every configured index exists in the DataFrame.  When multiple
    field names share the same column index, the column is renamed to the first
    name and copied under each additional name so all fields are addressable.

    If ``config.requirement_description`` is set, an additional ``description``
    column is created by joining the values of the listed (1-based) columns.
    """
    columns_count = len(df.columns)

    def _assert_column_exists(idx: int, label: str) -> None:
        if idx >= columns_count:
            raise ValueError(
                f"Column '{label}' (index {idx + 1}) not found in the file. "
                f"The file has {columns_count} column{'s' if columns_count != 1 else ''}, "
                "but the configuration specifies a higher index. "
                "Check your configuration and make sure the index is within range."
            )

    for idx, names in column_mapping.items():
        _assert_column_exists(idx, names[0])
        if len(names) > 1:
            logger.warning(
                "Column index %d is mapped to multiple fields (%s); "
                "the same value will be applied to all of them.",
                idx + 1,
                ", ".join(f"'{n}'" for n in names),
            )

    rename_map = {
        col: column_mapping[idx][0] for idx, col in enumerate(df.columns) if idx in column_mapping
    }
    df = df.rename(columns=rename_map)

    for names in column_mapping.values():
        for alias in names[1:]:
            df[alias] = df[names[0]]

    if config.requirement_description:
        description_columns = [idx - 1 for idx in config.requirement_description]
        for idx in description_columns:
            _assert_column_exists(idx, "description")
        df["description"] = df.iloc[:, description_columns].apply(
            lambda row: " ".join(x for x in row if x), axis=1
        )

    return df


def read_data_frame_from_file_path(
    file_path: Path, config: ExcelRequirementReaderConfig
) -> pd.DataFrame:
    logger.debug(
        "Reading file: %s (%.2f MiB)",
        file_path,
        file_path.stat().st_size / (1024**2),
    )
    start = time.monotonic()

    df = _load_dataframe(file_path, config)
    column_mapping = get_column_mapping_for_config(config)
    df = _apply_column_mapping(df, column_mapping, config)

    bytes_used = df.memory_usage(index=True, deep=True).sum()
    logger.debug(
        "Read dataframe in %.3fs (%.2f MiB)",
        time.monotonic() - start,
        bytes_used / (1024**2),
    )
    return df  # type: ignore[no-any-return]


def build_extendedrequirementobject_from_row_data(
    row_data: dict, config: ExcelRequirementReaderConfig, baseline: str
) -> ExtendedRequirementObject:
    requirement_object = build_requirementobjectnode_from_row_data(row_data, config)
    sep = config.arrayValueSeparator
    documents = str(row_data.get("references")).split(sep) if row_data.get("references") else []

    return ExtendedRequirementObject(
        **requirement_object.model_dump(exclude={"children"}),
        description=row_data.get("description", ""),
        documents=documents,
        baseline=baseline,
    )


def build_requirementobjectnode_from_row_data(
    row_data: dict, config: ExcelRequirementReaderConfig
) -> RequirementObjectNode:
    extended_id = row_data["id"]
    key = RequirementKey(id=row_data["id"], version=row_data["version"])
    folder_pattern = config.requirement_folderPattern
    is_requirement = re.fullmatch(folder_pattern, row_data.get("type", "")) is None

    return RequirementObjectNode(
        name=row_data["name"],
        extendedID=extended_id,
        key=key,
        owner=row_data.get("owner", ""),
        status=row_data.get("status", ""),
        priority=row_data.get("priority", ""),
        requirement=is_requirement,
        children=row_data.get("children"),
    )


def build_requirementversionobject_from_row_data(
    row_data: dict, config: ExcelRequirementReaderConfig
) -> RequirementVersionObject:
    date_string = row_data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
    date_format = config.dateFormat or "yyyy-MM-dd HH:mm:ss"
    date = parse_date_string(date_string, date_format)

    return RequirementVersionObject(
        name=row_data["version"],
        date=date,
        author=row_data.get("owner", ""),
        comment=row_data.get("comment", ""),
    )


def build_requirement_tree_from_dataframe(
    df: pd.DataFrame, config: ExcelRequirementReaderConfig
) -> list[RequirementObjectNode]:
    """Build requirement tree from dataframe, handling optional hierarchyID.

    If hierarchyID column exists, builds a hierarchical tree structure.
    Otherwise, returns a flat list in the original order.
    """
    if "hierarchyID" in df.columns:
        df = df.sort_values(by="hierarchyID")

    requirement_nodes: dict[str, RequirementObjectNode] = {}
    requirement_tree: list[RequirementObjectNode] = []
    hierarchy_id_mapping: dict[str, str] = {}

    for row in df.to_dict("records"):
        requirement_node = build_requirementobjectnode_from_row_data(row, config)
        requirement_id = requirement_node.key.id

        parent_id = None
        hierarchy = row.get("hierarchyID")
        if hierarchy:
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

    return requirement_tree


def get_config_for_user_defined_attribute(
    name: str, config: ExcelRequirementReaderConfig
) -> UserDefinedAttributeConfig | None:
    return next(
        (udf_cfg for udf_cfg in config.udf_configs if udf_cfg.name == name),
        None,
    )
