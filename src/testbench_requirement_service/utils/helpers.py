import importlib.util
import inspect
from pathlib import Path


def import_module_from_file_path(file_path: Path):
    """Imports a module dynamically from a file path."""
    file_path = Path(file_path).resolve()
    module_name = file_path.stem

    if not file_path.exists() or file_path.suffix != ".py":
        raise FileNotFoundError(f"File '{file_path}' not found or not a .py file.")

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from '{file_path}'.")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        raise ImportError(f"Failed to import module from '{file_path}': {e}") from e


def import_class_from_file_path(
    file_path: Path, class_name: str | None = None, subclass_from: type | None = None
):
    """Imports a class dynamically from a Python file at file_path.

    Args:
        file_path (Path): The path to the Python file.
        class_name (str | None): The specific class name to import (optional).
        subclass_from (type | None): If set, finds a direct subclass of this type.

    Returns:
        type: The imported class.

    Raises:
        ImportError: If the class cannot be found or loaded.
    """
    module = None
    try:
        module = import_module_from_file_path(file_path)

        if subclass_from:
            subclasses = [
                cls
                for _, cls in inspect.getmembers(module, inspect.isclass)
                if subclass_from in cls.__bases__ and cls is not subclass_from
            ]
            if not subclasses:
                raise ImportError(
                    f"No direct subclass of '{subclass_from.__name__}' found in '{file_path}'."
                )
            return subclasses[0]

        if class_name is None:
            class_name = module.__name__

        if not hasattr(module, class_name):
            raise ImportError(f"Class '{class_name}' not found in file '{file_path}'.")

        imported_class = getattr(module, class_name)
        if not inspect.isclass(imported_class):
            raise ImportError(f"'{class_name}' in '{file_path}' is not a valid class.")

        return imported_class

    except Exception as e:
        raise ImportError(f"Failed to import class from '{file_path}': {e}") from e


def import_class_from_module_str(
    module_str: str, class_name: str | None = None, subclass_from: type | None = None
):
    """Imports a class dynamically from a module string.

    Args:
        module_str (str): The module import string (e.g., "my_package.my_module")
        class_name (str | None): The specific class name to import (optional).
        subclass_from (type | None): If set, finds a direct subclass of this type.

    Returns:
        type: The imported class.

    Raises:
        ImportError: If the class cannot be found or loaded.
    """
    module = None
    try:
        module = importlib.import_module(module_str)

        if subclass_from:
            subclasses = [
                cls
                for _, cls in inspect.getmembers(module, inspect.isclass)
                if subclass_from in cls.__bases__ and cls is not subclass_from
            ]
            if not subclasses:
                raise ImportError(
                    f"No direct subclass of '{subclass_from.__name__}' found in '{module_str}'."
                )
            return subclasses[0]

        if class_name is None:
            _, class_name = module_str.rsplit(".", 1)

        if not hasattr(module, class_name):
            raise ImportError(f"Class '{class_name}' not found in '{module_str}'.")

        imported_class = getattr(module, class_name)
        if not inspect.isclass(imported_class):
            raise ImportError(f"'{class_name}' in '{module_str}' is not a valid class.")

        return imported_class

    except Exception as e:
        raise ImportError(f"Failed to import class from '{module_str}': {e}") from e


def get_project_root() -> Path:
    current_path = Path.cwd()
    if (current_path / "pyproject.toml").exists():
        return current_path
    for parent in current_path.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return current_path
