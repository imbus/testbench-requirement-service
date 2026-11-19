from itertools import count

import pytest
from sanic import Sanic

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


def test_docs_serves_swagger_ui_configuration(app: Sanic) -> None:
    _, resp = app.test_client.get("/docs/swagger-config")

    assert resp.status == 200
    assert resp.json == SWAGGER_UI_CONFIGURATION
