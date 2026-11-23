"""Serve the bundled OpenAPI spec and Swagger UI under ``/docs``.

These routes used to come from sanic-ext. sanic-ext depends on PyYAML, which has no
wheels for every supported Python version and cannot be built on Windows without a
C compiler, so the service serves its static spec itself.
"""

from pathlib import Path

from sanic import Blueprint, response
from sanic.request import Request

PACKAGE_DIR = Path(__file__).parent
OPENAPI_SPEC_PATH = PACKAGE_DIR / "openapi.yaml"
SWAGGER_HTML_PATH = PACKAGE_DIR / "static" / "swagger-ui" / "index.html"
SWAGGER_HTML_TITLE = "OpenAPI Swagger"
SWAGGER_UI_CONFIGURATION = {
    "apisSorter": "alpha",
    "operationsSorter": "alpha",
    "docExpansion": "full",
}

docs = Blueprint("docs", url_prefix="/docs")


@docs.get("/", strict_slashes=False)
@docs.get("/swagger", name="swagger_ui_alias")
async def swagger_ui(request: Request):
    page = SWAGGER_HTML_PATH.read_text(encoding="utf-8")
    return response.html(page.replace("__HTML_TITLE__", SWAGGER_HTML_TITLE))


@docs.get("/openapi.json")
async def openapi_spec(request: Request):
    return await response.file(OPENAPI_SPEC_PATH)


@docs.get("/swagger-config")
async def swagger_config(request: Request):
    return response.json(SWAGGER_UI_CONFIGURATION)
