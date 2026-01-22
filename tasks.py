import robot  # type: ignore
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
def test(c: Context, loglevel: str = "TRACE:INFO") -> None:
    """Runs the robot tests."""
    failed = robot.run(
        "tests/robot", loglevel=loglevel, variable=["HEADLESS:True"], outputdir="results"
    )
    if failed:
        raise SystemExit(failed)
