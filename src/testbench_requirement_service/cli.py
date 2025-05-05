import os
from functools import partial
from pathlib import Path

import click
from sanic import Sanic
from sanic.worker.loader import AppLoader

from testbench_requirement_service import __version__
from testbench_requirement_service.app import AppConfig, create_app
from testbench_requirement_service.utils.auth import hash_password, save_credentials_in_config_file


@click.group()
@click.version_option(
    version=__version__, prog_name="TestBench Requirement Service", message="%(prog)s %(version)s"
)
@click.pass_context
def cli(ctx):
    ctx.max_content_width = 120


@click.command()
@click.option(
    "--config", type=str, metavar="PATH", help="Path to the app config file  [default: config.py]"
)
@click.option(
    "--reader-class",
    type=str,
    metavar="PATH",
    help="""Path or module string to the reader class  \b
    [default: testbench_requirement_service.readers.JsonlFileReader]""",
)
@click.option(
    "--reader-config",
    type=str,
    metavar="PATH",
    help="Path to the reader config file  [default: reader_config.py]",
)
@click.option(
    "--host", type=str, metavar="HOST", help="Host to run the service on  [default: 127.0.0.1]"
)
@click.option(
    "--port", type=int, metavar="PORT", help="Port to run the service on  [default: 8000]"
)
@click.option(
    "--dev",
    is_flag=True,
    default=False,
    show_default=True,
    help="Run the service in dev mode (debug + auto reload)",
)
def start(config, reader_class, reader_config, host, port, dev):  # noqa: PLR0913
    """Start the TestBench Requirement Service."""
    app_name = "RequirementWrapperAPI"
    loglevel = "DEBUG" if dev else None
    app_config = AppConfig(config, reader_class, reader_config, loglevel)
    factory = partial(create_app, app_name, app_config)
    loader = AppLoader(factory=factory)
    app = loader.load()
    if not host:
        host = getattr(app.config, "HOST", None)
    if not port:
        port = getattr(app.config, "PORT", None)
    app.prepare(host=host, port=port, dev=dev)
    try:
        Sanic.serve(primary=app, app_loader=loader)
    except Exception as e:
        raise click.ClickException("Server could not start.") from e


@click.command()
@click.option(
    "--config", type=str, default="config.py", show_default=True, help="Path to the app config file"
)
@click.option("--username", type=str, prompt="Enter your username", help="Your username")
@click.option(
    "--password",
    type=str,
    prompt="Enter your password",
    help="Your password",
    hide_input=True,
    confirmation_prompt="Confirm your password",
)
def set_credentials(config, username, password):
    """Set credentials for the TestBench Requirement Service."""
    config_path = Path(config)
    salt = os.urandom(16)
    password_hash = hash_password(username + password, salt)
    save_credentials_in_config_file(password_hash, salt, config_path)
    click.echo(f"Credentials saved to '{config_path}'.")


cli.add_command(start)
cli.add_command(set_credentials)
