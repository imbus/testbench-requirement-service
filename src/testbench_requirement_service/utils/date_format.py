import warnings
from datetime import datetime, timezone

import pandas as pd


def java_to_python_date_format(java_format: str) -> str:
    """
    Converts a Java SimpleDateFormat string to a Python strftime format string.
    """
    # Mapping of Java SimpleDateFormat patterns to Python strftime patterns
    mapping = {
        "yyyy": "%Y",  # Year (4 digits)
        "yy": "%y",  # Year (2 digits)
        "MM": "%m",  # Month (2 digits)
        "dd": "%d",  # Day of the month (2 digits)
        "HH": "%H",  # Hour (24-hour clock)
        "hh": "%I",  # Hour (12-hour clock)
        "mm": "%M",  # Minutes
        "ss": "%S",  # Seconds
        "a": "%p",  # AM/PM marker
        "EEE": "%a",  # Day name (short)
        "EEEE": "%A",  # Day name (full)
        "Z": "%z",  # Time zone offset
        "'T'": "'T'",  # Literal "T" (e.g., in ISO 8601 formats)
        "''": "'",  # Escaped single quote
    }

    # Replace Java patterns with Python patterns
    python_format = java_format
    for java_pattern, python_pattern in mapping.items():
        python_format = python_format.replace(java_pattern, python_pattern)

    return python_format


def parse_date_string(date_string: str, java_date_format: str) -> datetime:
    """
    Parses a date string using a converted Java date format. If the format is invalid,
    falls back to guessing the format with pandas.to_datetime and displays a warning.

    Args:
        date_string (str): The date string to parse.
        java_date_format (str): The Java SimpleDateFormat string to convert.

    Returns:
        datetime: The parsed date as a python datetime object
    """
    python_format = java_to_python_date_format(java_date_format)

    try:
        return datetime.strptime(date_string, python_format).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        warnings.warn(
            f"Invalid value for 'dateFormat' in reader config: {java_date_format}. "
            f"Falling back to guessing the date format.",
            UserWarning,
            stacklevel=2,
        )
        return pd.to_datetime(date_string, errors="raise", utc=True).to_pydatetime()
