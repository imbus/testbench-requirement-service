import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click
import tomli_w
from pydantic import ValidationError

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

try:
    import javaproperties  # type: ignore[import-not-found]
except ImportError:
    javaproperties = None  # type: ignore[assignment]

from testbench_requirement_service.models.config import RequirementServiceConfig

CONFIG_PREFIX = "testbench-requirement-service"


def create_config_file(
    config: RequirementServiceConfig | dict,
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

    config_data = (
        config.model_dump(mode="json") if isinstance(config, RequirementServiceConfig) else config
    )
    to_serialize = {config_prefix: config_data}
    toml_str = tomli_w.dumps(to_serialize)
    output_path.write_text(toml_str, encoding="utf-8")

    print(f"Configuration file created at '{output_path.resolve()}'.")


def print_config_errors(
    e: ValidationError,
    config_path: Path | None = None,
    config_prefix: str | None = CONFIG_PREFIX,
):
    """
    Print user-friendly config validation errors from a pydantic ValidationError.

    This function processes all validation errors in a pydantic ValidationError instance,
    formatting each error message to show only the field name and its context
    (TOML section or file).

    Args:
        e: Pydantic ValidationError with error details
        config_path: Optional path to the configuration file, used for error messages
        config_prefix: Optional TOML section name (e.g., "testbench-requirement-service")
    """
    for error in e.errors():
        loc = [str(loc) for loc in error["loc"]]
        field_name = loc[-1] if loc else None

        error_type = error.get("type", "")
        if error_type == "missing":
            msg = (
                f"Missing required field '{field_name}'" if field_name else "Missing required field"
            )
            detail = None
        else:
            msg = f"Invalid field '{field_name}'" if field_name else "Invalid configuration"
            detail = error.get("msg")

        if config_path is not None:
            msg += f" in file '{config_path.resolve()}'"
        if config_prefix is not None:
            section_parts = [config_prefix, *loc[:-1]] if config_prefix else loc[:-1]
            section = ".".join(section_parts) if section_parts else config_prefix
            msg += f" in TOML section [{section}]"

        print(f"Configuration Error: {msg}")
        if detail:
            print(f"  Detail: {detail}")
        print()


def load_config_from_toml_file(
    config_path: Path, config_prefix: str = CONFIG_PREFIX
) -> RequirementServiceConfig:
    """
    This function reads a TOML configuration file, extracts the section specified
    by `config_prefix`, and validates it against the `RequirementServiceConfig` model.

    Args:
        config_path (Path): Path to the TOML configuration file.
        config_prefix (str): The top-level section in the TOML file containing the app config.

    Returns:
        RequirementServiceConfig: An instance of the validated application configuration.
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
        return RequirementServiceConfig(**config_dict[config_prefix])
    except ValidationError as e:
        print_config_errors(e, config_path, config_prefix)
        sys.exit(1)


def resolve_config_file_path(config_path: Path | str | None) -> Path:
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


def load_config(config_path: Path | str | None = None) -> RequirementServiceConfig:
    if not config_path:
        config_file_path = resolve_config_file_path(config_path)
    else:
        config_file_path = Path(config_path)
    return load_config_from_toml_file(config_file_path)


def load_toml_config(config_path: Path) -> dict[str, Any]:
    """Load TOML configuration if the config file exists."""
    if not config_path.exists():
        return {}

    try:
        with config_path.open("rb") as config_file:
            return tomllib.load(config_file)
    except (OSError, tomllib.TOMLDecodeError) as e:
        click.echo(f"⚠️  Error loading {config_path}: {e}")
        return {}


def load_properties_config(config_path: Path) -> dict[str, Any]:
    """Load .properties configuration if the config file exists."""
    if not config_path.exists() or javaproperties is None:
        return {}

    try:
        with config_path.open("r") as config_file:
            return javaproperties.load(config_file)  # type: ignore[no-any-return]
    except (OSError, UnicodeDecodeError) as e:
        click.echo(f"⚠️  Error loading {config_path}: {e}")
        return {}


def load_reader_config_from_file(config_path: Path) -> dict:
    """Load reader configuration from a separate file (TOML or properties format).

    Args:
        config_path: Path to the reader config file (.toml or .properties)

    Returns:
        Dictionary containing reader configuration

    Raises:
        ValueError: If file format is unsupported or file not found
    """
    if not config_path.exists():
        raise ValueError(f"Reader config file not found: '{config_path}'")

    suffix = config_path.suffix.lower()
    if suffix == ".toml":
        config = load_toml_config(config_path)
        if CONFIG_PREFIX in config and "reader_config" in config[CONFIG_PREFIX]:
            reader_cfg: dict[Any, Any] = config[CONFIG_PREFIX]["reader_config"]
            return reader_cfg
        return config
    if suffix == ".properties":
        return load_properties_config(config_path)

    raise ValueError(
        f"Unsupported reader config file format: '{suffix}'. Supported formats: .toml, .properties"
    )


def get_reader_config(service_config: RequirementServiceConfig) -> dict:
    """Get reader configuration from service config or separate file.

    Priority:
    1. If reader_config_path points to a separate file that exists, load from there
    2. Otherwise, use reader_config dict from service_config
    """
    if service_config.reader_config_path:
        reader_config_file = service_config.reader_config_path
        if reader_config_file.exists():
            return load_reader_config_from_file(reader_config_file)
        return {}
    return service_config.reader_config


def save_toml_config(config_dict: dict, config_path: Path):
    """Save configuration to TOML configuration file.

    Note: config_dict should already be TOML-serializable (use Pydantic's model_dump(mode='json')).
    """
    try:
        with config_path.open("wb") as config_file:
            tomli_w.dump(config_dict, config_file)
    except (OSError, TypeError, ValueError) as e:
        click.echo(f"❌ Error saving TOML config to {config_path}: {e}")


def update_config_files(
    config_path: Path,
    updates: dict,
    reader_config: dict | None = None,
):
    """Update specific fields in config file while preserving others.

    Args:
        config_path: Path to the main config file
        updates: Dictionary of fields to update in service config section
        reader_config: Optional reader configuration to save to separate file or inline.
                      If None, reader config is not modified.
    """
    service_config = load_service_config(config_path)

    config_data = service_config.model_dump()
    config_data.update(updates)
    updated_config = RequirementServiceConfig.model_validate(config_data)

    if reader_config is not None:
        if updated_config.reader_config_path:
            save_reader_config(reader_config, updated_config.reader_config_path)
            updated_config.reader_config = {}
        else:
            updated_config.reader_config = reader_config
    elif updated_config.reader_config_path:
        updated_config.reader_config = {}

    save_service_config(updated_config, config_path)


def save_properties_config(config_dict: dict, config_path: Path):
    """Save configuration to .properties configuration file.

    Note: config_dict should already be serializable (use Pydantic's model_dump(mode='json')).
    All values will be converted to strings as required by properties format.
    """
    # Convert all values to strings for properties file format
    str_config = {}
    for key, value in config_dict.items():
        if value is None:
            continue
        if isinstance(value, bool):
            str_config[key] = "true" if value else "false"
        else:
            str_config[key] = str(value)

    if javaproperties:
        try:
            with config_path.open("w") as config_file:
                javaproperties.dump(str_config, config_file, timestamp=False)  # type: ignore[no-any-return]
        except (OSError, UnicodeEncodeError) as e:
            click.echo(f"❌ Error saving properties config to {config_path}: {e}")
    else:
        click.echo("⚠️  javaproperties not installed, creating as text file")
        try:
            with config_path.open("w") as f:
                for key, value in str_config.items():
                    f.write(f"{key}={value}\n")
        except OSError as e:
            click.echo(f"❌ Error saving properties config to {config_path}: {e}")


def load_service_config(config_path: Path) -> RequirementServiceConfig:
    """Load service configuration from TOML config file."""
    config_dict = load_toml_config(config_path)
    try:
        return RequirementServiceConfig(**config_dict.get(CONFIG_PREFIX, {}))
    except ValidationError as e:
        print_config_errors(e, config_path, CONFIG_PREFIX)
        sys.exit(1)


def save_service_config(config: RequirementServiceConfig, config_path: Path):
    """Save service configuration to TOML config file."""
    config_dict = {CONFIG_PREFIX: config.model_dump(mode="json", exclude_none=True)}
    save_toml_config(config_dict, config_path)


def save_reader_config(reader_config: dict, reader_config_path: Path):
    """Save reader config to separate file."""
    if reader_config_path.suffix == ".toml":
        save_toml_config(reader_config, reader_config_path)
    elif reader_config_path.suffix == ".properties":
        save_properties_config(reader_config, reader_config_path)


def create_config_backup_file(config_path: Path) -> Path:
    """Create a timestamped backup of the existing config file."""
    backup_path = Path(f"{config_path}.backup")
    if backup_path.exists():
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = Path(f"{config_path}.backup.{timestamp}")
    config_path.rename(backup_path)
    return backup_path
