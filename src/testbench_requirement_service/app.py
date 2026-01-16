from pathlib import Path

from sanic import Sanic

from testbench_requirement_service.config import AppConfig
from testbench_requirement_service.exceptions import handle_jira_error
from testbench_requirement_service.middlewares import check_request_auth, log_request, log_response
from testbench_requirement_service.routes import router
from testbench_requirement_service.utils.dependencies import (
    check_excel_dependencies,
    check_jira_dependencies,
)


def register_middlewares(app: Sanic) -> None:
    """Register application middlewares."""
    app.register_middleware(check_request_auth, "request")
    app.register_middleware(log_request, "request")
    app.register_middleware(log_response, "response")  # type: ignore


def register_exception_handlers(app: Sanic) -> None:
    """Register application exception handlers."""
    try:
        from jira import JIRAError  # noqa: PLC0415

        app.exception(JIRAError)(handle_jira_error)
    except ImportError:
        pass


def check_dependencies(app: Sanic) -> None:
    """Check and validate optional dependencies based on reader type."""
    if "ExcelRequirementReader" in app.config.READER_CLASS:
        check_excel_dependencies(raise_on_missing=True)

    if "JiraRequirementReader" in app.config.READER_CLASS:
        check_jira_dependencies(raise_on_missing=True)


def create_app(name: str, config: AppConfig | None = None) -> Sanic:
    """Create and configure the Sanic application."""
    app = Sanic(name)

    # Apply configuration
    if not config:
        config = AppConfig()
    app.update_config(config)

    # Validate dependencies
    check_dependencies(app)

    # Setup application
    register_middlewares(app)
    register_exception_handlers(app)
    app.blueprint(router)

    # Serve static assets
    static_path = (Path(__file__).parent / "static/swagger-ui").resolve().as_posix()
    app.static("/static/swagger-ui", static_path)

    return app
