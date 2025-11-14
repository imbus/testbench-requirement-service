from pathlib import Path

from testbench_requirement_service.utils.helpers import import_module_from_file_path


def load_config_from_path(config_path: Path):
    try:
        return import_module_from_file_path(config_path)
    except Exception as e:
        raise ImportError(f"Importing reader config from '{config_path.resolve()}' failed.") from e


def load_and_validate_config_from_path(config_path: Path):
    config = load_config_from_path(config_path)

    if not hasattr(config, "BASE_DIR"):
        raise KeyError("BASE_DIR is missing in reader config file.")
    if not getattr(config, "BASE_DIR", None):
        raise ValueError("BASE_DIR is required in reader config file.")
    base_dir = Path(config.BASE_DIR)
    if not base_dir.exists():
        raise FileNotFoundError(f"BASE_DIR not found: '{base_dir.resolve()}'.")

    return config
