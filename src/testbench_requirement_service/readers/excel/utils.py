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

# Data column names that must have a non-blank value in every data row.
_REQUIRED_DATA_COLUMNS: tuple[str, ...] = ("id", "version", "name")


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


def _validate_column_mapping(
    column_mapping: dict[int, list[str]],
    total_columns: int,
    udf_names: set[str],
) -> dict[int, list[str]]:
    """Validate every entry in *column_mapping* against the available column count.

    Returns a filtered mapping that contains only entries whose index is within
    range.  Raises ``ValueError`` immediately for out-of-range *required* columns
    (id, version, name); logs a warning and drops out-of-range optional / UDF
    columns so the import can still proceed without them.
    """
    valid_mapping: dict[int, list[str]] = {}
    for idx, names in column_mapping.items():
        primary_name = names[0]
        if idx < total_columns:
            if len(names) > 1:
                logger.warning(
                    "Column index %d is mapped to multiple fields (%s); "
                    "the same value will be applied to all of them.",
                    idx + 1,
                    ", ".join(f"'{n}'" for n in names),
                )
            valid_mapping[idx] = names
        elif primary_name in _REQUIRED_DATA_COLUMNS:
            raise ValueError(
                f"Required column '{primary_name}' (index {idx + 1}) not found "
                f"in the file ({total_columns} "
                f"column{'s' if total_columns != 1 else ''}). "
                "Check your configuration and make sure the index is within range."
            )
        else:
            kind = "UDF" if primary_name in udf_names else "Optional"
            logger.warning(
                "%s column '%s' (index %d) not found in the file (%d columns); "
                "it will be absent from the imported data.",
                kind,
                primary_name,
                idx + 1,
                total_columns,
            )

    return valid_mapping


def _build_description_series(
    df: pd.DataFrame,
    config: ExcelRequirementReaderConfig,
) -> "pd.Series | None":
    """Build the composite description column from the original (pre-filter) DataFrame.

    Returns ``None`` when description is not configured or all configured indices
    are out of range.
    """
    if not config.requirement_description:
        return None

    total_columns = len(df.columns)
    valid_indices = []
    for config_idx in config.requirement_description:
        col_idx = config_idx - 1
        if col_idx < total_columns:
            valid_indices.append(col_idx)
        else:
            logger.warning(
                "Optional column 'description' (index %d) not found in the file "
                "(%d columns); it will be skipped.",
                config_idx,
                total_columns,
            )

    if not valid_indices:
        return None

    return df.iloc[:, valid_indices].apply(  # type: ignore[no-any-return]
        lambda row: " ".join(str(x) for x in row if x),
        axis=1,
    )


def _apply_column_mapping(
    df: pd.DataFrame,
    valid_mapping: dict[int, list[str]],
    description_series: pd.Series | None,
) -> pd.DataFrame:
    """Apply a pre-validated column mapping to the DataFrame.

    Filters the DataFrame to only the mapped columns (by position), renames
    them to their logical field names, copies any alias fields for multi-field
    entries, and attaches the pre-built description column if provided.
    """
    ordered_indices = sorted(valid_mapping.keys())
    df = df.iloc[:, ordered_indices].copy()
    df.columns = pd.Index([valid_mapping[idx][0] for idx in ordered_indices])

    for names in valid_mapping.values():
        for alias in names[1:]:
            df[alias] = df[names[0]]

    if description_series is not None:
        df["description"] = description_series.values

    return df


def _validate_required_column_values(
    df: pd.DataFrame,
    file_path: Path,
    config: ExcelRequirementReaderConfig,
) -> None:
    """Raise ``ValueError`` if any required column is missing or contains blank values.

    Checks:
    - The column is present in the DataFrame at all (i.e. ``requirement.<col>``
      was configured and its index was in range).
    - Every row has a non-blank value in that column.

    Reports 1-based file row numbers so the user can locate the offending rows
    directly, taking ``header.rowIdx`` and ``data.rowIdx`` into account.
    All violations across all required columns are collected and reported
    together so the user can fix everything in one pass.
    """
    first_data_file_row = config.data_rowIdx or 2

    errors: list[str] = []
    for col in _REQUIRED_DATA_COLUMNS:
        if col not in df.columns:
            errors.append(
                f"  - 'requirement.{col}': column is not configured or could not be found. "
                "Set a valid 'requirement." + col + "' column index in your configuration."
            )
            continue
        blank_indices = df.index[df[col].str.strip() == ""].tolist()
        if not blank_indices:
            continue
        config_key = f"requirement.{col}"
        row_label = "row" if len(blank_indices) == 1 else "rows"
        max_displayed_rows = 10
        displayed = [str(first_data_file_row + i) for i in blank_indices[:max_displayed_rows]]
        overflow = len(blank_indices) - max_displayed_rows
        suffix = f" (and {overflow} more)" if overflow > 0 else ""
        errors.append(f"  - '{config_key}': empty at {row_label} {', '.join(displayed)}{suffix}")

    if errors:
        raise ValueError(
            f"Required columns contain empty values in '{file_path}':\n" + "\n".join(errors)
        )


def _validate_unique_constraints(
    df: pd.DataFrame,
    file_path: Path,
    config: ExcelRequirementReaderConfig,
) -> None:
    """Raise ``ValueError`` if uniqueness constraints are violated.

    Checks:
    - ``hierarchyID`` values must be unique.
    - ``(id, version)`` tuples must be unique across all rows.

    Reports 1-based file row numbers and collects all violations before raising
    so the user can fix everything in one pass.
    """
    first_data_file_row = config.data_rowIdx or 2
    max_displayed_rows = 10

    errors: list[str] = []

    if "hierarchyID" in df.columns:
        non_empty_mask = df["hierarchyID"].astype(str).str.strip() != ""
        non_empty = df[non_empty_mask]
        duplicated_mask = non_empty.duplicated(subset=["hierarchyID"], keep=False)
        duplicate_values = non_empty.loc[duplicated_mask, "hierarchyID"].unique()
        for dup_value in duplicate_values:
            indices = non_empty.index[non_empty["hierarchyID"] == dup_value].tolist()
            displayed = [str(first_data_file_row + i) for i in indices[:max_displayed_rows]]
            overflow = len(indices) - max_displayed_rows
            suffix = f" (and {overflow} more)" if overflow > 0 else ""
            errors.append(
                f"  - 'requirement.hierarchyID': duplicate value {dup_value!r} at "
                f"rows {', '.join(displayed)}{suffix}"
            )

    if "id" in df.columns and "version" in df.columns:
        duplicated_mask = df.duplicated(subset=["id", "version"], keep=False)
        duplicate_pairs = df.loc[duplicated_mask, ["id", "version"]].drop_duplicates()
        for _, pair_row in duplicate_pairs.iterrows():
            dup_id, dup_version = pair_row["id"], pair_row["version"]
            indices = df.index[(df["id"] == dup_id) & (df["version"] == dup_version)].tolist()
            displayed = [str(first_data_file_row + i) for i in indices[:max_displayed_rows]]
            overflow = len(indices) - max_displayed_rows
            suffix = f" (and {overflow} more)" if overflow > 0 else ""
            errors.append(
                f"  - '(requirement.id, requirement.version)': duplicate tuple "
                f"({dup_id!r}, {dup_version!r}) at rows {', '.join(displayed)}{suffix}"
            )

    if errors:
        raise ValueError(f"Uniqueness constraints violated in '{file_path}':\n" + "\n".join(errors))


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
    udf_names = {udf_cfg.name for udf_cfg in config.udf_configs}
    valid_mapping = _validate_column_mapping(column_mapping, len(df.columns), udf_names)

    description_series = _build_description_series(df, config)
    df = _apply_column_mapping(df, valid_mapping, description_series)
    _validate_required_column_values(df, file_path, config)
    _validate_unique_constraints(df, file_path, config)

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
    key = RequirementKey(id=row_data["id"], version=row_data["version"])
    folder_pattern = config.requirement_folderPattern
    is_requirement = re.fullmatch(folder_pattern, row_data.get("type", "")) is None

    return RequirementObjectNode(
        name=row_data["name"],
        extendedID=row_data["id"],
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
    now_string = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    date_string = row_data.get("date", now_string)
    date_format = config.dateFormat or "dd/MM/yyyy"
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
