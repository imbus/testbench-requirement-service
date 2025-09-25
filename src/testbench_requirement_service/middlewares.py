from math import ceil
from time import monotonic

from sanic.request import Request
from sanic.response import BaseHTTPResponse, HTTPResponse

from testbench_requirement_service.utils.auth import check_auth_for_request


async def check_request_auth(req: Request):
    if req.path.startswith("/docs") or req.path.startswith("/static"):
        return None

    response = check_auth_for_request(req)
    if isinstance(response, BaseHTTPResponse):
        return response
    return None


# Middleware for request logging
async def log_request(req: Request):
    req.ctx.start_time = monotonic()
    if req.app.config.LOGLEVEL.upper() == "DEBUG":
        print(
            f"Request: {req.method} {req.path}\n"
            f"   Headers: {req.headers}\n"
            f"   Body: {req.body.decode('utf-8') if req.body else 'No Body'}"
        )
    else:
        print(f"Request: {req.method} {req.path}")


# Middleware for request and response logging
async def log_response(req: Request, resp: HTTPResponse):
    response_time = ceil((monotonic() - getattr(req.ctx, "start_time", 0.0)) * 1000) / 1000
    print(f"Response: {resp.status} in {response_time}")
    if req.app.config.LOGLEVEL.upper() == "DEBUG" and resp.body:
        print(f"Response: {resp.status} - Body: {resp.body.decode('utf-8')}")
