from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.fields import FieldInfo

INVALID_SEPARATOR_CHARS = {"\r", "\n", "\r\n", '"'}


class ExcelRequirementReaderConfigValidatorsMixin:
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

    @field_validator("header_rowIdx")
    @classmethod
    def validate_header_row_idx(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError(
                "Invalid value for 'header.rowIdx' in reader config: "
                f"Expected a positive integer (starting from 1), but got '{v}'."
            )
        return v

    @model_validator(mode="after")
    def validate_config(self):
        validate_array_value_separator(self)
        validate_data_row_idx(self)
        validate_column_settings(self)
        return self


class ExcelRequirementReaderProjectConfig(BaseModel, ExcelRequirementReaderConfigValidatorsMixin):
    columnSeparator: str | None = Field(None, alias="columnSeparator")
    arrayValueSeparator: str | None = Field(None, alias="arrayValueSeparator")
    baselineFileExtensions: list[str] | None = Field(None, alias="baselineFileExtensions")

    useExcelDirectly: bool | None = Field(None, alias="useExcelDirectly")
    baselinesFromSubfolders: bool | None = Field(None, alias="baselinesFromSubfolders")
    worksheetName: str | None = Field(None, alias="worksheetName")
    dateFormat: str | None = Field(None, alias="dateFormat")
    header_rowIdx: int | None = Field(None, alias="header.rowIdx")
    data_rowIdx: int | None = Field(None, alias="data.rowIdx")

    requirement_hierarchyID: int | None = Field(None, alias="requirement.hierarchyID")
    requirement_id: int | None = Field(None, alias="requirement.id")
    requirement_version: int | None = Field(None, alias="requirement.version")
    requirement_name: int | None = Field(None, alias="requirement.name")
    requirement_owner: int | None = Field(None, alias="requirement.owner")
    requirement_status: int | None = Field(None, alias="requirement.status")
    requirement_priority: int | None = Field(None, alias="requirement.priority")
    requirement_comment: int | None = Field(None, alias="requirement.comment")
    requirement_date: int | None = Field(None, alias="requirement.date")
    requirement_references: int | None = Field(None, alias="requirement.references")
    requirement_description: list[int] | None = Field(None)
    requirement_type: int | None = Field(None, alias="requirement.type")
    requirement_folderPattern: str | None = Field(None, alias="requirement.folderPattern")

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
    requirementsDataPath: Path = Field(..., alias="requirementsDataPath")

    columnSeparator: str = Field(..., alias="columnSeparator")
    arrayValueSeparator: str = Field(..., alias="arrayValueSeparator")
    baselineFileExtensions: list[str] = Field(..., alias="baselineFileExtensions")

    useExcelDirectly: bool = Field(False, alias="useExcelDirectly")
    baselinesFromSubfolders: bool = Field(False, alias="baselinesFromSubfolders")
    worksheetName: str | None = Field(None, alias="worksheetName")
    dateFormat: str | None = Field(None, alias="dateFormat")
    header_rowIdx: int | None = Field(None, alias="header.rowIdx")
    data_rowIdx: int | None = Field(None, alias="data.rowIdx")

    requirement_hierarchyID: int | None = Field(None, alias="requirement.hierarchyID")
    requirement_id: int = Field(..., alias="requirement.id")
    requirement_version: int = Field(..., alias="requirement.version")
    requirement_name: int = Field(..., alias="requirement.name")
    requirement_owner: int | None = Field(None, alias="requirement.owner")
    requirement_status: int | None = Field(None, alias="requirement.status")
    requirement_priority: int | None = Field(None, alias="requirement.priority")
    requirement_comment: int | None = Field(None, alias="requirement.comment")
    requirement_date: int | None = Field(None, alias="requirement.date")
    requirement_references: int | None = Field(None, alias="requirement.references")
    requirement_description: list[int] | None = Field(default_factory=list)
    requirement_type: int | None = Field(None, alias="requirement.type")
    requirement_folderPattern: str = Field(".*folder.*", alias="requirement.folderPattern")

    udf_count: int = Field(0, alias="udf.count")
    udf_configs: list[UserDefinedAttributeConfig] = Field(default_factory=list)

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
            raise FileNotFoundError(
                f"'requirementsDataPath' defined in reader config not found: '{v.resolve()}'."
            )
        return v


def validate_array_value_separator(config) -> None:
    array_sep = getattr(config, "arrayValueSeparator", None)
    column_sep = getattr(config, "columnSeparator", None)
    if array_sep is None or column_sep is None:
        return
    if any(char in array_sep for char in INVALID_SEPARATOR_CHARS | {column_sep}):
        raise ValueError(
            "Invalid value for 'arrayValueSeparator' in reader config: "
            "Cannot contain line feed characters ('\\r', '\\n', '\\r\\n'), "
            "double quotes ('\"') or the defined 'columnSeparator'"
            f"({column_sep!r})."
        )


def validate_data_row_idx(config) -> None:
    data_row_idx = getattr(config, "data_rowIdx", None)
    header_row_idx = getattr(config, "header_rowIdx", None)

    if data_row_idx is None:
        return
    if data_row_idx < 1:
        raise ValueError(
            "Invalid value for 'data.rowIdx' in reader config: "
            f"Expected a positive integer (starting from 1), but got '{data_row_idx}'."
        )
    if header_row_idx is not None and data_row_idx <= header_row_idx:
        raise ValueError(
            "Invalid value for 'data.rowIdx' in reader config: "
            "Expected a row index (starting from 1) greater than 'header.rowIdx'"
            f"({header_row_idx}), but got {data_row_idx}."
        )


def validate_column_settings(config) -> None:
    column_idx_mapping: dict[int, str] = {}
    for field_name, field_info in config.column_settings.items():
        field_value = getattr(config, field_name)
        if field_value is None:
            continue
        if isinstance(field_value, list):
            field_alias = field_name.replace("_", ".")
            for idx, column_idx in enumerate(field_value, start=1):
                alias_with_idx = f"{field_alias}.{idx}"
                validate_column_index(column_idx, alias_with_idx, column_idx_mapping)
        elif isinstance(field_value, int):
            validate_column_index(field_value, field_info.alias, column_idx_mapping)


def validate_column_index(column_idx: int, field_alias: str, column_idx_mapping: dict[int, str]):
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
