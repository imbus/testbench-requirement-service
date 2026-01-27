"""Configuration wizard helper functions for CLI."""

# ruff: noqa
import base64
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

try:
    import javaproperties  # type: ignore[import-not-found]
except ImportError:
    javaproperties = None  # type: ignore[assignment]

import click
import questionary
import tomli_w
from questionary import Choice

from testbench_requirement_service.utils.auth import (
    create_credentials,
    save_credentials,
)
from testbench_requirement_service.utils.config import CONFIG_PREFIX

MAX_PORT = 65535
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
READER_CLASSES = {
    "jsonl": "testbench_requirement_service.readers.JsonlRequirementReader",
    "excel": "testbench_requirement_service.readers.ExcelRequirementReader",
    "jira": "testbench_requirement_service.readers.JiraRequirementReader",
}


def load_toml_config(config_path: Path) -> dict[str, Any]:
    """Load TOML configuration if the config file exists."""
    if not config_path.exists():
        return {}

    try:
        with config_path.open("rb") as config_file:
            return tomllib.load(config_file)
    except Exception:
        return {}


def load_properties_config(config_path: Path) -> dict[str, Any]:
    """Load .properties configuration if the config file exists."""
    if not config_path.exists() or javaproperties is None:
        return {}

    try:
        with config_path.open("r") as config_file:
            return javaproperties.load(config_file)  # type: ignore[no-any-return]
    except Exception:
        return {}


def save_toml_config(config_dict: dict, config_path: Path):
    """Save configuration to TOML configuration file."""
    try:
        with config_path.open("wb") as config_file:
            tomli_w.dump(config_dict, config_file)
    except Exception as e:
        click.echo(f"Error saving TOML config: {e}")


def save_properties_config(config_dict: dict, config_path: Path):
    """Save configuration to .properties configuration file."""
    if javaproperties:
        try:
            with config_path.open("w") as config_file:
                javaproperties.dump(config_dict, config_file)  # type: ignore[no-any-return]
        except Exception as e:
            click.echo(f"Error saving properties config: {e}")
    else:
        click.echo("⚠️  javaproperties not installed, creating as text file")
        try:
            with config_path.open("w") as f:
                for key, value in config_dict.items():
                    f.write(f"{key}={value}\n")
        except Exception as e:
            click.echo(f"Error saving properties config as text file: {e}")


def load_reader_config(config_path: Path, reader_section: str) -> dict:
    """Extract reader configuration from main config file."""
    config: dict[str, dict] = load_toml_config(config_path)
    app_config = config.get(CONFIG_PREFIX, {})
    reader_config_path = app_config.get("reader_config_path")
    if reader_config_path:
        reader_config_file = Path(reader_config_path)
        if reader_config_file.exists():
            if reader_config_file.suffix == ".toml":
                reader_config: dict[str, dict] = load_toml_config(reader_config_file)
                return reader_config.get(reader_section, {})
            elif reader_config_file.suffix == ".properties":
                return load_properties_config(reader_config_file)
        return {}
    return config.get(reader_section, {})


def backup_existing_files(config_path: Path, dotenv_path: Path) -> bool:
    """Backup existing configuration files."""
    config_exists = config_path.exists()
    dotenv_exists = dotenv_path.exists()

    if not (config_exists or dotenv_exists):
        return True

    existing_files = []
    if config_exists:
        existing_files.append(config_path)
    if dotenv_exists:
        existing_files.append(dotenv_path)

    file_names = [f.name for f in existing_files]
    click.echo(f"⚠️  Found existing configuration: {', '.join(file_names)}")
    overwrite = questionary.confirm(
        "Do you want to reconfigure? (existing files will be backed up)", default=False
    ).ask()

    if not overwrite:
        click.echo("Configuration cancelled. Existing files preserved.")
        return False

    for file_path in existing_files:
        backup_path = Path(f"{file_path}.backup")
        # If backup already exists, add timestamp
        if backup_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = Path(f"{file_path}.backup.{timestamp}")
        file_path.rename(backup_path)
        click.echo(f"✓ Backed up {file_path.name} to {backup_path.name}")
    click.echo()
    return True


def ask_for_separate_config(reader_type: str, existing_path: str | None = None) -> str | None:
    """Ask user if they want to use a separate configuration file.

    Args:
        reader_type: The type of reader (jsonl, excel, jira, custom)
        existing_path: Path to existing separate config file if any

    Returns:
        Path to separate config file, or None for inline config
    """
    if existing_path:
        click.echo(f"\nCurrent config location: {existing_path}")
        change_location = questionary.confirm(
            "Do you want to change the configuration location?", default=False
        ).ask()

        if not change_location:
            return existing_path

    use_separate = questionary.confirm(
        "Do you want to use a separate configuration file?", default=False
    ).ask()

    if not use_separate:
        return None

    # Suggest appropriate file extension
    if reader_type == "excel":
        default_path = "excel_config.properties"
    else:
        default_path = f"{reader_type}_config.toml"

    config_file_path = questionary.text(
        "Enter path for separate config file:", default=default_path
    ).ask()

    return config_file_path if config_file_path else None


def configure_jsonl_reader(config_path: Path) -> dict | None:
    """Configure JSONL reader settings matching JsonlRequirementReaderConfig."""

    existing_config = load_reader_config(config_path, "jsonl")

    click.echo("\n📄 JSONL Reader Configuration")
    click.echo("Configure required fields for JsonlRequirementReader\n")

    requirements_path = questionary.path(
        "Enter the path to your JSONL requirements directory:",
        default=str(existing_config.get("requirements_path", "requirements/jsonl")),
        validate=lambda p: not Path(p).is_file() or "Path cannot be a file",
        only_directories=True,
    ).ask()

    if requirements_path is None:
        return None

    return {"requirements_path": requirements_path}


def configure_excel_reader(config_path: Path) -> dict | None:
    """Configure Excel reader settings matching ExcelRequirementReaderConfig."""

    existing_config = load_reader_config(config_path, "excel")

    click.echo("\n📊 Excel Reader Configuration")
    click.echo("Configure required fields for ExcelRequirementReader\n")

    # Required fields
    requirements_path = questionary.path(
        "Requirements data path:",
        default=str(existing_config.get("requirementsDataPath", "requirements/excel")),
        validate=lambda p: not Path(p).is_file() or "Path cannot be a file",
        only_directories=True,
    ).ask()
    if requirements_path is None:
        return None

    column_separator = questionary.text(
        "Column separator:", default=existing_config.get("columnSeparator", ";")
    ).ask()
    if column_separator is None:
        return None

    array_value_separator = questionary.text(
        "Array value separator:", default=existing_config.get("arrayValueSeparator", ",")
    ).ask()
    if array_value_separator is None:
        return None

    baseline_extensions = questionary.text(
        "Baseline file extensions (comma-separated):",
        default=existing_config.get("baselineFileExtensions", ".tsv,.csv,.txt"),
    ).ask()
    if baseline_extensions is None:
        return None

    # Required column indices
    req_id_col = questionary.text(
        "requirement.id column index:", default=existing_config.get("requirement.id", "1")
    ).ask()
    if req_id_col is None:
        return None

    req_version_col = questionary.text(
        "requirement.version column index:", default=existing_config.get("requirement.version", "2")
    ).ask()
    if req_version_col is None:
        return None

    req_name_col = questionary.text(
        "requirement.name column index:", default=existing_config.get("requirement.name", "3")
    ).ask()
    if req_name_col is None:
        return None

    config_dict = {
        "requirementsDataPath": requirements_path,
        "columnSeparator": column_separator,
        "arrayValueSeparator": array_value_separator,
        "baselineFileExtensions": baseline_extensions,
        "requirement.id": req_id_col,
        "requirement.version": req_version_col,
        "requirement.name": req_name_col,
    }

    # Note: Optional fields like useExcelDirectly, baselinesFromSubfolders, worksheetName,
    # dateFormat, and various requirement.* fields are not prompted here.
    # Users can manually add these to their config file if needed.
    # Consider adding interactive prompts for these in a future enhancement.

    return config_dict


def configure_jira_reader(config_path: Path) -> dict | None:
    """Configure Jira reader settings matching JiraRequirementReaderConfig."""

    existing_config = load_reader_config(config_path, "jira")

    click.echo("\n🔗 Jira Reader Configuration")
    click.echo("Configure Jira connection and authentication\n")

    server_url = questionary.text(
        "Jira server URL:",
        default=existing_config.get("server_url", "https://your-company.atlassian.net"),
    ).ask()
    if server_url is None:
        return None

    auth_type = questionary.select(
        "Authentication type:",
        choices=[
            Choice("Basic (username + API token)", "basic"),
            Choice("Token (Personal Access Token)", "token"),
            Choice("OAuth", "oauth"),
        ],
        default=existing_config.get("auth_type", "basic"),
    ).ask()
    if auth_type is None:
        return None

    config_dict = {"server_url": server_url, "auth_type": auth_type}

    # Auth-specific configuration
    if auth_type == "basic":
        username = questionary.text(
            "Jira username/email:",
            default=existing_config.get("username") or os.getenv("JIRA_USERNAME") or "",
        ).ask()
        if username is None:
            return None

        api_token = questionary.password("Jira API token:").ask()
        if api_token is None:
            return None

        config_dict.update({"username": username, "api_token": api_token})

    elif auth_type == "token":
        token = questionary.password("Personal Access Token:").ask()
        if token is None:
            return None

        config_dict.update({"token": token})

    elif auth_type == "oauth":
        click.echo("OAuth requires multiple credentials...")
        access_token = questionary.password("Access token:").ask()
        if access_token is None:
            return None

        access_token_secret = questionary.password("Access token secret:").ask()
        if access_token_secret is None:
            return None

        consumer_key = questionary.text("Consumer key:").ask()
        if consumer_key is None:
            return None

        key_cert = questionary.text("Private key file path:").ask()
        if key_cert is None:
            return None

        config_dict.update(
            {
                "access_token": access_token,
                "access_token_secret": access_token_secret,
                "consumer_key": consumer_key,
                "key_cert": key_cert,
            }
        )

    # Note: Optional Jira fields like baseline_field, project_key, jql_query, etc.
    # are not prompted here. Users can manually add these to their config file if needed.
    # Consider adding interactive prompts for these in a future enhancement.

    return config_dict


def configure_custom_reader() -> tuple[str | None, dict | None]:
    """Configure custom reader settings.

    Returns:
        Tuple of (reader_class, reader_config) or (None, None) if cancelled
    """
    click.echo("\n⚙️  Custom Reader Configuration")
    click.echo("Configure your custom requirement reader\n")

    reader_class = questionary.text(
        "Enter the full module path to your custom reader class:",
        default="custom_reader.CustomRequirementReader",
    ).ask()

    if reader_class is None:
        return None, None

    # Return empty config - user can configure manually or through other means
    reader_config: dict = {}
    return reader_class, reader_config


def configure_server_settings(
    existing_host: str | None = None, existing_port: int | None = None
) -> tuple[str | None, int | None]:
    """Configure service host and port.

    Args:
        existing_host: Current host value to show as default
        existing_port: Current port value to show as default

    Returns:
        Tuple of (host, port) or (None, None) if cancelled
    """
    host = questionary.text("Service host:", default=existing_host or DEFAULT_HOST).ask()
    port_str = questionary.text(
        "Service port:", default=str(existing_port or DEFAULT_PORT), validate=validate_port
    ).ask()

    if host is None or port_str is None:
        return None, None

    port = int(port_str)

    return host, port


def setup_authentication(
    existing_username: str | None = None,
    prompt_for_password: bool = True,
) -> tuple[str | None, str | None]:
    """Configure service credentials.

    Args:
        existing_username: Current username to show as default
        prompt_for_password: Whether to prompt for password (False when password provided via CLI)

    Returns:
        Tuple of (username, password) or (None, None) if cancelled
    """
    username = questionary.text("Enter username:", default=existing_username or "admin").ask()

    if username is None:
        return None, None

    if not prompt_for_password:
        return username, None

    while True:
        password = questionary.password("Enter password:").ask()
        if password is None:
            return None, None

        password_confirm = questionary.password("Confirm password:").ask()
        if password_confirm is None:
            return None, None

        if password == password_confirm:
            return username, password

        click.echo("❌ Passwords do not match. Please try again.\n")


def is_sensitive_config_key(key: str) -> bool:
    """Check if a configuration key contains sensitive data.

    Args:
        key: The configuration key to check

    Returns:
        True if the key is sensitive and should be masked
    """
    sensitive_keys = {
        "password",
        "password_hash",
        "salt",
        "api_token",
        "token",
        "access_token",
        "access_token_secret",
        "consumer_key",
        "key_cert",
        "jira_api_token",
        "jira_bearer_token",
        "jira_access_token",
        "jira_access_token_secret",
        "jira_key_cert",
    }
    key_lower = key.lower()
    return any(sensitive in key_lower for sensitive in sensitive_keys)


def show_main_menu(config_path: Path) -> str | None:
    """Show main menu and return selected mode.

    Args:
        config_path: Path to the config file

    Returns:
        Selected mode or None if cancelled
    """
    click.echo("What would you like to do?\n")

    choices = [Choice("🚀 Full setup (first-time configuration)", "full")]

    if config_path.exists():
        choices.append(Choice("🌐 Update service settings", "service"))
        choices.append(Choice("🔐 Update service credentials", "credentials"))
        choices.append(Choice("📚 Update reader configuration", "reader"))
        choices.append(Choice("👁️  View current configuration", "view"))

    choices.append(Choice("❌ Quit", "quit"))

    mode: str | None = questionary.select("Choose an option:", choices=choices).ask()

    return mode


def view_current_config(config_path: Path):
    """Display current configuration."""

    config: dict[str, Any] = {}
    reader_config_path: str | None = None

    if config_path.exists():
        config = load_toml_config(config_path)
        app_config: dict = config.get(CONFIG_PREFIX, {})
        click.echo(f"⚙️  Service Configuration ({config_path.name})")
        click.echo("─" * 50)
        click.echo(f"[{CONFIG_PREFIX}]")
        for key, value in app_config.items():
            if is_sensitive_config_key(key):
                click.echo(f"{key}={'*' * 10}")
            else:
                click.echo(f"{key}={value}")
        reader_config_path = app_config.get("reader_config_path")
    else:
        click.echo(f"❌ No {config_path.name} found")

    click.echo()

    # Check reader config - either in main config or separate file
    if reader_config_path and Path(reader_config_path).exists():
        # Separate reader config file (e.g., Excel .properties)
        click.echo(f"⚙️  Reader Configuration ({reader_config_path})")
        click.echo("─" * 50)

        if reader_config_path.endswith(".toml"):
            reader_config = load_toml_config(Path(reader_config_path))
            for section, values in reader_config.items():
                click.echo(f"[{section}]")
                if isinstance(values, dict):
                    for key, value in values.items():
                        if is_sensitive_config_key(key):
                            click.echo(f"{key}={'*' * 10}")
                        else:
                            click.echo(f"{key}={value}")

        elif reader_config_path.endswith(".properties"):
            with Path(reader_config_path).open() as f:
                for line in f:
                    line = line.rstrip()
                    if line:
                        if "=" in line and not line.startswith("#"):
                            key, value = line.split("=", 1)
                            if is_sensitive_config_key(key):
                                click.echo(f"{key}={'*' * 10}")
                            else:
                                click.echo(line)
                        else:
                            click.echo(line)
    elif reader_config_path:
        click.echo(f"❌ Reader config file not found: {reader_config_path}")
    elif config:
        # Reader config is inline in main config file
        reader_sections = [key for key in config.keys() if key not in [CONFIG_PREFIX]]
        if reader_sections:
            click.echo(f"⚙️  Reader Configuration (inline in {config_path.name})")
            click.echo("─" * 50)
            for section in reader_sections:
                click.echo(f"[{section}]")
                values = config[section]
                if isinstance(values, dict):
                    for key, value in values.items():
                        if is_sensitive_config_key(key):
                            click.echo(f"{key}={'*' * 10}")
                        else:
                            click.echo(f"{key}={value}")

    click.echo()

    dotenv_path = Path(".env")
    if dotenv_path.exists():
        click.echo("⚙️  Environment Variables (.env)")
        click.echo("─" * 50)
        with dotenv_path.open() as f:
            for line in f:
                line = line.rstrip()
                if line and not line.startswith("#"):
                    if "=" in line:
                        key, value = line.split("=", 1)
                        if is_sensitive_config_key(key):
                            click.echo(f"{key}={'*' * 10}")
                        else:
                            click.echo(line)
                    else:
                        click.echo(line)
    else:
        click.echo(f"❌ No {dotenv_path.name} file found")

    click.echo()


def update_config_toml(
    config_path: Path,
    app_config: dict,
    reader_section: str | None = None,
    reader_config: dict | None = None,
):
    """Update specific fields in config file while preserving others.

    Args:
        config_path: Path to the main config file
        app_config: Dictionary of fields to update in the main app config section
        reader_section: Optional reader section name (e.g., 'jsonl', 'jira')
        reader_config: Optional reader configuration to save
    """
    config = load_toml_config(config_path)

    if CONFIG_PREFIX not in config:
        config[CONFIG_PREFIX] = {}

    config[CONFIG_PREFIX].update(app_config)

    # Remove reader_config_path if explicitly set to None
    if "reader_config_path" in app_config and app_config["reader_config_path"] is None:
        config[CONFIG_PREFIX].pop("reader_config_path", None)

    # Handle reader config based on whether reader_config_path is set
    if reader_section and reader_config:
        reader_config_path = config[CONFIG_PREFIX].get("reader_config_path")
        if reader_config_path:
            reader_config_file = Path(reader_config_path)
            if reader_config_file.suffix == ".toml":
                existing_reader_config = load_toml_config(reader_config_file)
                existing_reader_config[reader_section] = reader_config
                save_toml_config(existing_reader_config, reader_config_file)
                click.echo(f"✓ Updated {reader_config_path}")
            elif reader_config_file.suffix == ".properties":
                save_properties_config(reader_config, reader_config_file)
                click.echo(f"✓ Updated {reader_config_path}")
        else:
            config[reader_section] = reader_config

    save_toml_config(config, config_path)
    click.echo(f"✓ Updated {config_path.name}")


def configure_reader_only(config_path: Path):
    """Configure only the reader settings."""
    click.echo("\n📚 Reader Configuration\n")

    config = load_toml_config(config_path)
    app_config: dict[str, str] = config.get(CONFIG_PREFIX, {})

    # Check existing reader type
    existing_reader_class = app_config.get("reader_class", "")
    existing_reader = existing_reader_class.split(".")[-1]
    if existing_reader:
        click.echo(f"Current reader: {existing_reader}\n")

    # Ask if user wants to change reader type
    change_reader_type = False
    reader_choice = None

    if existing_reader_class:
        change_reader_type = questionary.confirm(
            "Do you want to change the reader type?", default=False
        ).ask()

        if change_reader_type is None:
            click.echo("\nConfiguration cancelled.")
            return

        if not change_reader_type:
            # Determine reader choice from existing reader to update its config
            if "JsonlRequirementReader" in existing_reader_class:
                reader_choice = "jsonl"
            elif "ExcelRequirementReader" in existing_reader_class:
                reader_choice = "excel"
            elif "JiraRequirementReader" in existing_reader_class:
                reader_choice = "jira"
            else:
                reader_choice = "custom"
        else:
            # Ask for reader type if changing reader type
            reader_choice = None

    # Ask for reader type if changing or no existing reader
    if reader_choice is None:
        click.echo()
        reader_choice = questionary.select(
            "Select reader type:",
            choices=[
                Choice("📄 JSONL Files", "jsonl"),
                Choice("📊 Excel/CSV Files", "excel"),
                Choice("🔗 Jira", "jira"),
                Choice("⚙️  Custom Reader", "custom"),
            ],
        ).ask()

        if reader_choice is None:
            click.echo("\nConfiguration cancelled.")
            return

    reader_config = None
    custom_reader_class = None

    if reader_choice == "jsonl":
        reader_config = configure_jsonl_reader(config_path)
    elif reader_choice == "excel":
        reader_config = configure_excel_reader(config_path)
    elif reader_choice == "jira":
        reader_config = configure_jira_reader(config_path)
    elif reader_choice == "custom":
        custom_reader_class, reader_config = configure_custom_reader()
        if custom_reader_class is None:
            click.echo("\nConfiguration cancelled.")
            return

    if reader_config is None:
        click.echo("\nConfiguration cancelled.")
        return

    click.echo()

    # Prepare updates
    if reader_choice == "custom":
        reader_class = custom_reader_class or ""
    else:
        reader_class = READER_CLASSES.get(reader_choice, "")

    updates: dict = {"reader_class": reader_class}

    # Ask user about separate config file
    existing_reader_config_path = app_config.get("reader_config_path")
    new_reader_config_path = ask_for_separate_config(reader_choice, existing_reader_config_path)

    # Always set reader_config_path explicitly (either to a path or None for inline)
    if new_reader_config_path:
        updates["reader_config_path"] = new_reader_config_path
    else:
        updates["reader_config_path"] = None

    update_config_toml(
        config_path=config_path,
        app_config=updates,
        reader_section=reader_choice,
        reader_config=reader_config,
    )

    # Note: Jira credentials (API tokens, OAuth secrets) are currently stored in the
    # config file. For better security, consider moving them to environment variables
    # or a secrets management system in a future enhancement.
    # This would require updates to the JiraRequirementReader initialization.

    click.echo("\n✅ Reader configuration updated successfully!")


def validate_port(port_str: str) -> bool | str:
    """Validate port number input."""
    try:
        port = int(port_str.strip())
        if 1 <= port <= 65535:
            return True
        return "Port must be between 1 and 65535"
    except ValueError:
        return "Enter a valid port number (1-65535)"


def configure_service_only(config_path: Path):
    """Configure only service settings (host and port)."""
    click.echo("\n🌐 Service Configuration\n")

    # Load existing config
    config = load_toml_config(config_path)
    app_config = config.get(CONFIG_PREFIX, {})
    existing_host = app_config.get("host")
    existing_port = app_config.get("port")

    if existing_host or existing_port:
        click.echo(f"Current: {existing_host or DEFAULT_HOST}:{existing_port or DEFAULT_PORT}\n")

    host, port = configure_server_settings(existing_host, existing_port)
    if host is None or port is None:
        click.echo("\nConfiguration cancelled.")
        return

    click.echo()

    update_config_toml(config_path, app_config={"host": host, "port": port})

    click.echo("\n✅ Service configuration updated successfully!")


def configure_credentials_only(
    config_path: Path, username: str | None = None, password: str | None = None
):
    """Configure only service credentials.

    Args:
        config_path: Path to the config file
        username: Optional username (prompts if not provided)
        password: Optional password (prompts if not provided)
    """
    click.echo("\n🔐 Service Credentials Configuration\n")

    # If both provided via CLI, just save them
    if username and password:
        password_hash, salt = create_credentials(username, password)
        save_credentials(password_hash, salt, config_path)
        click.echo("\n✅ Service credentials updated successfully!")
        return

    # Otherwise collect credentials
    collected_username, collected_password = setup_authentication(
        existing_username=username, prompt_for_password=(password is None)
    )

    if collected_username is None:
        click.echo("\nConfiguration cancelled.")
        return

    # Use collected password or the one provided via CLI
    final_password = collected_password if collected_password else password

    if final_password is None:
        click.echo("\nConfiguration cancelled.")
        return

    password_hash, salt = create_credentials(collected_username, final_password)
    save_credentials(password_hash, salt, config_path)
    click.echo("\n✅ Service credentials updated successfully!")


def run_full_wizard(config_path: Path):
    """Run the complete configuration wizard.

    Args:
        config_path: Path to the config file to create/update
    """
    click.echo("This wizard will help you configure the TestBench Requirement Service.")
    click.echo("Press Ctrl+C at any time to cancel.\n")

    dotenv_path = Path(".env")

    # Check and backup existing files
    if not backup_existing_files(config_path, dotenv_path=dotenv_path):
        return

    # Step 1: Service settings
    click.echo("🌐 Step 1: Service Configuration\n")
    configure_service = questionary.confirm(
        f"Do you want to configure custom host/port? (default: {DEFAULT_HOST}:{DEFAULT_PORT})",
        default=False,
    ).ask()

    host, port = None, None
    if configure_service:
        host, port = configure_server_settings()
        if host is None or port is None:
            click.echo("\nConfiguration cancelled.")
            return

    # Step 2: Authentication
    click.echo("\n🔐 Step 2: Service Credentials Setup\n")
    click.echo("The service requires credentials for API access.\n")

    setup_auth = questionary.confirm(
        "Do you want to set up service credentials now?", default=True
    ).ask()

    if not setup_auth:
        click.echo("\nConfiguration cancelled. Service requires credentials.")
        return

    username, password = setup_authentication()

    if username is None or password is None:
        click.echo("\nConfiguration cancelled.")
        return

    # Step 3: Select requirement reader
    click.echo("\n📚 Step 3: Select Requirement Source\n")

    reader_choice = questionary.select(
        "Where are your requirements stored?",
        choices=[
            questionary.Choice("📄 JSONL Files (lightweight, file-based storage)", "jsonl"),
            questionary.Choice("📊 Excel/CSV Files (spreadsheet-based storage)", "excel"),
            questionary.Choice("🔗 Jira (connect to Atlassian Jira)", "jira"),
            questionary.Choice("⚙️  Custom Reader (your own implementation)", "custom"),
        ],
    ).ask()

    if reader_choice is None:
        click.echo("\nConfiguration cancelled.")
        return

    # Step 4: Configure reader-specific settings
    click.echo(f"\n📝 Step 4: Configure {reader_choice.upper()} Reader\n")

    reader_config = None
    reader_section = None

    custom_reader_class = None
    if reader_choice == "jsonl":
        reader_section = "jsonl"
        reader_config = configure_jsonl_reader(config_path)
    elif reader_choice == "excel":
        reader_section = "excel"
        reader_config = configure_excel_reader(config_path)
    elif reader_choice == "jira":
        reader_section = "jira"
        reader_config = configure_jira_reader(config_path)
    else:
        reader_section = "custom"
        custom_reader_class, reader_config = configure_custom_reader()
        if custom_reader_class is None:
            click.echo("\nConfiguration cancelled.")
            return

    if reader_config is None:
        click.echo("\nConfiguration cancelled.")
        return

    if reader_choice == "custom":
        reader_class_path = custom_reader_class or ""
    else:
        reader_class_path = READER_CLASSES.get(reader_choice, "")

    reader_class = reader_class_path.split(".")[-1] if reader_class_path else ""

    # Ask about separate config file
    click.echo()
    reader_config_path = ask_for_separate_config(reader_choice)

    # Step 5: Preview
    click.echo("\n📋 Configuration Summary\n")
    click.echo("─" * 60)
    click.echo(f"Reader Type:          {reader_choice.upper()}")
    click.echo(f"Reader Class:         {reader_class}")
    if reader_config_path:
        click.echo(f"Config Location:      {reader_config_path} (separate file)")
    else:
        click.echo(f"Config Location:      Inline in {config_path.name}")
    if host:
        click.echo(f"Service Host:         {host}")
    if port:
        click.echo(f"Service Port:         {port}")
    if username:
        click.echo(f"Username:             {username}")
        click.echo(f"Password:             {'*' * len(password)}")
    click.echo("─" * 60)

    click.echo("\nFiles to be created:")
    click.echo(f"  • {config_path.name:20s} (application configuration)")
    if reader_config_path:
        click.echo(f"  • {reader_config_path:20s} (reader configuration)")
    click.echo()

    confirm = questionary.confirm("Create configuration files?", default=True).ask()

    if not confirm:
        click.echo("\nConfiguration cancelled.")
        return

    # Step 6: Generate files
    click.echo("\n⚙️  Generating configuration files...\n")

    # Build config dictionary
    config_dict: dict[str, dict] = {CONFIG_PREFIX: {"reader_class": reader_class_path}}

    # Set reader_config_path if user chose separate file
    if reader_config_path:
        config_dict[CONFIG_PREFIX]["reader_config_path"] = reader_config_path

    # Save reader config
    if reader_section and reader_config:
        if reader_config_path:
            # Save to separate file
            separate_config_file = Path(reader_config_path)
            if separate_config_file.suffix == ".toml":
                save_toml_config({reader_section: reader_config}, separate_config_file)
                click.echo(f"✓ Created {reader_config_path}")
            elif separate_config_file.suffix == ".properties":
                save_properties_config(reader_config, separate_config_file)
                click.echo(f"✓ Created {reader_config_path}")
        else:
            # Add reader config inline in main config file
            config_dict[reader_section] = reader_config

    # Add optional service settings
    if host:
        config_dict[CONFIG_PREFIX]["host"] = host
    if port:
        config_dict[CONFIG_PREFIX]["port"] = port

    # Add credentials
    if username and password:
        password_hash, salt = create_credentials(username, password)
        config_dict[CONFIG_PREFIX]["password_hash"] = password_hash
        config_dict[CONFIG_PREFIX]["salt"] = base64.b64encode(salt).decode()

    # Write config.toml
    save_toml_config(config_dict, config_path)
    click.echo(f"✓ Created {config_path.name}")

    # Success message
    click.echo("\n" + "═" * 60)
    click.echo("✅ Configuration completed successfully!")
    click.echo("═" * 60)
    click.echo("\nNext steps:")
    click.echo("  1. Review the generated configuration files")
    click.echo("  2. Start the service with: testbench-requirement-service start")
    api_host = host or DEFAULT_HOST
    api_port = port or DEFAULT_PORT
    click.echo(f"  3. Access the API documentation at: http://{api_host}:{api_port}/docs\n")
