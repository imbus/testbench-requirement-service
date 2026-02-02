from pathlib import Path

from pydantic import BaseModel

from testbench_requirement_service.readers.abstract_reader import AbstractRequirementReader
from testbench_requirement_service.utils.config import (
    load_properties_config,
    load_toml_config,
)
from testbench_requirement_service.utils.helpers import (
    get_project_root,
    import_class_from_file_path,
    import_class_from_module_str,
)


def load_reader_config_from_path(
    config_path: Path, config_class: type[BaseModel], config_prefix: str | None = None
) -> BaseModel:
    """
    Load reader config from a file path into an instance of config_class.

    Args:
        config_path: Path to the config file (.toml or .properties).
        config_class: Pydantic or dataclass type to instantiate with loaded config.
        config_prefix: Optional key in config dict whose value dict is the config to load.

    Returns:
        An instance of config_class populated with the config data.

    Raises:
        FileNotFoundError: If the config file doesn't exist.
        ValueError: If file format unsupported, prefix missing, or validation fails.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Reader config file not found at: '{config_path.resolve()}'")

    suffix = config_path.suffix.lower()
    if suffix == ".toml":
        config_dict = load_toml_config(config_path)
    elif suffix == ".properties":
        config_dict = load_properties_config(config_path)
    else:
        raise ValueError(
            f"Unsupported config file format: '{suffix}'. Supported formats: .toml and .properties"
        )

    if config_prefix is None:
        config_section = config_dict
    else:
        if config_prefix not in config_dict:
            raise ValueError(f"TOML section [{config_prefix}] not found in reader config file.")
        config_section = config_dict[config_prefix]

    try:
        return config_class.model_validate(config_section)
    except Exception as e:
        raise ValueError(f"Invalid reader config: {e}") from e


def get_reader_class_from_file_path(file_path: Path) -> type[AbstractRequirementReader]:
    try:
        return import_class_from_file_path(file_path, subclass_from=AbstractRequirementReader)  # type: ignore
    except Exception as e:
        message = f"Failed to import custom RequirementReader class from '{file_path}'."
        raise ImportError(message) from e


def get_reader_class_from_module_str(
    reader_name: str, default_package: str = "testbench_requirement_service.readers"
) -> type[AbstractRequirementReader]:
    try:
        if "." in reader_name:
            return import_class_from_module_str(  # type: ignore
                reader_name, subclass_from=AbstractRequirementReader
            )
        return import_class_from_module_str(  # type: ignore
            default_package,
            class_name=reader_name,
            subclass_from=AbstractRequirementReader,
        )
    except Exception as e:
        message = f"Failed to import custom RequirementReader class from '{reader_name}'."
        raise ImportError(message) from e


def get_requirement_reader_from_reader_class_str(
    reader_class: str,
) -> type[AbstractRequirementReader]:
    reader_path = Path(reader_class)
    if reader_path.is_file():
        return get_reader_class_from_file_path(reader_path)
    local_file = Path(__file__).resolve().parent / reader_path
    if local_file.is_file():
        return get_reader_class_from_file_path(local_file)
    if not local_file.suffix and local_file.with_suffix(".py").is_file():
        return get_reader_class_from_file_path(local_file.with_suffix(".py"))
    relative_from_root = get_project_root() / reader_path
    if relative_from_root.is_file():
        return get_reader_class_from_file_path(relative_from_root)
    return get_reader_class_from_module_str(reader_class)


def get_reader_config_class(
    reader_class: str | type[AbstractRequirementReader],
) -> type[BaseModel] | None:
    """Resolve the CONFIG_CLASS for a reader class path or type."""

    reader_cls: type[AbstractRequirementReader]
    if isinstance(reader_class, str):
        reader_cls = get_requirement_reader_from_reader_class_str(reader_class)
    else:
        reader_cls = reader_class

    config_class = getattr(reader_cls, "CONFIG_CLASS", None)
    if config_class is None:
        return None

    if not isinstance(config_class, type) or not issubclass(config_class, BaseModel):
        raise TypeError(
            f"CONFIG_CLASS on {reader_cls.__name__} must inherit from pydantic.BaseModel"
        )

    return config_class


def get_requirement_reader(app) -> AbstractRequirementReader:
    """Get or create the requirement reader instance for the app.
    1. Gets the reader class from app.config.READER_CLASS
    2. Gets the validated reader config from app.config.READER_CONFIG
    3. Instantiates the reader with the validated config
    """
    if not getattr(app.ctx, "requirement_reader", None):
        requirement_reader_class_str = app.config.READER_CLASS
        requirement_reader_class = get_requirement_reader_from_reader_class_str(
            requirement_reader_class_str
        )
        requirement_reader_config = app.config.READER_CONFIG
        requirement_reader = requirement_reader_class(requirement_reader_config)  # type: ignore
        if not isinstance(requirement_reader, AbstractRequirementReader):
            raise ImportError(
                f"{requirement_reader_class} is no instance of AbstractRequirementReader!"
            )
        app.ctx.requirement_reader = requirement_reader
    return app.ctx.requirement_reader  # type: ignore
