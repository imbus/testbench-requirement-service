import argparse
import sys
from pathlib import Path

import tomli_w


def parse_properties(file_path: Path):
    """Parses a .properties file into a flat dictionary, handling lines cleanly."""
    properties = {}
    try:
        with file_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()  # noqa: PLW2901
                # Skip comments and empty lines
                if not line or line.startswith(("#", "!")):
                    continue

                # Split by the first '='
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    properties[key] = val
    except FileNotFoundError:
        print(f"Error: The properties file '{file_path}' was not found.")
        sys.exit(1)
    return properties


def convert_val(val):
    """Helper to convert string values to Python types (int, float, bool)."""
    if val.lower() == "true":
        return True
    if val.lower() == "false":
        return False
    # Try converting to Integer
    try:
        return int(val)
    except ValueError:
        pass
    # Try converting to Float
    try:
        return float(val)
    except ValueError:
        pass
    return val


def properties_to_toml(
    properties_file: Path, toml_output_file: Path, include_base_template: bool = False
):
    """
    Converts properties to TOML.
    If include_base_template is True, appends the boilerplate infrastructural sections.
    """
    props = parse_properties(properties_file)

    # Create the core configuration dictionary dynamically from properties
    reader_config = {}
    for key, raw_val in props.items():
        reader_config[key] = convert_val(raw_val)

    # Build final dictionary structure based on template preference
    if include_base_template:
        toml_dict = {
            "testbench-requirement-service": {
                "reader_class": "testbench_requirement_service.readers.ExcelRequirementReader",
                "host": "127.0.0.1",
                "port": 8020,
                "debug": False,
                "password_hash": "a3d0339584abd7307e250b319d1126d967c2890e677a7b9b466cca08031c6be6",
                "salt": "fY9qE8wBo7VRRNJoDAy7qg==",
            },
            "testbench-requirement-service.reader_config": reader_config,
            "testbench-requirement-service.logging.console": {
                "log_level": "INFO",
                "log_format": "%(asctime)s %(levelname)8s: %(message)s",
            },
            "testbench-requirement-service.logging.file": {
                "log_level": "INFO",
                "log_format": "%(asctime)s - %(levelname)8s - %(name)s - %(message)s",
                "file_path": "testbench-requirement-service.log",
            },
            "testbench-requirement-service.server": {
                "single_process": True,
                "keep_alive_timeout": 5,
            },
            "testbench-requirement-service.server.run_kwargs": {},
        }
    else:
        # Isolated output: Only builds the parsed section
        defaults = {
            "bufferMaxAgeMinutes": 1440.0,
            "bufferMaxSizeMiB": 1024.0,
            "bufferCleanupIntervalMinutes": 1.0,
        }
        for k, v in defaults.items():
            if k not in reader_config:
                reader_config[k] = v
        toml_dict = {"testbench-requirement-service.reader_config": reader_config}

    # Write out using tomli_w to preserve quoted dotted keys
    with toml_output_file.open("wb") as f:
        tomli_w.dump(toml_dict, f)

    print(f"Successfully converted: {properties_file} -> {toml_output_file}")
    print(f"Base template structure included: {include_base_template}")


if __name__ == "__main__":
    # Setting up command line argument parsing
    parser = argparse.ArgumentParser(
        description="Convert an imbus TestBench .properties file into a TOML configuration file."
    )

    parser.add_argument(
        "input_file",
        nargs="?",
        default="genericexcel.properties",
        help="Path to the input .properties file (default: genericexcel.properties)",
    )
    parser.add_argument(
        "output_file",
        nargs="?",
        default="config2.toml",
        help="Path to the output .toml file (default: config.toml)",
    )
    parser.add_argument(
        "-f",
        "--full",
        action="store_true",
        help="Include the full base infrastructure template (logging, server settings, etc.)",
    )

    args = parser.parse_args()

    properties_to_toml(
        Path(args.input_file), Path(args.output_file), include_base_template=args.full
    )
