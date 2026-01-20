import json
import runpy
import sys
from pathlib import Path

import tomli_w
from pydantic import ValidationError

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from testbench_requirement_service.models.config import Settings

CONFIG_PREFIX = "testbench-requirement-service"


def create_default_config_file(output_path: str, force: bool = False):
    """
    Write the default config to a TOML configuration file.

    Args:
        output_path: Path where the configuration file will be saved.
        force: Overwrite existing file if True.
    """
    default_config_json = Settings().model_dump_json(exclude_none=True)
    default_config = json.loads(default_config_json)
    create_config_file(config=default_config, output_path=output_path, force=force)


def create_config_file(
    config: Settings | dict,
    output_path: str | Path,
    config_prefix: str = CONFIG_PREFIX,
    force: bool = False,
):
    """
    Write the given config object to a TOML configuration file.

    Args:
        config: Settings instance or dict representing configuration.
        output_path: Path where the configuration file will be saved.
        config_prefix: String prefix to nest config under (default: 'testbench-requirement-service')
        force: Overwrite existing file if True.
    """
    output_path = Path(output_path)
    if output_path.exists() and not force:
        print(
            f"Configuration file already exists at '{output_path.resolve()}'. "
            "Use --force to overwrite existing file."
        )
        sys.exit(1)

    config_data = config.model_dump() if isinstance(config, Settings) else config
    to_serialize = {config_prefix: config_data}
    toml_str = tomli_w.dumps(to_serialize)
    output_path.write_text(toml_str, encoding="utf-8")

    print(f"Configuration file created at '{output_path.resolve()}'.")


def print_config_errors(e: ValidationError, config_prefix: str):
    """
    Print user-friendly config validation errors from a pydantic ValidationError.

    This function processes all validation errors in a pydantic ValidationError instance,
    formatting each error message to show only the field name and its TOML section context.
    """
    for error in e.errors():
        loc = [str(loc) for loc in error["loc"]]
        field_name = loc[-1]

        # Build section path
        section_parts = [config_prefix, *loc[:-1]] if config_prefix else loc[:-1]
        section = ".".join(section_parts) if section_parts else config_prefix

        error_type = error.get("type", "")
        if error_type == "missing":
            msg = f"Missing required field '{field_name}' in TOML section [{section}]"
            detail = None
        else:
            msg = f"Invalid field '{field_name}' in TOML section [{section}]"
            detail = error.get("msg")

        print(f"Configuration Error: {msg}")
        if detail:
            print(f"  Detail: {detail}")
        print()


def load_settings_from_python_file(config_path: Path) -> Settings:
    """Load legacy settings from a Python config module (config.py)."""

    if not config_path.exists():
        print(f"Configuration file not found at: '{config_path.resolve()}'.")
        sys.exit(1)

    try:
        config_dict = runpy.run_path(config_path.as_posix())
    except Exception as e:
        print(f"Configuration Error: Failed to read config file.\nDetails: {e}")
        sys.exit(1)

    config_dict = {k.lower(): v for k, v in config_dict.items()}

    try:
        return Settings(**config_dict)
    except ValidationError as e:
        print_config_errors(e, "legacy")
        sys.exit(1)


def load_settings_from_toml_file(config_path: Path, config_prefix: str = CONFIG_PREFIX) -> Settings:
    """
    This function reads a TOML configuration file, extracts the section specified
    by `config_prefix`, and validates it against the `Settings` model.

    Args:
        config_path (Path): Path to the TOML configuration file.
        config_prefix (str): The top-level section in the TOML file containing the app config.

    Returns:
        Settings: An instance of the validated application configuration.
    """
    if not config_path.exists():
        print(f"Configuration file not found at: '{config_path.resolve()}'.")
        sys.exit(1)

    try:
        with config_path.open("rb") as config_file:
            config_dict = tomllib.load(config_file)
    except tomllib.TOMLDecodeError as e:
        print(
            f"Configuration Error: The configuration file contains invalid TOML syntax.\nDetails: {e}"  # noqa: E501
        )
        sys.exit(1)

    if config_prefix not in config_dict:
        print(
            f"Configuration Error: TOML section [{config_prefix}] not found in the configuration file."  # noqa: E501
        )
        sys.exit(1)

    try:
        return Settings(**config_dict[config_prefix])
    except ValidationError as e:
        print_config_errors(e, config_prefix)
        sys.exit(1)


def resolve_config_file_path(config_path: str | None) -> Path:
    """Determine which config file to load, preferring TOML but supporting legacy Python."""

    if config_path:
        return Path(config_path)

    toml_path = Path("config.toml")
    if toml_path.exists():
        return toml_path

    py_path = Path("config.py")
    if py_path.exists():
        return py_path

    return toml_path


def load_settings(config_path: str | None = None) -> Settings:
    if not config_path:
        config_file_path = resolve_config_file_path(config_path)
    else:
        config_file_path = Path(config_path)

    if config_file_path.suffix.lower() == ".py":
        return load_settings_from_python_file(config_file_path)
    return load_settings_from_toml_file(config_file_path)
