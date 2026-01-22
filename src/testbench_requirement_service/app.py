from pathlib import Path

from sanic import Sanic

from testbench_requirement_service.config import AppConfig
from testbench_requirement_service.exceptions import handle_jira_error
from testbench_requirement_service.log import get_logging_dict
from testbench_requirement_service.middlewares import check_request_auth, log_request, log_response
from testbench_requirement_service.routes import router
from testbench_requirement_service.utils.config import load_settings
from testbench_requirement_service.utils.dependencies import (
    check_excel_dependencies,
    check_jira_dependencies,
    check_sql_dependencies,
)


def register_middlewares(app: Sanic) -> None:
    """Register application middlewares."""
    app.register_middleware(check_request_auth, "request")
    app.register_middleware(log_request, "request")
    app.register_middleware(log_response, "response")  # type: ignore


def register_exception_handlers(app: Sanic) -> None:
    """Register application exception handlers."""
    try:
        from jira import JIRAError

        app.exception(JIRAError)(handle_jira_error)
    except ImportError:
        pass


def check_dependencies(app: Sanic) -> None:
    """Check and validate optional dependencies based on reader type."""
    if "ExcelRequirementReader" in app.config.READER_CLASS:
        check_excel_dependencies(raise_on_missing=True)

    if "JiraRequirementReader" in app.config.READER_CLASS:
        check_jira_dependencies(raise_on_missing=True)

    if "SqlRequirementReader" in app.config.READER_CLASS:
        check_sql_dependencies(raise_on_missing=True)


def create_app(name: str, config: AppConfig | None = None) -> Sanic:
    """Create and configure the Sanic application."""
    if not config:
        config = AppConfig()

    settings = getattr(config, "SETTINGS", None)
    if settings is None:
        settings = load_settings()

    debug = getattr(config, "DEBUG", False)
    log_config = get_logging_dict(settings.logging, debug=debug)

    # Create Sanic app
    app = Sanic(name, log_config=log_config)

    # Apply configuration after Sanic initialization
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
