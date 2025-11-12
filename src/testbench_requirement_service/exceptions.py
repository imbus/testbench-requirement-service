from __future__ import annotations

try:  # noqa: SIM105
    from jira import JIRAError
except ImportError:
    pass
from sanic import Forbidden, NotFound, Request, ServerError


async def handle_jira_error(request: Request, exception: JIRAError):
    if exception.status_code == NotFound.status_code:
        raise NotFound("Not Found")
    if exception.status_code == Forbidden.status_code:
        raise Forbidden("Forbidden")
    raise ServerError("Jira service error")
