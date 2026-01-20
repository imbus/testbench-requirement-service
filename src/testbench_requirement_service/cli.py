import os
from functools import partial

import click
from dotenv import load_dotenv
from sanic import Sanic
from sanic.worker.loader import AppLoader

from testbench_requirement_service import __version__
from testbench_requirement_service.app import AppConfig, create_app
from testbench_requirement_service.utils.auth import hash_password, save_credentials
from testbench_requirement_service.utils.config import (
    create_default_config_file,
    resolve_config_file_path,
)


@click.group()
@click.version_option(
    version=__version__, prog_name="TestBench Requirement Service", message="%(prog)s %(version)s"
)
@click.pass_context
def cli(ctx):
    ctx.max_content_width = 120


@click.command()
@click.option(
    "--path",
    type=str,
    metavar="PATH",
    default="config.toml",
    help="Path to the configuration file to generate.",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    default=False,
    show_default=True,
    help="Overwrite the configuration file if it exists.",
)
def init(path, force):
    """Generate a default configuration file."""
    create_default_config_file(output_path=path, force=force)


@click.command()
@click.option(
    "--config",
    type=str,
    metavar="PATH",
    help=(
        "Path to the app config file  [default: config.toml, automatically falls back to config.py]"
    ),
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
    type=str,
    metavar="PATH",
    help="Path to the reader config file  [default: reader_config.toml]",
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
    load_dotenv()

    app_name = "TestBenchRequirementService"
    app_config = AppConfig(
        config_path=config,
        reader_class=reader_class,
        reader_config_path=reader_config,
        host=host,
        port=port,
        debug=dev,
    )

    print(r"""  ______          __  ____                  __       ____  __  ___   _____                 _         
 /_  __/__  _____/ /_/ __ )___  ____  _____/ /_     / __ \/  |/  /  / ___/___  ______   __(_)_______ 
  / / / _ \/ ___/ __/ __  / _ \/ __ \/ ___/ __ \   / /_/ / /|_/ /   \__ \/ _ \/ ___/ | / / / ___/ _ \
 / / /  __(__  ) /_/ /_/ /  __/ / / / /__/ / / /  / _, _/ /  / /   ___/ /  __/ /   | |/ / / /__/  __/
/_/  \___/____/\__/_____/\___/_/ /_/\___/_/ /_/  /_/ |_/_/  /_/   /____/\___/_/    |___/_/\___/\___/ 
                                                                                                     """)  # noqa: W291, E501

    factory = partial(create_app, app_name, app_config)
    loader = AppLoader(factory=factory)
    app = loader.load()
    if not host:
        host = getattr(app.config, "HOST", None)
    if not port:
        port = getattr(app.config, "PORT", None)
    app.prepare(host=host, port=port, dev=dev, debug=app_config.DEBUG, access_log=True)
    try:
        Sanic.serve(primary=app, app_loader=loader)
    except Exception as e:
        raise click.ClickException("Server could not start.") from e


@click.command()
@click.option(
    "--config",
    type=str,
    show_default=True,
    help="Path to the app config file [default: config.toml]",
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
    config_path = resolve_config_file_path(config)
    salt = os.urandom(16)
    password_hash = hash_password(username + password, salt)
    save_credentials(password_hash, salt, config_path)
    click.echo("Credentials saved.")


cli.add_command(init)
cli.add_command(start)
cli.add_command(set_credentials)

if __name__ == "__main__":
    cli()
