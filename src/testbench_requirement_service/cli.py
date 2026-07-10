import sys
from functools import partial
from pathlib import Path
from ssl import SSLContext

import click
import tomli_w
from dotenv import load_dotenv
from sanic import Sanic
from sanic.worker.loader import AppLoader

from testbench_requirement_service import __title__, __version__
from testbench_requirement_service.app import AppConfig, create_app
from testbench_requirement_service.log import logger
from testbench_requirement_service.utils.config_wizard import (
    configure_credentials_only,
    configure_reader_only,
    configure_service_only,
    run_full_wizard,
    show_main_menu,
    view_current_config,
)
from testbench_requirement_service.utils.legacy_config_converter import (
    REQUIRED_EXCEL_CONVERTER_MODULES,
    build_base_service_config,
    build_project_reader_config,
    convert_jira_conf_to_reader_config,
    get_missing_dependencies,
    load_toml,
    parse_legacy_jira_conf,
    properties_to_reader_config,
    properties_to_toml,
)

CONFIG_ROOT = "testbench-requirement-service"


def print_service_banner():
    """Print the service banner."""
    click.echo(rf"""  ______          __  ____                  __       ____  __  ___   _____                 _         
 /_  __/__  _____/ /_/ __ )___  ____  _____/ /_     / __ \/  |/  /  / ___/___  ______   __(_)_______ 
  / / / _ \/ ___/ __/ __  / _ \/ __ \/ ___/ __ \   / /_/ / /|_/ /   \__ \/ _ \/ ___/ | / / / ___/ _ \
 / / /  __(__  ) /_/ /_/ /  __/ / / / /__/ / / /  / _, _/ /  / /   ___/ /  __/ /   | |/ / / /__/  __/   version:
/_/  \___/____/\__/_____/\___/_/ /_/\___/_/ /_/  /_/ |_/_/  /_/   /____/\___/_/    |___/_/\___/\___/    {__version__} 
                                                                                                     """)  # noqa: W291, E501


def print_wizard_banner():
    """Print the configuration wizard banner."""
    click.echo("╔════════════════════════════════════════════════════════╗")
    click.echo("║  TestBench Requirement Service - Configuration Wizard  ║")
    click.echo("╚════════════════════════════════════════════════════════╝\n")


@click.group()
@click.version_option(version=__version__, prog_name=__title__, message="%(prog)s %(version)s")
@click.pass_context
def cli(ctx):
    ctx.max_content_width = 120
    load_dotenv()


@click.command()
@click.option(
    "--path",
    "config_path",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    metavar="PATH",
    default="config.toml",
    help="Path to the configuration file.",
)
def init(config_path: Path):
    """Initialize service configuration interactively."""
    print_wizard_banner()
    run_full_wizard(config_path)


@click.command()
@click.option(
    "--path",
    "config_path",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default="config.toml",
    help="Path to the app configuration file",
)
@click.option("--full", is_flag=True, help="Run full configuration wizard (skip menu)")
@click.option("--service-only", is_flag=True, help="Configure service settings only")
@click.option("--credentials-only", is_flag=True, help="Configure service credentials only")
@click.option("--reader-only", is_flag=True, help="Configure reader settings only")
@click.option("--view", is_flag=True, help="View current configuration")
def configure(  # noqa: PLR0911, PLR0913, C901
    config_path: Path,
    full: bool,
    service_only: bool,
    credentials_only: bool,
    reader_only: bool,
    view: bool,
):
    """Create or update configuration files interactively."""
    print_wizard_banner()

    # Handle command flags (direct modes)
    if service_only:
        configure_service_only(config_path)
        return

    if credentials_only:
        configure_credentials_only(config_path)
        return

    if reader_only:
        configure_reader_only(config_path)
        return

    if view:
        view_current_config(config_path)
        return

    # Show menu if no flags specified
    if not full:
        mode = show_main_menu(config_path)
        if mode is None or mode == "quit":
            click.echo("\nConfiguration cancelled.")
            return

        if mode == "service":
            configure_service_only(config_path)
            return
        if mode == "credentials":
            configure_credentials_only(config_path)
            return
        if mode == "reader":
            configure_reader_only(config_path)
            return
        if mode == "view":
            view_current_config(config_path)
            return

    run_full_wizard(config_path)


@click.command()
@click.option(
    "--config",
    "config_path",
    type=click.Path(dir_okay=False, path_type=Path),
    metavar="PATH",
    help=("Path to the app config file  [default: config.toml]"),
)
@click.option(
    "--reader-class",
    type=str,
    metavar="PATH",
    help="""Path or module string to the reader class  \b
    [default: testbench_requirement_service.readers.JsonlRequirementReader]""",
)
@click.option(
    "--reader-config",
    type=click.Path(dir_okay=False, path_type=Path),
    metavar="PATH",
    help=" Path to the reader config file  [default: reader_config.toml]",
)
@click.option(
    "--host", type=str, metavar="HOST", help="Host to run the service on  [default: 127.0.0.1]"
)
@click.option(
    "--port", type=int, metavar="PORT", help="Port to run the service on  [default: 8020]"
)
@click.option(
    "--dev",
    is_flag=True,
    default=False,
    show_default=True,
    help="Run the service in dev mode (debug + auto reload)",
)
@click.option(
    "--ssl-cert",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    metavar="PATH",
    help="Path to SSL certificate file for HTTPS",
)
@click.option(
    "--ssl-key",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    metavar="PATH",
    help="Path to SSL private key file for HTTPS",
)
@click.option(
    "--ssl-ca-cert",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    metavar="PATH",
    help="Path to CA certificate file for client verification (optional)",
)
def start(  # noqa: PLR0913
    config_path: Path | None = None,
    reader_class: str | None = None,
    reader_config: Path | None = None,
    host: str | None = None,
    port: int | None = None,
    dev: bool = False,
    ssl_cert: Path | None = None,
    ssl_key: Path | None = None,
    ssl_ca_cert: Path | None = None,
):
    """Start the TestBench Requirement Service."""
    app_name = __title__
    app_config = AppConfig(
        config_path=config_path,
        reader_class=reader_class,
        reader_config_path=reader_config,
        host=host,
        port=port,
        debug=dev,
        ssl_cert=ssl_cert,
        ssl_key=ssl_key,
        ssl_ca_cert=ssl_ca_cert,
    )

    print_service_banner()

    factory = partial(create_app, app_name, app_config)
    loader = AppLoader(factory=factory)
    try:
        app = loader.load()
    except ImportError as e:
        raise click.ClickException(str(e)) from e

    logger.info("Starting %s v%s", app_name, __version__)

    if not host:
        host = getattr(app.config, "HOST", None)
    if not port:
        port = getattr(app.config, "PORT", None)

    server_config = app_config.SERVER_CONFIG
    ssl_context = app_config.get_ssl_context()

    use_single_process = server_config.single_process
    if dev and use_single_process:
        logger.info(
            "Dev mode enabled: switching to multi-process mode to support auto-reload. "
            "Set 'server.single_process = false' explicitly to suppress this message."
        )
        use_single_process = False
    if getattr(sys, "frozen", False) and not use_single_process:
        logger.warning(
            "Auto-reload is not supported in the executable. Falling back to single-process mode."
        )
        use_single_process = True
    if isinstance(ssl_context, SSLContext) and not use_single_process:
        logger.warning(
            "mTLS (ssl_ca_cert) requires single-process mode. "
            "Ignoring 'single_process = false' and running in single-process mode."
        )
        use_single_process = True

    common_kwargs: dict = {
        "host": host,
        "port": port,
        "debug": app_config.DEBUG,
        "access_log": True,
        "ssl": ssl_context,
        **server_config.run_kwargs,
    }

    try:
        if use_single_process:
            app.run(**common_kwargs, single_process=True)
        else:
            app.prepare(**common_kwargs, dev=dev)
            Sanic.serve(primary=app, app_loader=loader)
    except Exception as e:
        raise click.ClickException(f"Server could not start: {e}") from e


@click.command()
@click.option(
    "--path",
    "config_path",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    metavar="PATH",
    default="config.toml",
    help="Path to the app config file",
)
@click.option("--username", type=str, help="Username (prompts if not provided)")
@click.option("--password", type=str, help="Password (prompts if not provided)")
def set_credentials(config_path, username, password):
    """Set credentials for the TestBench Requirement Service."""
    configure_credentials_only(config_path, username=username, password=password)


def _ensure_excel_converter_dependencies(command_name: str) -> None:
    missing = get_missing_dependencies(REQUIRED_EXCEL_CONVERTER_MODULES)
    if missing:
        deps = ", ".join(missing)
        raise click.ClickException(
            f"Missing required dependencies for '{command_name}': "
            f"{deps}.\n"
            "Install with: pip install testbench-requirement-service[excel]"
        )


def _resolve_convert_action(
    output_file: Path,
    overwrite: bool,
    add_project: bool,
) -> tuple[bool, bool]:
    if not output_file.exists() or overwrite or add_project:
        return overwrite, add_project

    choice = click.prompt(
        (f"Output file '{output_file}' already exists. Choose action"),
        type=click.Choice(["overwrite", "add-project", "cancel"], case_sensitive=False),
        default="cancel",
        show_choices=True,
    )

    if choice == "cancel":
        raise click.ClickException("Conversion cancelled.")

    return choice == "overwrite", choice == "add-project"


def _load_converted_reader_config(input_type: str, input_file: Path) -> dict[str, object]:
    if input_type == "jira":
        jira_conf = parse_legacy_jira_conf(input_file)
        return convert_jira_conf_to_reader_config(jira_conf)

    _ensure_excel_converter_dependencies("convert-config")
    return properties_to_reader_config(input_file, include_defaults=True)


def _write_overwrite_output(
    input_type: str,
    input_file: Path,
    output_file: Path,
    reader_config: dict[str, object],
) -> None:
    if input_type == "excel":
        properties_to_toml(input_file, output_file, include_base_template=True)
        return

    full_config = build_base_service_config(
        "testbench_requirement_service.readers.JiraRequirementReader",
        reader_config,
    )
    with output_file.open("wb") as file_handle:
        tomli_w.dump(full_config, file_handle)


def _append_project_config(
    output_file: Path,
    input_type: str,
    reader_config: dict[str, object],
    project_name: str | None,
) -> str:
    if not output_file.exists():
        raise click.ClickException(
            f"Output file '{output_file}' does not exist. Use --overwrite first."
        )

    project_key = project_name or click.prompt("Project key to append", type=str).strip()
    if not project_key:
        raise click.ClickException("Project key cannot be empty.")

    existing_config = load_toml(output_file)
    service_config = existing_config.setdefault(CONFIG_ROOT, {})
    if not isinstance(service_config, dict):
        raise click.ClickException(
            f"Invalid TOML structure in '{output_file}': section [{CONFIG_ROOT}] is not a table."
        )

    root_reader_config = service_config.setdefault("reader_config", {})
    if not isinstance(root_reader_config, dict):
        raise click.ClickException(
            f"Invalid TOML structure in '{output_file}': reader_config is not a table."
        )

    projects = root_reader_config.setdefault("projects", {})
    if not isinstance(projects, dict):
        raise click.ClickException(
            f"Invalid TOML structure in '{output_file}': reader_config.projects is not a table."
        )

    if project_key in projects:
        should_replace = click.confirm(
            f"Project '{project_key}' already exists in '{output_file}'. Replace it?",
            default=False,
        )
        if not should_replace:
            raise click.ClickException("Conversion cancelled.")

    projects[project_key] = build_project_reader_config(input_type, reader_config)

    with output_file.open("wb") as file_handle:
        tomli_w.dump(existing_config, file_handle)

    return project_key


def _run_convert_config(  # noqa: PLR0913
    *,
    input_type: str,
    input_file: Path,
    output_file: Path,
    overwrite: bool,
    add_project: bool,
    project_name: str | None,
) -> None:
    if overwrite and add_project:
        raise click.ClickException("Use either --overwrite or --add-project, not both.")

    overwrite, add_project = _resolve_convert_action(output_file, overwrite, add_project)

    try:
        reader_config = _load_converted_reader_config(input_type, input_file)
    except FileNotFoundError as exc:
        raise click.ClickException(f"Input file not found: {input_file}") from exc

    if add_project:
        project_key = _append_project_config(output_file, input_type, reader_config, project_name)
        click.echo(f"Successfully appended project '{project_key}' to {output_file}")
        return

    try:
        _write_overwrite_output(input_type, input_file, output_file, reader_config)
    except OSError as exc:
        raise click.ClickException(
            f"Could not write TOML output file '{output_file}': {exc}"
        ) from exc
    except ImportError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Successfully converted: {input_file} -> {output_file}")
    click.echo("Output mode: overwrite")


@click.command("convert-config")
@click.argument(
    "input_file",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
)
@click.argument(
    "output_file",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
)
@click.option(
    "--type",
    "input_type",
    type=click.Choice(["jira", "excel"], case_sensitive=False),
    default="jira",
    show_default=True,
    help="Input file type to convert.",
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="Overwrite OUTPUT_FILE with a full base TOML config.",
)
@click.option(
    "--add-project",
    is_flag=True,
    help="Append a project section to an existing TOML config.",
)
@click.option(
    "--project-name",
    type=str,
    help="Project key to use with --add-project.",
)
def convert_config_command(  # noqa: PLR0913
    input_type: str,
    input_file: Path,
    output_file: Path,
    overwrite: bool,
    add_project: bool,
    project_name: str | None,
):
    """Convert a legacy config file into TestBench Requirement Service TOML."""
    if overwrite and add_project:
        raise click.ClickException("Use either --overwrite or --add-project, not both")

    if add_project and not project_name:
        raise click.ClickException("--project-name is required when using --add-project")

    if output_file.exists() and not overwrite and not add_project:
        click.echo(f"Notice: The file '{output_file}' already exists.")
        choice = click.prompt(
            "Do you want to Overwrite it (o) or Add as a project (a)?",
            type=click.Choice(["o", "a"], case_sensitive=False),
        ).lower()
        if choice == "a":
            add_project = True
            if not project_name:
                project_name = click.prompt("Please enter the project name", type=str).strip()
        else:
            overwrite = True

    normalized_type = input_type.lower()

    _run_convert_config(
        input_type=normalized_type,
        input_file=input_file,
        output_file=output_file,
        overwrite=overwrite,
        add_project=add_project,
        project_name=project_name,
    )


cli.add_command(init)
cli.add_command(configure)
cli.add_command(set_credentials)
cli.add_command(convert_config_command)
cli.add_command(start)

if __name__ == "__main__":
    cli()
