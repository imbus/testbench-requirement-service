from functools import partial
from pathlib import Path
from ssl import SSLContext

import click
from dotenv import load_dotenv
from sanic import Sanic
from sanic.worker.loader import AppLoader

from testbench_requirement_service import __version__
from testbench_requirement_service.app import AppConfig, create_app
from testbench_requirement_service.utils.config_wizard import (
    configure_credentials_only,
    configure_reader_only,
    configure_service_only,
    run_full_wizard,
    show_main_menu,
    view_current_config,
)


def print_service_banner():
    """Print the service banner."""
    click.echo(r"""  ______          __  ____                  __       ____  __  ___   _____                 _         
 /_  __/__  _____/ /_/ __ )___  ____  _____/ /_     / __ \/  |/  /  / ___/___  ______   __(_)_______ 
  / / / _ \/ ___/ __/ __  / _ \/ __ \/ ___/ __ \   / /_/ / /|_/ /   \__ \/ _ \/ ___/ | / / / ___/ _ \
 / / /  __(__  ) /_/ /_/ /  __/ / / / /__/ / / /  / _, _/ /  / /   ___/ /  __/ /   | |/ / / /__/  __/
/_/  \___/____/\__/_____/\___/_/ /_/\___/_/ /_/  /_/ |_/_/  /_/   /____/\___/_/    |___/_/\___/\___/ 
                                                                                                     """)  # noqa: W291, E501


def print_wizard_banner():
    """Print the configuration wizard banner."""
    click.echo("╔════════════════════════════════════════════════════════╗")
    click.echo("║  TestBench Requirement Service - Configuration Wizard  ║")
    click.echo("╚════════════════════════════════════════════════════════╝\n")


@click.group()
@click.version_option(
    version=__version__, prog_name="TestBench Requirement Service", message="%(prog)s %(version)s"
)
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
    app_name = "TestBenchRequirementService"
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
    app = loader.load()
    if not host:
        host = getattr(app.config, "HOST", None)
    if not port:
        port = getattr(app.config, "PORT", None)

    ssl_context = app_config.get_ssl_context()

    use_single_process = isinstance(ssl_context, SSLContext)
    if use_single_process:
        # SSLContext cannot be pickled, so we must use app.run() directly (single-process)
        # instead of Sanic.serve() with AppLoader (which uses multiprocessing)
        try:
            app.run(
                host=host,
                port=port,
                debug=app_config.DEBUG,
                access_log=True,
                ssl=ssl_context,
                single_process=True,
            )
        except Exception as e:
            raise click.ClickException("Server could not start.") from e
    else:
        app.prepare(
            host=host,
            port=port,
            dev=dev,
            debug=app_config.DEBUG,
            access_log=True,
            ssl=ssl_context,
        )
        try:
            Sanic.serve(primary=app, app_loader=loader)
        except Exception as e:
            raise click.ClickException("Server could not start.") from e


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


cli.add_command(init)
cli.add_command(configure)
cli.add_command(set_credentials)
cli.add_command(start)

if __name__ == "__main__":
    cli()
