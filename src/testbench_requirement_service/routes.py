from urllib.parse import unquote

from pydantic import ValidationError
from sanic import Blueprint, response
from sanic.exceptions import BadRequest, NotFound
from sanic.request import Request

from testbench_requirement_service import __version__
from testbench_requirement_service.models.requirement import (
    RequirementKey,
    UserDefinedAttributeRequest,
)
from testbench_requirement_service.readers.utils import get_requirement_reader
from testbench_requirement_service.utils.auth import protected

router = Blueprint("requirement")


@router.route("/", methods=["GET"])
async def redirect_to_docs(req: Request):
    return response.redirect("/docs")


@router.route("/server-name-and-version", methods=["GET"])
@protected
async def get_server_name_and_version(req: Request):
    return response.json(f"{req.app.name}-{__version__}")


@router.route("/user-defined-attributes", methods=["GET"])
@protected
async def get_user_defined_attributes(request: Request):
    requirement_reader = get_requirement_reader(request.app)
    return response.json(
        [uda.model_dump() for uda in requirement_reader.get_user_defined_attributes()]
    )


@router.route("/projects", methods=["GET"])
@protected
async def get_projects(request: Request):
    requirement_reader = get_requirement_reader(request.app)
    return response.json(requirement_reader.get_projects())


@router.route("/projects/<project:str>/baselines", methods=["GET"], unquote=True)
@protected
async def get_baselines(request: Request, project: str):
    project = unquote(project)
    requirement_reader = get_requirement_reader(request.app)

    if not requirement_reader.project_exists(project):
        raise NotFound("Project not found")

    return response.json(
        [baseline.model_dump() for baseline in requirement_reader.get_baselines(project)]
    )


@router.route(
    "/projects/<project:str>/baselines/<baseline:str>/requirements-root",
    methods=["GET"],
    unquote=True,
)
@protected
async def get_requirements_root(request: Request, project: str, baseline: str):
    project = unquote(project)
    baseline = unquote(baseline)
    requirement_reader = get_requirement_reader(request.app)

    if not requirement_reader.project_exists(project):
        raise NotFound("Project not found")
    if not requirement_reader.baseline_exists(project, baseline):
        raise NotFound("Baseline not found")

    return response.json(
        requirement_reader.get_requirements_root_node(project, baseline).model_dump()
    )


@router.route(
    "/projects/<project:str>/baselines/<baseline:str>/user-defined-attributes",
    methods=["POST"],
    unquote=True,
)
@protected
async def post_all_user_defined_attributes(request: Request, project: str, baseline: str):
    project = unquote(project)
    baseline = unquote(baseline)
    requirement_reader = get_requirement_reader(request.app)

    if not requirement_reader.project_exists(project):
        raise NotFound("Project not found")
    if not requirement_reader.baseline_exists(project, baseline):
        raise NotFound("Baseline not found")

    if request.json is None:
        raise BadRequest("Missing request body")
    try:
        request_body = UserDefinedAttributeRequest.model_validate(request.json)
    except ValidationError as e:
        raise BadRequest("Invalid request body") from e

    return response.json(
        [
            udas.model_dump()
            for udas in requirement_reader.get_all_user_defined_attributes(
                project, baseline, request_body.keys, request_body.attributeNames
            )
        ]
    )


@router.route(
    "/projects/<project:str>/baselines/<baseline:str>/extended-requirement",
    methods=["POST"],
    unquote=True,
)
@protected
async def post_extended_requirement(request: Request, project: str, baseline: str):
    project = unquote(project)
    baseline = unquote(baseline)
    requirement_reader = get_requirement_reader(request.app)

    if not requirement_reader.project_exists(project):
        raise NotFound("Project not found")
    if not requirement_reader.baseline_exists(project, baseline):
        raise NotFound("Baseline not found")

    if request.json is None:
        raise BadRequest("Missing request body")
    try:
        key = RequirementKey(**request.json)
    except ValidationError as e:
        raise BadRequest("Invalid request body") from e

    return response.json(
        requirement_reader.get_extended_requirement(project, baseline, key).model_dump()
    )


@router.route(
    "/projects/<project:str>/baselines/<baseline:str>/requirement-versions",
    methods=["POST"],
    unquote=True,
)
@protected
async def post_requirement_versions(request: Request, project: str, baseline: str):
    project = unquote(project)
    baseline = unquote(baseline)
    requirement_reader = get_requirement_reader(request.app)

    if not requirement_reader.project_exists(project):
        raise NotFound("Project not found")
    if not requirement_reader.baseline_exists(project, baseline):
        raise NotFound("Baseline not found")

    if request.json is None:
        raise BadRequest("Missing request body")
    try:
        key = RequirementKey(**request.json)
    except ValidationError as e:
        raise BadRequest("Invalid request body") from e

    return response.json(
        [
            version.model_dump()
            for version in requirement_reader.get_requirement_versions(project, baseline, key)
        ]
    )
