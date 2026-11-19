import json
from itertools import count
from pathlib import Path

import pytest
from sanic import Sanic
from sanic.application.ext import setup_ext

from testbench_requirement_service.app import create_app
from testbench_requirement_service.config import AppConfig
from testbench_requirement_service.docs import (
    OPENAPI_SPEC_PATH,
    SWAGGER_UI_CONFIGURATION,
    docs,
)

_app_ids = count()


@pytest.fixture
def app() -> Sanic:
    Sanic.test_mode = True
    app = Sanic(f"docs_test_{next(_app_ids)}")
    app.config.AUTO_EXTEND = False
    app.blueprint(docs)
    return app


@pytest.mark.parametrize("path", ["/docs", "/docs/", "/docs/swagger"])
def test_docs_serves_swagger_ui(app: Sanic, path: str) -> None:
    _, resp = app.test_client.get(path)

    assert resp.status == 200
    assert resp.content_type.startswith("text/html")
    assert "/static/swagger-ui/swagger-ui-bundle.min.js" in resp.text
    assert "__HTML_TITLE__" not in resp.text


def test_docs_serves_bundled_openapi_spec(app: Sanic) -> None:
    _, resp = app.test_client.get("/docs/openapi.json")

    assert resp.status == 200
    assert resp.body == OPENAPI_SPEC_PATH.read_bytes()


def test_installed_sanic_ext_does_not_register_conflicting_docs_routes(tmp_path: Path) -> None:
    # Upgrading an existing installation leaves sanic-ext installed. Sanic loads it
    # automatically at server start unless AUTO_EXTEND is off, and its OpenAPI
    # blueprint then clashes with ours ("Route already registered: docs/...").
    requirements_dir = tmp_path / "requirements"
    requirements_dir.mkdir()
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "[testbench-requirement-service]\n"
        'reader_class = "testbench_requirement_service.readers.JsonlRequirementReader"\n'
        "[testbench-requirement-service.reader_config]\n"
        f"requirements_path = {json.dumps(requirements_dir.as_posix())}\n",
        encoding="utf-8",
    )
    Sanic.test_mode = True
    app = create_app(f"docs_test_{next(_app_ids)}", AppConfig(config_path=config_path))

    setup_ext(app)

    assert app.config.AUTO_EXTEND is False
    assert not hasattr(app, "_ext")


def test_docs_serves_swagger_ui_configuration(app: Sanic) -> None:
    _, resp = app.test_client.get("/docs/swagger-config")

    assert resp.status == 200
    assert resp.json == SWAGGER_UI_CONFIGURATION
