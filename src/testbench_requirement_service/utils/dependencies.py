import importlib.util


def check_excel_dependencies():
    """Checks if Excel dependencies are installed, raises an ImportError if missing."""
    required_packages = ["pandas", "openpyxl", "xlrd", "javaproperties"]
    missing = [pkg for pkg in required_packages if importlib.util.find_spec(pkg) is None]
    if missing:
        raise ImportError(
            "Excel functionality is required but missing.\n"
            "To enable Excel support, install the required dependencies with:\n\n"
            "    pip install testbench-requirement-service[excel]\n\n"
            f"Missing dependencies: {', '.join(missing)}"
        )
