import re
import sys
import tomli_w  # Requires: pip install tomli-w


def parse_properties(file_path):
    """Parses a .properties file into a flat dictionary, handling escaped backslashes."""
    properties = {}
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#") or line.startswith("!"):
                continue

            # Split by the first '='
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()

                # Clean up Java properties path/escape artifacts if necessary
                # (un-escaping standard characters)
                properties[key] = val
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
    # Return string if no matches, retaining single backslashes safely
    return val


def properties_to_toml(properties_file, toml_output_file):
    props = parse_properties(properties_file)

    # Initialize the base template structure
    toml_dict = {
        "testbench-requirement-service": {
            "reader_class": "testbench_requirement_service.readers.ExcelRequirementReader",
            "host": "127.0.0.1",
            "port": 8020,
            "debug": False,
            "password_hash": "a3d0339584abd7307e250b319d1126d967c2890e677a7b9b466cca08031c6be6",
            "salt": "fY9qE8wBo7VRRNJoDAy7qg==",
        },
        "testbench-requirement-service.reader_config": {},
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

    reader_config = toml_dict["testbench-requirement-service.reader_config"]

    # Keys to process from properties
    for key, raw_val in props.items():
        converted_val = convert_val(raw_val)

        # Map directly to reader_config
        reader_config[key] = converted_val

    # Inject default service buffer values if missing from the property file
    defaults = {
        "bufferMaxAgeMinutes": 1440.0,
        "bufferMaxSizeMiB": 1024.0,
        "bufferCleanupIntervalMinutes": 1.0,
    }
    for k, v in defaults.items():
        if k not in reader_config:
            reader_config[k] = v

    # Write out using tomli_w to ensure correct quoting of dotted keys
    with open(toml_output_file, "wb") as f:
        tomli_w.dump(toml_dict, f)

    print(f"Successfully converted {properties_file} -> {toml_output_file}")


if __name__ == "__main__":
    # Example usage: python convert.py genericexcel.properties config.toml
    input_prop = sys.argv[1] if len(sys.argv) > 1 else "genericexcel.properties"
    output_toml = sys.argv[2] if len(sys.argv) > 2 else "config1.toml"

    properties_to_toml(input_prop, output_toml)
