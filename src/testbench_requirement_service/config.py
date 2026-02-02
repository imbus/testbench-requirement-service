"""Configuration management for TestBench Requirement Service."""

import os
import sys
from pathlib import Path

from pydantic import ValidationError
from sanic.config import Config

from testbench_requirement_service.readers.utils import get_reader_config_class
from testbench_requirement_service.utils.config import (
    get_reader_config,
    load_config,
    print_config_errors,
    resolve_config_file_path,
)


class AppConfig(Config):
    """Sanic configuration with uppercase attributes (Sanic requirement)."""

    def __init__(  # noqa: PLR0913
        self,
        config_path: Path | None = None,
        reader_class: str | None = None,
        reader_config_path: Path | None = None,
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

        # Load config from config file
        self.CONFIG_PATH = resolve_config_file_path(config_path)
        service_config = load_config(self.CONFIG_PATH)
        self.SERVICE_CONFIG = service_config

        # Map validated settings to uppercase Sanic config
        self.READER_CLASS = service_config.reader_class
        self.READER_CONFIG_PATH = service_config.reader_config_path or self.CONFIG_PATH
        self.HOST = service_config.host
        self.PORT = service_config.port

        # Override with CLI parameters (highest priority)
        if reader_class:
            self.READER_CLASS = reader_class
        if reader_config_path:
            self.READER_CONFIG_PATH = reader_config_path
        if host:
            self.HOST = host
        if port:
            self.PORT = port
        self.DEBUG = debug or service_config.debug

        # Validate and store reader config
        self.READER_CONFIG = self._validate_reader_config()

        # Load credentials
        self.PASSWORD_HASH = service_config.password_hash or os.getenv("PASSWORD_HASH") or ""
        self.SALT = service_config.salt or os.getenv("SALT") or ""

    def _validate_reader_config(self):
        """Validate reader_config dict against the reader's CONFIG_CLASS.

        Priority:
        1. If reader_config_path points to a separate file, load from there
        2. Otherwise, use reader_config from the main service config
        """
        try:
            config_class = get_reader_config_class(self.READER_CLASS)
            if config_class is None:
                return {}
            reader_config = get_reader_config(self.SERVICE_CONFIG)
            return config_class.model_validate(reader_config)
        except ValidationError as e:
            config_path = Path(self.CONFIG_PATH) if self.CONFIG_PATH else None
            reader_config_path = Path(self.READER_CONFIG_PATH) if self.READER_CONFIG_PATH else None
            if reader_config_path and reader_config_path != config_path:
                print_config_errors(e, config_path=reader_config_path, config_prefix=None)
            else:
                print_config_errors(e, config_path=reader_config_path)
            sys.exit(1)
        except Exception as e:
            raise ValueError(f"Failed to validate reader configuration: {e}") from e
