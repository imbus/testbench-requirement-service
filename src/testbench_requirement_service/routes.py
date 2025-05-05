from urllib.parse import unquote

from pydantic import ValidationError
from sanic import Blueprint, response
from sanic.exceptions import BadRequest, NotFound
from sanic.request import Request

from testbench_requirement_service import __version__
from testbench_requirement_service.models.requirement import (
    RequirementKey,
    UserDefinedAttributesQuery,
)
from testbench_requirement_service.readers.utils import get_file_reader
from testbench_requirement_service.utils.auth import protected

router = Blueprint("requirement")


@router.route("/server-name-and-version", methods=["GET"])
@protected
async def _get_server_name_and_version(req: Request):
    return response.json(f"{req.app.name}-{__version__}")


@router.route("/user-defined-attributes", methods=["GET"])
@protected
async def _get_user_defined_attributes(req: Request):
    file_reader = get_file_reader(req.app)
    return response.json([uda.model_dump() for uda in file_reader.get_user_defined_attributes()])


@router.route("/projects", methods=["GET"])
@protected
async def _get_projects(req: Request):
    file_reader = get_file_reader(req.app)
    return response.json(file_reader.get_projects())


@router.route("/projects/<project:str>/baselines", methods=["GET"], unquote=True)
@protected
async def _get_baselines(req: Request, project: str):
    project = unquote(project)
    file_reader = get_file_reader(req.app)

    if not file_reader.project_exists(project):
        raise NotFound("Project not found")

    return response.json(file_reader.get_baselines(project))


@router.route(
    "/projects/<project:str>/baselines/<baseline:str>/requirements-root",
    methods=["GET"],
    unquote=True,
)
@protected
async def _get_requirements_root(req: Request, project: str, baseline: str):
    project = unquote(project)
    baseline = unquote(baseline)
    file_reader = get_file_reader(req.app)

    if not file_reader.project_exists(project):
        raise NotFound("Project not found")
    if not file_reader.baseline_exists(project, baseline):
        raise NotFound("Baseline not found")

    return response.json(file_reader.get_requirements_root_node(project, baseline).model_dump())


@router.route(
    "/projects/<project:str>/baselines/<baseline:str>/user-defined-attributes",
    methods=["POST"],
    unquote=True,
)
@protected
async def _post_all_user_defined_attributes(req: Request, project: str, baseline: str):
    project = unquote(project)
    baseline = unquote(baseline)
    file_reader = get_file_reader(req.app)

    if not file_reader.project_exists(project):
        raise NotFound("Project not found")
    if not file_reader.baseline_exists(project, baseline):
        raise NotFound("Baseline not found")

    if req.json is None:
        raise BadRequest("Missing request body")
    try:
        req_body = UserDefinedAttributesQuery.model_validate(req.json)
    except ValidationError as e:
        raise BadRequest("Invalid request body") from e

    return response.json(
        [
            udas.model_dump()
            for udas in file_reader.get_all_user_defined_attributes(
                project, baseline, req_body.keys, req_body.attributeNames
            )
        ]
    )


@router.route(
    "/projects/<project:str>/baselines/<baseline:str>/extended-requirement",
    methods=["POST"],
    unquote=True,
)
@protected
async def _post_extended_requirement(req: Request, project: str, baseline: str):
    project = unquote(project)
    baseline = unquote(baseline)
    file_reader = get_file_reader(req.app)

    if not file_reader.project_exists(project):
        raise NotFound("Project not found")
    if not file_reader.baseline_exists(project, baseline):
        raise NotFound("Baseline not found")

    if req.json is None:
        raise BadRequest("Missing request body")
    try:
        key = RequirementKey(**req.json.get("key", {}))
    except ValidationError as e:
        raise BadRequest("Invalid request body") from e

    return response.json(file_reader.get_extended_requirement(project, baseline, key).model_dump())


@router.route(
    "/projects/<project:str>/baselines/<baseline:str>/requirement-versions",
    methods=["POST"],
    unquote=True,
)
@protected
async def _post_requirement_versions(req: Request, project: str, baseline: str):
    project = unquote(project)
    baseline = unquote(baseline)
    file_reader = get_file_reader(req.app)

    if not file_reader.project_exists(project):
        raise NotFound("Project not found")
    if not file_reader.baseline_exists(project, baseline):
        raise NotFound("Baseline not found")

    if req.json is None:
        raise BadRequest("Missing request body")
    try:
        key = RequirementKey(**req.json.get("key", {}))
    except ValidationError as e:
        raise BadRequest("Invalid request body") from e

    return response.json(
        [
            version.model_dump()
            for version in file_reader.get_requirement_versions(project, baseline, key)
        ]
    )
