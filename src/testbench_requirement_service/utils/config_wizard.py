"""Configuration wizard helper functions for CLI."""

from pathlib import Path
from typing import Any

import click
import questionary
from pydantic import BaseModel
from questionary import Choice

from testbench_requirement_service.models.config import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    RequirementServiceConfig,
)
from testbench_requirement_service.readers.utils import (
    get_reader_config_class,
    get_requirement_reader_from_reader_class_str,
)
from testbench_requirement_service.utils.auth import (
    create_credentials,
    save_credentials,
)
from testbench_requirement_service.utils.config import (
    CONFIG_PREFIX,
    create_config_backup_file,
    get_reader_config,
    load_service_config,
    save_reader_config,
    save_toml_config,
    update_config_files,
)
from testbench_requirement_service.utils.dependencies import check_reader_dependencies
from testbench_requirement_service.utils.wizard import prompt_model_fields

MAX_PORT = 65535
READER_CLASSES = {
    "jsonl": "testbench_requirement_service.readers.JsonlRequirementReader",
    "excel": "testbench_requirement_service.readers.ExcelRequirementReader",
    "jira": "testbench_requirement_service.readers.JiraRequirementReader",
}
SERVICE_WIZARD_SKIP_FIELDS = {
    "reader_class",
    "reader_config",
    "reader_config_path",
    "password_hash",
    "salt",
    "logging",
}


def validate_port(value: Any) -> tuple[bool, str | None]:
    try:
        port_value = int(value)
    except (TypeError, ValueError):
        return False, "Enter a valid port number"

    if 1 <= port_value <= MAX_PORT:
        return True, None
    return False, f"Port must be between 1 and {MAX_PORT}"


def backup_config_file(config_path: Path) -> bool:
    """Backup existing configuration file."""
    if not config_path.exists():
        return True

    click.echo(f"⚠️  Found existing configuration: {config_path.name}")
    overwrite = questionary.confirm(
        "Do you want to reconfigure? (existing files will be backed up)", default=False
    ).ask()

    if not overwrite:
        click.echo("Configuration cancelled. Existing files preserved.")
        return False

    backup_path = create_config_backup_file(config_path)
    click.echo(f"✓ Backed up {config_path.name} to {backup_path.name}")
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

    if reader_type == "excel":
        default_path = "excel_config.properties"
    else:
        default_path = f"{reader_type}_config.toml"

    config_file_path = questionary.text(
        "Enter path for separate config file:", default=default_path
    ).ask()

    if not config_file_path:
        return None

    config_path = Path(config_file_path)
    parent_dir = config_path.parent
    if not parent_dir.exists():
        try:
            parent_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            click.echo(f"⚠️  Warning: Cannot create directory {parent_dir}: {e}")
            click.echo("Using inline configuration instead.")
            return None

    return str(config_file_path)


def merge_with_defaults(
    config_dict: dict[str, Any],
    config_class: type[BaseModel],
    exclude_fields: set[str] | None = None,
) -> dict[str, Any]:
    """Merge user-provided config with model defaults to create complete config.

    This ensures all fields (including defaults) are written to config files,
    eliminating 'magic' values that only exist in code.

    Args:
        config_dict: User-provided configuration values
        config_class: Pydantic model class with field defaults
        exclude_fields: Optional set of field names to exclude from output

    Returns:
        Complete configuration dict with all fields (user values + defaults), TOML-serializable
    """
    config_obj = config_class.model_validate(config_dict)
    return config_obj.model_dump(
        mode="json", by_alias=True, exclude_none=True, exclude=exclude_fields
    )


def configure_reader(
    reader_type: str, reader_class: str, service_config: RequirementServiceConfig | None = None
) -> dict | None:
    """Universal reader configurator for built-in readers like JSONL, Excel, and Jira."""
    try:
        check_reader_dependencies(reader_type, raise_on_missing=True)
    except ImportError as e:
        click.echo(f"\n{e}\n")
        return None

    try:
        config_class = get_reader_config_class(reader_class)
    except (ImportError, TypeError, ValueError) as exc:
        click.echo(f"❌ Unable to load {reader_type} reader configuration: {exc}")
        return None

    if config_class is None:
        click.echo(
            f"❌ Reader '{reader_type}' does not expose a CONFIG_CLASS for guided configuration"
        )
        return None

    existing_config = {}
    if service_config is not None:
        try:
            existing_config = get_reader_config(service_config) or {}
            existing_config = config_class.model_validate(existing_config).model_dump()
        except Exception:
            pass

    reader_config = prompt_model_fields(
        config_class,
        existing_config=existing_config,
        section_label=f"{reader_type.title()} Reader Configuration",
    )

    if reader_config is None:
        return None

    return merge_with_defaults(reader_config, config_class)


def setup_authentication(
    existing_username: str | None = None,
    prompt_for_password: bool = True,
) -> tuple[str | None, str | None]:
    """Configure service credentials (username/password)."""
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
    """Check if a config key contains sensitive data (passwords, tokens, etc)."""
    sensitive_keys = {
        "password",
        "password_hash",
        "salt",
        "api_token",
        "token",
        "oauth1_access_token",
        "oauth1_access_token_secret",
        "oauth1_key_cert",
        "jira_api_token",
        "jira_bearer_token",
        "jira_oauth1_access_token",
        "jira_oauth1_access_token_secret",
        "jira_oauth1_key_cert",
    }
    key_lower = key.lower()
    return any(sensitive in key_lower for sensitive in sensitive_keys)


def print_nested_config(config: dict[str, Any], indent: int = 0, parent_key: str = "") -> None:
    """Recursively print nested configuration dictionaries in TOML-like format.

    Args:
        config: Dictionary to print
        indent: Current indentation level
        parent_key: Parent key path for nested sections
    """
    for key, value in config.items():
        if isinstance(value, dict):
            section_path = f"{parent_key}.{key}" if parent_key else key
            click.echo(f"\n[{CONFIG_PREFIX}.{section_path}]")
            print_nested_config(value, indent, section_path)
        elif is_sensitive_config_key(key):
            click.echo(f"{key} = {'*' * 10}")
        else:
            click.echo(f"{key} = {value}")


def show_main_menu(config_path: Path) -> str | None:
    """Show main menu and return selected mode."""
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


def view_service_config(config_path: Path) -> RequirementServiceConfig | None:
    """Display service configuration and return service config."""
    if not config_path.exists():
        click.echo(f"❌ No {config_path.name} found")
        return None

    service_config = load_service_config(config_path)

    click.echo(f"⚙️  Service Configuration ({config_path.name})")
    click.echo("─" * 50)
    click.echo(f"[{CONFIG_PREFIX}]")

    for key, value in service_config.model_dump(mode="json", exclude_none=True).items():
        if key == "reader_config":
            continue
        if is_sensitive_config_key(key):
            click.echo(f"{key} = {'*' * 10}")
        elif isinstance(value, dict):
            print_nested_config(value, indent=0, parent_key=key)
        else:
            click.echo(f"{key} = {value}")

    return service_config


def view_reader_config(service_config: RequirementServiceConfig):
    """Display reader configuration (separate file or inline)."""

    reader_config_path = service_config.reader_config_path
    if reader_config_path and Path(reader_config_path).exists():
        click.echo(f"⚙️  Reader Configuration ({reader_config_path})")
        click.echo("─" * 50)
    elif reader_config_path:
        click.echo(f"❌ Reader config file not found: {reader_config_path}")
    else:
        click.echo("⚙️  Reader Configuration")
        click.echo("─" * 50)
        click.echo(f"[{CONFIG_PREFIX}.reader_config]")

    reader_config = get_reader_config(service_config)
    if not reader_config:
        click.echo("❌ No reader config found")
        return

    for key, value in reader_config.items():
        click.echo(f"{key} = {'*' * 10}" if is_sensitive_config_key(key) else f"{key} = {value}")


def view_env_config(dotenv_path: Path = Path(".env")) -> None:
    """Display .env file contents.

    Args:
        dotenv_path: Path to the .env file (defaults to '.env' in current directory)
    """
    if not dotenv_path.exists():
        click.echo(f"❌ No {dotenv_path.name} file found")
        return

    click.echo(f"⚙️  Environment Variables ({dotenv_path.name})")
    click.echo("─" * 50)

    try:
        with dotenv_path.open() as f:
            for line in f:
                line_stripped = line.rstrip()
                if line_stripped and not line_stripped.startswith("#") and "=" in line_stripped:
                    key = line_stripped.split("=", 1)[0]
                    if is_sensitive_config_key(key):
                        click.echo(f"{key}={'*' * 10}")
                    else:
                        click.echo(line_stripped)
    except (OSError, UnicodeDecodeError) as e:
        click.echo(f"❌ Error reading {dotenv_path.name}: {e}")


def view_current_config(config_path: Path):
    """Display current configuration (service, reader, env)."""
    service_config = view_service_config(config_path)
    click.echo()
    if service_config is not None:
        view_reader_config(service_config)
    click.echo()
    view_env_config()
    click.echo()


def get_reader_class(reader_type: str) -> str | None:
    if reader_type == "custom":
        reader_class: str | None = questionary.text(
            "Enter the full class path to your custom reader class:",
            default="CustomRequirementReader.py",
        ).ask()
        if reader_class is None:
            return None
        try:
            get_requirement_reader_from_reader_class_str(reader_class)
            return reader_class
        except Exception as e:
            click.echo(f"❌ Error: Could not load custom reader class: {e}")
            return None
    return READER_CLASSES.get(reader_type)


def get_reader_type(reader: str) -> str | None:
    """Infer reader type from class name."""
    for reader_type, reader_class in READER_CLASSES.items():
        if reader in reader_class or reader_type in reader.lower():
            return reader_type

    return None


def configure_reader_only(config_path: Path):
    """Configure reader settings only."""
    click.echo("\n📚 Reader Configuration\n")

    service_config = load_service_config(config_path)

    reader_class_path = service_config.reader_class
    if ".py" in reader_class_path:
        reader = Path(reader_class_path).stem
    else:
        reader = reader_class_path.split(".")[-1]
    if reader:
        click.echo(f"Current reader: {reader}\n")

    change_reader_type = questionary.confirm(
        "Do you want to change the reader type?", default=False
    ).ask()

    if change_reader_type is None:
        click.echo("\nConfiguration cancelled.")
        return

    if change_reader_type:
        click.echo()
        reader_type = questionary.select(
            "Select reader type:",
            choices=[
                Choice("📄 JSONL Files", "jsonl"),
                Choice("📊 Excel/CSV Files", "excel"),
                Choice("🔗 Jira", "jira"),
                Choice("⚙️  Custom Reader", "custom"),
            ],
        ).ask()
    else:
        reader_type = get_reader_type(reader) or "custom"

    if reader_type is None:
        click.echo("\nConfiguration cancelled.")
        return

    reader_class = get_reader_class(reader_type)
    if reader_class is None:
        click.echo("\nConfiguration cancelled.")
        return

    reader_config = configure_reader(reader_type, reader_class, service_config)
    if reader_config is None:
        click.echo("\nConfiguration cancelled.")
        return

    click.echo()

    reader_config_path = ask_for_separate_config(reader_type, service_config.reader_config_path)
    if reader_config_path:
        save_reader_config(reader_config, Path(reader_config_path))

    updates: dict[str, Any] = {
        "reader_class": reader_class,
        "reader_config_path": reader_config_path,
    }
    update_config_files(config_path, updates=updates, reader_config=reader_config)

    click.echo("\n✅ Reader configuration updated successfully!")


def configure_service_only(config_path: Path):
    """Configure service settings (host, port, debug, etc.)."""
    click.echo("\n🌐 Service Configuration\n")

    service_config = load_service_config(config_path)

    click.echo(f"Current: http://{service_config.host}:{service_config.port}\n")

    updates = prompt_model_fields(
        RequirementServiceConfig,
        existing_config=service_config.model_dump(),
        skip_fields=SERVICE_WIZARD_SKIP_FIELDS,
        field_overrides={"port": {"validate": validate_port}},
    )

    if updates is None:
        click.echo("\nConfiguration cancelled.")
        return

    click.echo()

    update_config_files(config_path, updates=updates)

    click.echo("\n✅ Service configuration updated successfully!")


def configure_credentials_only(
    config_path: Path, username: str | None = None, password: str | None = None
):
    """Configure service credentials (username/password)."""
    click.echo("\n🔐 Service Credentials Configuration\n")

    if not username or not password:
        username, collected_password = setup_authentication(
            existing_username=username, prompt_for_password=(password is None)
        )
        password = collected_password if collected_password else password
        if username is None or password is None:
            click.echo("\nConfiguration cancelled.")
            return

    password_hash, salt = create_credentials(username, password)
    save_credentials(password_hash, salt, config_path)
    click.echo("\n✅ Service credentials updated successfully!")


def run_full_wizard(config_path: Path):  # noqa: C901, PLR0912, PLR0915
    """Run the complete configuration wizard (first-time setup)."""
    click.echo("This wizard will help you configure the TestBench Requirement Service.")
    click.echo("Press Ctrl+C at any time to cancel.\n")

    service_config: dict[str, Any] = {}

    if not backup_config_file(config_path):
        return

    click.echo("🌐 Step 1: Service Configuration\n")

    service_updates = prompt_model_fields(
        RequirementServiceConfig,
        skip_fields=SERVICE_WIZARD_SKIP_FIELDS,
        field_overrides={"port": {"validate": validate_port}},
        allowed_fields={"host", "port"},
    )

    if service_updates is None:
        click.echo("\nConfiguration cancelled.")
        return

    service_config.update(service_updates)

    click.echo("\n🔐 Step 2: Service Credentials Setup\n")
    click.echo("The service requires credentials for API access.\n")

    username, password = setup_authentication()

    if username is None or password is None:
        click.echo("\nConfiguration cancelled.")
        return

    password_hash, salt = create_credentials(username, password)
    service_config["password_hash"] = password_hash
    service_config["salt"] = salt

    click.echo("\n📚 Step 3: Select Requirement Source\n")

    reader_type: str = questionary.select(
        "Where are your requirements stored?",
        choices=[
            questionary.Choice("📄 JSONL Files (lightweight, file-based storage)", "jsonl"),
            questionary.Choice("📊 Excel/CSV Files (spreadsheet-based storage)", "excel"),
            questionary.Choice("🔗 Jira (connect to Atlassian Jira)", "jira"),
            questionary.Choice("⚙️  Custom Reader (your own implementation)", "custom"),
        ],
    ).ask()

    click.echo(f"\n📝 Step 4: Configure {reader_type.capitalize()} Reader\n")

    reader_class = get_reader_class(reader_type)
    if reader_class is None:
        click.echo("\nConfiguration cancelled.")
        return

    reader_config = configure_reader(reader_type, reader_class)
    if reader_config is None:
        click.echo("\nConfiguration cancelled.")
        return

    service_config["reader_class"] = reader_class

    click.echo()

    reader_config_path = ask_for_separate_config(reader_type)

    click.echo("\n📋 Configuration Summary\n")
    click.echo("─" * 60)
    click.echo(f"Reader Type:          {reader_type.upper()}")
    click.echo(f"Reader Class:         {reader_class}")
    if reader_config_path:
        click.echo(f"Config Location:      {reader_config_path} (separate file)")
    else:
        click.echo(f"Config Location:      Inline in {config_path.name}")
    if host := service_config.get("host"):
        click.echo(f"Service Host:         {host}")
    if port := service_config.get("port"):
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

    click.echo("\n⚙️  Generating configuration files...\n")

    if reader_config_path:
        # Save to separate file
        service_config["reader_config_path"] = reader_config_path
        save_reader_config(reader_config, Path(reader_config_path))
        click.echo(f"✓ Created {reader_config_path}")
    else:
        # Add reader config inline to [testbench-requirement-service.reader_config]
        service_config["reader_config"] = reader_config

    service_config = merge_with_defaults(service_config, RequirementServiceConfig)
    config_dict: dict[str, Any] = {CONFIG_PREFIX: service_config}
    save_toml_config(config_dict, config_path)
    click.echo(f"✓ Created {config_path.name}")

    click.echo("\n" + "═" * 60)
    click.echo("✅ Configuration completed successfully!")
    click.echo("═" * 60)
    click.echo("\nNext steps:")
    click.echo("  1. Review the generated configuration files")
    click.echo("  2. Start the service with: testbench-requirement-service start")
    click.echo(
        "  3. Access the API documentation at: "
        f"http://{host or DEFAULT_HOST}:{port or DEFAULT_PORT}/docs"
    )
    click.echo()
