"""Configuration management for TestBench Requirement Service."""

import os
from pathlib import Path

from sanic.config import Config

from testbench_requirement_service.models.config import Settings
from testbench_requirement_service.utils.config import load_settings


class AppConfig(Config):
    """Sanic configuration with uppercase attributes (Sanic requirement)."""

    def __init__(  # noqa: PLR0913
        self,
        config_path: str | None = None,
        reader_class: str | None = None,
        reader_config_path: str | None = None,
        host: str | None = None,
        port: int | None = None,
        debug: bool | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        # Sanic-specific settings
        self.OAS_UI_DEFAULT = "swagger"
        self.OAS_UI_REDOC = False
        self.OAS_CUSTOM_FILE = (Path(__file__).parent / "openapi.yaml").resolve().as_posix()
        self.OAS_PATH_TO_SWAGGER_HTML = (
            (Path(__file__).parent / "static/swagger-ui/index.html").resolve().as_posix()
        )

        # Load settings from config file
        settings: Settings = load_settings(config_path)
        self.SETTINGS = settings

        # Map validated settings to uppercase Sanic config
        self.READER_CLASS = settings.reader_class
        self.READER_CONFIG_PATH = settings.reader_config_path
        self.HOST = settings.host
        self.PORT = settings.port

        # Override with CLI parameters (highest priority)
        if reader_class:
            self.READER_CLASS = reader_class
        if reader_config_path:
            self.READER_CONFIG_PATH = reader_config_path
        if host:
            self.HOST = host
        if port:
            self.PORT = port
        self.DEBUG = debug or settings.debug

        # Load credentials
        self.PASSWORD_HASH = settings.password_hash or os.getenv("PASSWORD_HASH") or ""
        self.SALT = settings.salt or os.getenv("SALT") or ""
