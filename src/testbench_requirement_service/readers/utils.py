from pathlib import Path

from testbench_requirement_service.readers.FileReader import FileReader
from testbench_requirement_service.utils.helpers import (
    get_project_root,
    import_class_from_file_path,
    import_class_from_module_str,
)


def get_reader_class_from_file_path(file_path: Path) -> FileReader:
    try:
        return import_class_from_file_path(file_path, subclass_from=FileReader)  # type: ignore
    except Exception as e:
        message = f"Failed to import custom FileReader class from '{file_path}'."
        raise ImportError(message) from e


def get_reader_class_from_module_str(reader_name: str) -> FileReader:
    try:
        return import_class_from_module_str(reader_name, subclass_from=FileReader)  # type: ignore
    except Exception as e:
        message = f"Failed to import custom FileReader class from '{reader_name}'."
        raise ImportError(message) from e


def get_file_reader_from_reader_class_str(reader_class: str) -> FileReader:
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


def get_file_reader(app) -> FileReader:
    if not getattr(app.ctx, "file_reader", None):
        file_reader_config = app.config.READER_CONFIG_PATH
        file_reader_class_str = app.config.READER_CLASS
        file_reader_class = get_file_reader_from_reader_class_str(file_reader_class_str)
        file_reader = file_reader_class(file_reader_config)  # type: ignore
        if not isinstance(file_reader, FileReader):
            raise ImportError(f"{file_reader_class} is no instance of FileReader!")
        app.ctx.file_reader = file_reader
    return app.ctx.file_reader  # type: ignore
