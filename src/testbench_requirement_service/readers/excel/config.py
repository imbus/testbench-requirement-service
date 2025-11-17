from pathlib import Path

from testbench_requirement_service.readers.utils import load_properties_config_from_path


def validate_required_settings_in_config(config: dict[str, str]):
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


def validate_optional_settings_in_config(config: dict[str, str]):
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


def validate_column_settings_in_config(config: dict[str, str]):
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


def validate_udf_settings_in_config(config: dict[str, str]):
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


def validate_config(config: dict[str, str], is_project_config: bool = False) -> dict[str, str]:
    validate_required_settings_in_config(config)
    validate_optional_settings_in_config(config)
    validate_column_settings_in_config(config)
    if not is_project_config:
        validate_udf_settings_in_config(config)
    return config


def load_excel_config_from_path(config_path: Path) -> dict[str, str]:
    config = load_properties_config_from_path(config_path)
    return validate_config(config)
