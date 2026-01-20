from math import ceil
from time import monotonic

from sanic.request import Request
from sanic.response import BaseHTTPResponse, HTTPResponse

from testbench_requirement_service.log import logger
from testbench_requirement_service.utils.auth import check_auth_for_request


async def check_request_auth(req: Request):
    if (
        req.path in {"/", "/favicon.ico", "/openapi.yaml"}
        or req.path.startswith("/docs")
        or req.path.startswith("/static")
    ):
        return None

    response = check_auth_for_request(req)
    if isinstance(response, BaseHTTPResponse):
        return response
    return None


# Middleware for request logging
async def log_request(req: Request):
    req.ctx.start_time = monotonic()
    max_len = getattr(req.app.config, "MAX_LOG_BODY", 1024)

    def _format_body(body: bytes) -> str:
        if not body:
            return "No Body"
        try:
            text = body.decode("utf-8")
        except Exception:
            # fallback to repr if decoding fails
            text = repr(body)
        if len(text) > max_len:
            return f"{text[:max_len]}... (truncated, {len(text)} bytes)"
        return text

    try:
        body_text = _format_body(req.body)
    except Exception:
        body_text = "<error reading body>"

    logger.debug(
        f"Request: {req.method} {req.path}\n   Headers: {req.headers}\n   Body: {body_text}"
    )


# Middleware for request and response logging
async def log_response(req: Request, resp: HTTPResponse):
    response_time = ceil((monotonic() - getattr(req.ctx, "start_time", 0.0)) * 1000) / 1000
    max_len = getattr(req.app.config, "MAX_LOG_BODY", 1024)

    def _format_resp_body(body: bytes) -> str:
        if not body:
            return "No Body"
        try:
            text = body.decode("utf-8")
        except Exception:
            text = repr(body)
        if len(text) > max_len:
            return f"{text[:max_len]}... (truncated, {len(text)} bytes)"
        return text

    try:
        resp_body_text = _format_resp_body(getattr(resp, "body", b""))
    except Exception:
        resp_body_text = "<error reading response body>"

    logger.debug(f"Response: {resp.status} in {response_time}s\n   Body: {resp_body_text}")
