"""Configuration management for TestBench Requirement Service."""

import os
import runpy
import sys
from pathlib import Path
from typing import Literal

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib
from pydantic import BaseModel, ValidationError, field_validator
from sanic.config import Config

CONFIG_PREFIX = "testbench-requirement-service"


class Settings(BaseModel):
    """Validated settings loaded from TOML or legacy Python config."""

    reader_class: str = "testbench_requirement_service.readers.JsonlRequirementReader"
    reader_config_path: str = "reader_config.toml"
    loglevel: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    password_hash: str | None = None
    salt: str | None = None

    @field_validator("reader_config_path")
    @classmethod
    def validate_reader_config_exists(cls, v: str) -> str:
        if not Path(v).exists():
            raise ValueError(f"Reader config file not found: '{v}'")
        return v


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


def load_settings(config_path: str | None) -> Settings:
    if not config_path:
        config_file_path = resolve_config_file_path(config_path)
    else:
        config_file_path = Path(config_path)

    if config_file_path.suffix.lower() == ".py":
        return load_settings_from_python_file(config_file_path)
    return load_settings_from_toml_file(config_file_path)


class AppConfig(Config):
    """Sanic configuration with uppercase attributes (Sanic requirement)."""

    def __init__(
        self,
        config_path: str | None = None,
        reader_class: str | None = None,
        reader_config_path: str | None = None,
        loglevel: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        # Sanic-specific settings
        self.OAS_UI_DEFAULT = "swagger"
        self.OAS_UI_REDOC = False
        self.OAS_CUSTOM_FILE = (Path(__file__).parent / "openapi.yaml").resolve().as_posix()
        self.OAS_PATH_TO_SWAGGER_HTML = (
            (Path(__file__).parent / "static/swagger-ui/index.html").resolve().as_posix()
        )

        # Load settings from config file
        settings = load_settings(config_path)

        # Map validated settings to uppercase Sanic config
        self.READER_CLASS = settings.reader_class
        self.READER_CONFIG_PATH = settings.reader_config_path
        self.LOGLEVEL = settings.loglevel

        # Override with CLI parameters (highest priority)
        if reader_class:
            self.READER_CLASS = reader_class
        if reader_config_path:
            self.READER_CONFIG_PATH = reader_config_path
        if loglevel:
            self.LOGLEVEL = loglevel

        # Load credentials
        self.PASSWORD_HASH = settings.password_hash or os.getenv("PASSWORD_HASH") or ""
        self.SALT = settings.salt or os.getenv("SALT") or ""
