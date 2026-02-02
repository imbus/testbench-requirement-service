from pathlib import Path
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    ValidationInfo,
    field_validator,
    model_serializer,
    model_validator,
)
from pydantic.fields import FieldInfo

INVALID_SEPARATOR_CHARS = {"\r", "\n", "\r\n", '"'}


class ExcelRequirementReaderConfigValidatorsMixin:
    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def build_derived_fields(cls, values: dict) -> dict:
        build_baseline_file_extensions_field(values)
        build_requirement_description_field(values)
        build_udf_configs_field(values)
        return values

    @field_validator("columnSeparator")
    @classmethod
    def validate_column_separator(cls, v: str) -> str:
        return validate_column_separator(v)

    @field_validator("arrayValueSeparator")
    @classmethod
    def validate_array_value_separator_field(cls, v: str, info: ValidationInfo) -> str:
        return validate_array_value_separator(v, info.data)

    @field_validator("header_rowIdx")
    @classmethod
    def validate_header_row_idx(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError(
                "Invalid value for 'header.rowIdx' in reader config: "
                f"Expected a positive integer (starting from 1), but got '{v}'."
            )
        return v

    @field_validator("data_rowIdx")
    @classmethod
    def validate_data_row_idx_field(cls, v: int | None, info: ValidationInfo) -> int | None:
        return validate_data_row_idx(v, info.data)

    @field_validator(
        "requirement_hierarchyID",
        "requirement_id",
        "requirement_version",
        "requirement_name",
        "requirement_owner",
        "requirement_status",
        "requirement_priority",
        "requirement_comment",
        "requirement_date",
        "requirement_references",
        "requirement_description",
        "requirement_type",
    )
    @classmethod
    def validate_requirement_column_field(
        cls, v: int | list[int] | None, info: ValidationInfo
    ) -> int | list[int] | None:
        """Validate requirement column fields against already validated fields.

        Prevents duplicate column indices across requirement fields.
        """
        if v is None or info.field_name is None:
            return v
        return validate_column_setting(info.field_name, v, info.data)

    @field_validator("bufferMaxAgeMinutes")
    @classmethod
    def validate_buffer_max_age_minutes(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError(
                "Invalid value for 'bufferMaxAgeMinutes' in reader config: "
                f"Expected a positive number of minutes, but got '{v}'."
            )
        return v

    @field_validator("bufferMaxSizeMiB")
    @classmethod
    def validate_buffer_max_size_mib(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError(
                "Invalid value for 'bufferMaxSizeMiB' in reader config: "
                f"Expected a positive number of MiB, but got '{v}'."
            )
        return v

    @field_validator("bufferCleanupIntervalMinutes")
    @classmethod
    def validate_buffer_cleanup_interval_minutes(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError(
                "Invalid value for 'bufferCleanupIntervalMinutes' in reader config: "
                f"Expected a positive number of minutes, but got '{v}'."
            )
        return v


class ExcelRequirementReaderProjectConfig(BaseModel, ExcelRequirementReaderConfigValidatorsMixin):
    columnSeparator: str | None = Field(
        None, alias="columnSeparator", description="Column separator character"
    )
    arrayValueSeparator: str | None = Field(
        None, alias="arrayValueSeparator", description="Separator for array values within cells"
    )
    baselineFileExtensions: list[str] | None = Field(
        None,
        alias="baselineFileExtensions",
        description="Allowed file extensions for baseline files (comma-separated)",
    )

    useExcelDirectly: bool | None = Field(
        None, alias="useExcelDirectly", description="Read directly from Excel files (.xlsx)"
    )
    baselinesFromSubfolders: bool | None = Field(
        None, alias="baselinesFromSubfolders", description="Look for baselines in subfolders"
    )
    worksheetName: str | None = Field(
        None, alias="worksheetName", description="Worksheet name (for Excel files)"
    )
    dateFormat: str | None = Field(
        None, alias="dateFormat", description="Date format string (e.g., %Y-%m-%d)"
    )
    header_rowIdx: int | None = Field(
        None, alias="header.rowIdx", description="Row index for header (1-based)"
    )
    data_rowIdx: int | None = Field(
        None, alias="data.rowIdx", description="Row index where data starts (1-based)"
    )

    requirement_hierarchyID: int | None = Field(
        None, alias="requirement.hierarchyID", description="Column index for hierarchy ID"
    )
    requirement_id: int | None = Field(
        None, alias="requirement.id", description="Column index for requirement ID"
    )
    requirement_version: int | None = Field(
        None, alias="requirement.version", description="Column index for requirement version"
    )
    requirement_name: int | None = Field(
        None, alias="requirement.name", description="Column index for requirement name"
    )
    requirement_owner: int | None = Field(
        None, alias="requirement.owner", description="Column index for requirement owner"
    )
    requirement_status: int | None = Field(
        None, alias="requirement.status", description="Column index for requirement status"
    )
    requirement_priority: int | None = Field(
        None, alias="requirement.priority", description="Column index for requirement priority"
    )
    requirement_comment: int | None = Field(
        None, alias="requirement.comment", description="Column index for requirement comment"
    )
    requirement_date: int | None = Field(
        None, alias="requirement.date", description="Column index for requirement date"
    )
    requirement_references: int | None = Field(
        None,
        alias="requirement.references",
        description="Column index for requirement references",
    )
    requirement_description: list[int] | None = Field(
        None, description="Column indices for requirement description parts"
    )
    requirement_type: int | None = Field(
        None, alias="requirement.type", description="Column index for requirement type"
    )
    requirement_folderPattern: str | None = Field(
        None,
        alias="requirement.folderPattern",
        description="Regex pattern to identify folder/group requirements",
    )

    bufferMaxAgeMinutes: float | None = Field(None, alias="bufferMaxAgeMinutes")
    bufferMaxSizeMiB: float | None = Field(None, alias="bufferMaxSizeMiB")
    bufferCleanupIntervalMinutes: float | None = Field(None, alias="bufferCleanupIntervalMinutes")

    @property
    def column_settings(self) -> dict[str, FieldInfo]:
        return {
            field_name: field_info
            for field_name, field_info in self.__class__.model_fields.items()
            if field_name.startswith("requirement_")
        }


class UserDefinedAttributeConfig(BaseModel):
    name: str
    type: Literal["STRING", "ARRAY", "BOOLEAN"]
    column: int
    trueValue: str | None = None


class ExcelRequirementReaderConfig(BaseModel, ExcelRequirementReaderConfigValidatorsMixin):
    requirementsDataPath: Path = Field(
        ..., alias="requirementsDataPath", description="Path to the requirements data directory"
    )

    columnSeparator: str = Field(
        ..., alias="columnSeparator", description="Column separator character"
    )
    arrayValueSeparator: str = Field(
        ..., alias="arrayValueSeparator", description="Separator for array values within cells"
    )
    baselineFileExtensions: list[str] = Field(
        ...,
        alias="baselineFileExtensions",
        description=(
            "Allowed file extensions for baseline files (comma-separated, e.g., .tsv,.csv,.txt)"
        ),
    )

    useExcelDirectly: bool = Field(
        False, alias="useExcelDirectly", description="Read directly from Excel files (.xlsx)"
    )
    baselinesFromSubfolders: bool = Field(
        False, alias="baselinesFromSubfolders", description="Look for baselines in subfolders"
    )
    worksheetName: str | None = Field(
        None, alias="worksheetName", description="Worksheet name (for Excel files)"
    )
    dateFormat: str | None = Field(
        None, alias="dateFormat", description="Date format string (e.g., %Y-%m-%d)"
    )
    header_rowIdx: int | None = Field(
        None, alias="header.rowIdx", description="Row index for header (1-based)"
    )
    data_rowIdx: int | None = Field(
        None, alias="data.rowIdx", description="Row index where data starts (1-based)"
    )

    requirement_hierarchyID: int | None = Field(
        None, alias="requirement.hierarchyID", description="Column index for hierarchy ID"
    )
    requirement_id: int = Field(
        ..., alias="requirement.id", description="Column index for requirement ID"
    )
    requirement_version: int = Field(
        ..., alias="requirement.version", description="Column index for requirement version"
    )
    requirement_name: int = Field(
        ..., alias="requirement.name", description="Column index for requirement name"
    )
    requirement_owner: int | None = Field(
        None, alias="requirement.owner", description="Column index for requirement owner"
    )
    requirement_status: int | None = Field(
        None, alias="requirement.status", description="Column index for requirement status"
    )
    requirement_priority: int | None = Field(
        None, alias="requirement.priority", description="Column index for requirement priority"
    )
    requirement_comment: int | None = Field(
        None, alias="requirement.comment", description="Column index for requirement comment"
    )
    requirement_date: int | None = Field(
        None, alias="requirement.date", description="Column index for requirement date"
    )
    requirement_references: int | None = Field(
        None, alias="requirement.references", description="Column index for requirement references"
    )
    requirement_description: list[int] = Field(
        default_factory=list, description="Column indices for requirement description parts"
    )
    requirement_type: int | None = Field(
        None, alias="requirement.type", description="Column index for requirement type"
    )
    requirement_folderPattern: str = Field(
        ".*folder.*",
        alias="requirement.folderPattern",
        description="Regex pattern to identify folder/group requirements",
    )

    bufferMaxAgeMinutes: float = Field(1440.0, alias="bufferMaxAgeMinutes")
    bufferMaxSizeMiB: float = Field(1024.0, alias="bufferMaxSizeMiB")
    bufferCleanupIntervalMinutes: float = Field(1.0, alias="bufferCleanupIntervalMinutes")

    udf_count: int = Field(
        0,
        alias="udf.count",
        description="Number of user-defined attributes (auto-generated)",
        json_schema_extra={"skip_if_wizard": True},
    )
    udf_configs: list[UserDefinedAttributeConfig] = Field(
        default_factory=list,
        description="User-defined attribute configurations",
        json_schema_extra={"prompt_as_list": True, "item_label": "User Defined Attribute"},
    )

    @property
    def column_settings(self) -> dict[str, FieldInfo]:
        return {
            field_name: field_info
            for field_name, field_info in self.__class__.model_fields.items()
            if field_name.startswith("requirement_")
        }

    @field_validator("requirementsDataPath")
    @classmethod
    def validate_requirements_data_path(cls, v: Path) -> Path:
        if not v.exists():
            raise ValueError(
                f"'requirementsDataPath' defined in reader config not found: '{v}'.\n"
                "  Hint: Use forward slashes (C:/path/to/folder)"
                " or double-backslashes (C:\\\\path\\\\to\\\\folder)"
            )
        return v

    @model_serializer(mode="wrap")
    def serialize_model(self, serializer: SerializerFunctionWrapHandler, info: SerializationInfo):
        """Custom serializer that flattens derived fields for properties file export."""
        data = serializer(self)

        # Only flatten when serializing by alias (for properties files)
        if info.by_alias:
            dump_baseline_file_extensions_field(data)
            dump_requirement_description_field(data)
            dump_udf_configs_field(data)

        return data


def validate_array_value_separator(v: str, data: dict) -> str:
    """Validate arrayValueSeparator against columnSeparator.

    Args:
        v: The arrayValueSeparator value to validate
        data: ValidationInfo.data containing other field values

    Returns:
        The validated arrayValueSeparator value
    """
    column_sep = data.get("columnSeparator")
    if column_sep is None:
        return v
    if any(char in v for char in INVALID_SEPARATOR_CHARS | {column_sep}):
        raise ValueError(
            "Invalid value for 'arrayValueSeparator' in reader config: "
            "Cannot contain line feed characters ('\\r', '\\n', '\\r\\n'), "
            "double quotes ('\"') or the defined 'columnSeparator' "
            f"({column_sep!r})."
        )
    return v


def validate_data_row_idx(v: int | None, data: dict) -> int | None:
    """Validate data_rowIdx against header_rowIdx.

    Args:
        v: The data_rowIdx value to validate
        data: ValidationInfo.data containing other field values

    Returns:
        The validated data_rowIdx value
    """
    if v is None:
        return v
    if v < 1:
        raise ValueError(
            "Invalid value for 'data.rowIdx' in reader config: "
            f"Expected a positive integer (starting from 1), but got '{v}'."
        )

    header_row_idx = data.get("header_rowIdx") or data.get("header.rowIdx")
    if header_row_idx is not None and v <= header_row_idx:
        raise ValueError(
            "Invalid value for 'data.rowIdx' in reader config: "
            f"Must be greater than 'header.rowIdx' ({header_row_idx}), but got '{v}'."
        )
    return v


def _get_field_alias(field_name: str) -> str:
    """Convert field name to field alias for error messages.

    Args:
        field_name: The field name (e.g., 'requirement_id')

    Returns:
        The field alias (e.g., 'requirement.id')
    """
    if field_name == "requirement_description":
        return "requirement.description"
    return field_name.replace("_", ".", 1)


def validate_column_setting(field_name: str, value: int | list[int], data: dict) -> int | list[int]:
    """Validate a single column setting field against already validated fields.

    Args:
        field_name: Name of the field being validated (e.g., 'requirement_id')
        value: The column index or list of column indices
        data: ValidationInfo.data containing already validated fields

    Returns:
        The validated value
    """
    column_idx_mapping: dict[int, str] = {}
    for key, val in data.items():
        if key.startswith("requirement_") and key != field_name and val is not None:
            field_alias = _get_field_alias(key)
            if isinstance(val, list):
                for idx, column_idx in enumerate(val, start=1):
                    if isinstance(column_idx, int):
                        _validate_column_index(
                            column_idx,
                            f"{field_alias}.{idx}",
                            column_idx_mapping,
                        )
            elif isinstance(val, int):
                _validate_column_index(val, field_alias, column_idx_mapping)
    field_alias = _get_field_alias(field_name)
    if isinstance(value, list):
        for idx, column_idx in enumerate(value, start=1):
            _validate_column_index(column_idx, f"{field_alias}.{idx}", column_idx_mapping)
    elif isinstance(value, int):
        _validate_column_index(value, field_alias, column_idx_mapping)

    return value


def _validate_column_index(
    column_idx: int, field_alias: str, column_idx_mapping: dict[int, str]
) -> None:
    """Validate a single column index and add to mapping if valid.

    Args:
        column_idx: The column index to validate
        field_alias: The field alias for error messages
        column_idx_mapping: Mapping of already validated column indices

    Raises:
        ValueError: If column index is invalid or already used
    """
    if not isinstance(column_idx, int) or column_idx < 1:
        raise ValueError(
            f"Invalid value for '{field_alias}' in reader config: "
            "Expected a positive integer (starting from 1), "
            f"but got '{column_idx}'."
        )
    if column_idx in column_idx_mapping:
        assigned = column_idx_mapping[column_idx]
        raise ValueError(
            f"Invalid value for '{field_alias}' in reader config: "
            f"Column index {column_idx} is already assigned to '{assigned}'."
        )
    column_idx_mapping[column_idx] = field_alias


def validate_column_separator(v: str) -> str:
    if any(char in v for char in INVALID_SEPARATOR_CHARS):
        raise ValueError(
            "Invalid value for 'columnSeparator' in reader config: "
            "Must not contain line feed characters ('\\r', '\\n', '\\r\\n')"
            " or double quotes ('\"')."
        )
    return v


def build_baseline_file_extensions_field(config: dict) -> list[str]:
    if "baselineFileExtensions" not in config:
        return []
    value = config["baselineFileExtensions"]
    if isinstance(value, list):
        extensions = value
    else:
        extensions_str = str(value)
        extensions = [ext.strip() for ext in extensions_str.split(",") if ext.strip()]
    config["baselineFileExtensions"] = extensions
    return extensions


def build_requirement_description_field(config: dict) -> list[int]:
    description_settings = [
        key
        for key in config
        if key.startswith("requirement.description.")
        and key.rpartition(".")[2].isdigit()
        and int(key.rpartition(".")[2]) >= 1
    ]
    if not description_settings:
        return []
    description_settings.sort()
    description_columns: list[int] = []
    for setting in description_settings:
        column_raw = config.get(setting)
        if column_raw is None or str(column_raw).strip() == "":
            raise ValueError(
                f"Invalid value for '{setting}' in reader config: Value cannot be empty."
            )
        try:
            column_idx = int(column_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid value for '{setting}' in reader config: "
                f"Expected a positive integer (starting from 1), but got '{column_raw}'."
            ) from exc
        description_columns.append(column_idx)
    config["requirement_description"] = description_columns
    return description_columns


def build_udf_configs_field(config: dict) -> list[UserDefinedAttributeConfig]:
    if "udf.count" not in config:
        return []
    udf_count = _parse_udf_count(config.get("udf.count", "0"))
    udf_configs: list[UserDefinedAttributeConfig] = []
    for i in range(1, udf_count + 1):
        udf_configs.append(_build_single_udf_config(config, i))
    config["udf_configs"] = udf_configs
    return udf_configs


def dump_baseline_file_extensions_field(data: dict) -> None:
    """Convert baselineFileExtensions list to comma-separated string for properties export."""
    if "baselineFileExtensions" in data and isinstance(data["baselineFileExtensions"], list):
        data["baselineFileExtensions"] = ",".join(
            str(ext) for ext in data["baselineFileExtensions"]
        )


def dump_requirement_description_field(data: dict) -> None:
    """Flatten requirement_description list to individual requirement.description.N keys."""
    if "requirement_description" in data and isinstance(data["requirement_description"], list):
        desc_list = data.pop("requirement_description")
        for idx, col_idx in enumerate(desc_list, start=1):
            data[f"requirement.description.{idx}"] = col_idx


def dump_udf_configs_field(data: dict) -> None:
    """Flatten udf_configs list to individual udf.attrN.* keys for properties export."""
    if "udf_configs" in data and isinstance(data["udf_configs"], list):
        udf_list = data.pop("udf_configs")
        data["udf.count"] = len(udf_list)
        for idx, udf in enumerate(udf_list, start=1):
            data[f"udf.attr{idx}.name"] = udf["name"]
            data[f"udf.attr{idx}.type"] = udf["type"]
            data[f"udf.attr{idx}.column"] = udf["column"]
            if udf.get("trueValue") is not None:
                data[f"udf.attr{idx}.trueValue"] = udf["trueValue"]


def _parse_udf_count(raw_count: object) -> int:
    udf_count_str = str(raw_count)
    if not udf_count_str.isdigit() or int(udf_count_str) < 0:
        raise ValueError(
            "Invalid value for 'udf.count' in reader config: "
            f"Expected an integer, but got '{udf_count_str}'."
        )
    return int(udf_count_str)


def _build_single_udf_config(config: dict[str, Any], i: int) -> UserDefinedAttributeConfig:
    udf_config: dict[str, Any] = {
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

    try:
        column_idx = int(udf_config["column"])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid value for 'udf.attr{i}.column' in reader config: "
            f"Expected a positive integer (starting from 1), but got '{udf_config['column']}'."
        ) from exc
    if column_idx < 1:
        raise ValueError(
            f"Invalid value for 'udf.attr{i}.column' in reader config: "
            f"Expected a positive integer (starting from 1), but got '{column_idx}'."
        )

    type_upper = str(udf_config["type"]).upper()
    if type_upper not in {"STRING", "ARRAY", "BOOLEAN"}:
        raise ValueError(
            f"Invalid value for 'udf.attr{i}.type' in reader config: "
            "Expected 'string', 'array' or 'boolean' (case insensitive), "
            f"but got '{udf_config['type']}'."
        )

    return UserDefinedAttributeConfig(
        name=str(udf_config["name"]),
        type=type_upper,  # type: ignore
        column=column_idx,
        trueValue=str(udf_config["trueValue"]) if udf_config["trueValue"] is not None else None,
    )
