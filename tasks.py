try:
    import robot  # type: ignore
except ImportError:
    robot = None
from invoke import Context, task


def run_command(c: Context, command: str) -> int:
    """Run a command and return whether it failed."""
    result = c.run(command, warn=True)
    return int(result.failed if result else True)


@task
def lint_robot(c: Context) -> None:
    """Runs robocop on the project files."""
    failed = run_command(c, "robocop check tests/robot --include *.robot --include *.resource")
    failed += run_command(
        c, "robocop format tests/robot tests/robot --include *.robot --include *.resource"
    )
    if failed:
        raise SystemExit(failed)


@task
def lint_python(c: Context) -> None:
    """Task to run ruff and mypy on project files."""
    failed = run_command(c, "mypy --config-file pyproject.toml .")
    failed += run_command(c, "ruff format --config pyproject.toml .")
    failed += run_command(c, "ruff check --fix --config pyproject.toml .")
    if failed:
        raise SystemExit(failed)


@task(lint_python, lint_robot)
def lint(c: Context) -> None:
    """Runs all linting tasks."""


@task
def test(c: Context, loglevel: str = "TRACE:INFO") -> None:  # noqa: PT028
    """Runs the robot tests."""
    failed = robot.run(
        "tests/robot", loglevel=loglevel, variable=["HEADLESS:True"], outputdir="results"
    )
    if failed:
        raise SystemExit(failed)


@task
def generate_schemas(c: Context) -> None:
    """Generate JSON schemas from Pydantic models."""
    run_command(
        c, "python src/testbench_requirement_service/readers/jsonl/schemas/generate_schemas.py"
    )


@task
def build_binary(c: Context, no_clean: bool = False) -> None:
    """Build a self-contained binary using PyInstaller.

    invoke build-binary
    invoke build-binary --no-clean
    """
    cmd = "python build_binary.py"
    if no_clean:
        cmd += " --no-clean"
    run_command(c, cmd)


@task
def download_deps(  # noqa: PLR0913
    c: Context,
    extras: str = "excel,jira,sql,dev",
    platform: str = "win_amd64",
    python_versions: str = "310,311,312,313",
    dest: str = "downloads",
    zip: bool = False,  # noqa: A002
) -> None:
    """Download dependency wheels for offline installation.

    invoke download-deps
    invoke download-deps --platform manylinux_2_17_x86_64 --zip
    invoke download-deps --python-versions 310,311 --extras excel,jira
    """
    cmd = (
        f"python download_dependencies.py"
        f" --extras {extras}"
        f" --platform {platform}"
        f" --python-versions {python_versions}"
        f" --dest {dest}"
    )
    if zip:
        cmd += " --zip"
    run_command(c, cmd)
