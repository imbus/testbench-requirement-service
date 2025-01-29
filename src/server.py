import base64
import hashlib
import json
from datetime import datetime, timezone
from functools import wraps
from math import ceil
from pathlib import Path
from time import monotonic
from typing import Literal

from pydantic import BaseModel
from sanic import Sanic, response
from sanic.exceptions import NotFound
from sanic.request import Request
from sanic.response import HTTPResponse

# Initialize Sanic app
app = Sanic("RequirementWrapperAPI")
if Path("./config.py").exists():
    app.update_config("./config.py")
elif app.config.get("CONFIG_PATH"):
    app.update_config(app.config.CONFIG_PATH)
app.config.OAS_CUSTOM_FILE = (Path(__file__).parent / "openapi.yaml").resolve().as_posix()
loglevel = "INFO"
base_dir = Path("./requirements")


def hash_password(password: str, salt: bytes) -> str:
    """Hashes a password with a given salt using PBKDF2."""
    pepper = b"\xfb\x0e\xbb\x1cg\x15'\x8f6\x15\xcc\x14\x81\xd8\xfe\x93"
    return hashlib.pbkdf2_hmac("sha256", password.encode() + pepper, salt, 100000).hex()


def check_auth(username: str, password: str) -> bool:
    """Check if a username/password combination is valid and stores that if so."""
    if getattr(app.ctx, "valid_hash", None) == username + password:
        return True
    is_valid = bool(
        hash_password(username + password, base64.b64decode(app.config.SALT))
        == app.config.PASSWORD_HASH
    )
    if is_valid:
        app.ctx.valid_hash = username + password
    return is_valid


def protected(wrapped):
    def decorator(f):
        @wraps(f)
        async def decorated_function(request: Request, *args, **kwargs):
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Basic "):
                return response.json({"message": "Unauthorized"}, status=401)
            try:
                auth_decoded = base64.b64decode(auth_header.split(" ")[1]).decode("utf-8")
                username, password = auth_decoded.split(":", 1)
            except Exception:
                return response.json({"message": "Invalid authentication format"}, status=401)
            try:
                if not check_auth(username, password):
                    return response.json({"message": "Invalid credentials"}, status=403)
            except Exception:
                return response.json(
                    {"message": "Invalid Configuration! No server credentials set."}, status=500
                )
            return await f(request, *args, **kwargs)

        return decorated_function

    return decorator(wrapped)


# Middleware for request logging
@app.on_request
async def log_request(req: Request):
    req.ctx.start_time = monotonic()
    if loglevel.upper() == "DEBUG":
        print(
            f"Request: {req.method} {req.path}\n"
            f"   Headers: {req.headers}\n"
            f"   Body: {req.body.decode('utf-8') if req.body else 'No Body'}"
        )
    else:
        print(f"Request: {req.method} {req.path}")


# Middleware for request and response logging
@app.on_response
async def log_response(req: Request, resp: HTTPResponse):
    response_time = ceil((monotonic() - getattr(req.ctx, "start_time", 0.0)) * 1000) / 1000
    print(f"Response: {resp.status} in {response_time}")
    if loglevel.upper() == "DEBUG" and resp.body:
        print(f"Response: {resp.status} - Body: {resp.body.decode('utf-8')}")


# Models for HTTP API
class ValueType(str):
    STRING = "STRING"
    ARRAY = "ARRAY"
    BOOLEAN = "BOOLEAN"


class UserDefinedAttribute(BaseModel):
    name: str
    valueType: Literal["STRING", "ARRAY", "BOOLEAN"]
    stringValue: str | None = None
    stringValues: list[str] | None = None
    booleanValue: bool | None = None


class RequirementKey(BaseModel):
    id: str
    version: str


class RequirementObject(BaseModel):
    name: str
    extendedID: str
    key: RequirementKey
    owner: str
    status: str
    priority: str
    requirement: bool


class RequirementObjectNode(RequirementObject):
    children: list["RequirementObjectNode"] | None = None


class ExtendedRequirementObject(RequirementObject):
    description: str
    documents: list[str]
    baseline: str


class BaselineObjectNode(BaseModel):
    name: str
    date: str
    type: str
    repositoryID: str
    children: list[RequirementObjectNode] | None = []


class UserDefinedAttributes(BaseModel):
    key: RequirementKey
    userDefinedAttributes: list[UserDefinedAttribute]


RequirementObjectNode.model_rebuild()


# Models for JSON lines file
class FileRequirementVersionObject(BaseModel):
    name: str
    date: str
    author: str
    comment: str


class FileRequirementKey(BaseModel):
    id: str
    version: FileRequirementVersionObject


class FileRequirementObjectNode(BaseModel):
    name: str
    extendedID: str
    key: FileRequirementKey
    owner: str
    status: str
    priority: str
    requirement: bool
    description: str
    documents: list[str]
    parent: str | None
    userDefinedAttributes: list[UserDefinedAttribute]


def get_requirementobject_from_file_object(
    file_node: FileRequirementObjectNode,
) -> RequirementObjectNode:
    """Transform a FileRequirementObjectNode into a RequirementObjectNode."""
    return RequirementObjectNode(
        name=file_node.name,
        extendedID=file_node.extendedID,
        key=RequirementKey(id=file_node.key.id, version=file_node.key.version.name),
        owner=file_node.owner,
        status=file_node.status,
        priority=file_node.priority,
        requirement=file_node.requirement,
        children=None,  # Children will be attached in the tree-building step
    )


def get_extendedrequirementobject_from_file_object(
    file_node: FileRequirementObjectNode, baseline: str
) -> ExtendedRequirementObject:
    """Transform a FileRequirementObjectNode into a ExtendedRequirementObject."""
    return ExtendedRequirementObject(
        name=file_node.name,
        extendedID=file_node.extendedID,
        key=RequirementKey(id=file_node.key.id, version=file_node.key.version.name),
        owner=file_node.owner,
        status=file_node.status,
        priority=file_node.priority,
        requirement=file_node.requirement,
        description=file_node.description,
        documents=file_node.documents,
        baseline=baseline,
    )


@app.route("/server-name-and-version", methods=["GET"])
@protected
async def get_server_name_and_version(request):
    return response.json("RequirementWrapperServer-1.0.0")


@app.route("/projects", methods=["GET"])
@protected
async def get_projects(req: Request):
    if not base_dir.exists():
        return response.json([], status=200)
    projects = [p.name for p in base_dir.iterdir() if p.is_dir()]
    return response.json(projects)


@app.route("/projects/<project>/baselines", methods=["GET"])
@protected
async def get_baselines(req: Request, project: str):
    project_path = get_project_path(project)
    baselines = [f.stem for f in project_path.iterdir() if f.suffix == ".jsonl"]
    return response.json(baselines)


@app.route("/projects/<project>/baselines/<baseline>/requirements-root", methods=["GET"])
@protected
async def get_requirements_root(req: Request, project: str, baseline: str):
    baseline_path = get_baseline_path(project, baseline)

    # Parse the requirements file into FileRequirementObjectNode objects
    requirement_nodes: dict[str, RequirementObjectNode] = {}
    requirement_tree: dict[str, RequirementObjectNode] = {}
    with baseline_path.open("r") as f:
        for line in f:
            file_node = FileRequirementObjectNode(**json.loads(line))
            requirement_node = get_requirementobject_from_file_object(file_node)
            if file_node.key.id in requirement_nodes:
                continue
            requirement_nodes[file_node.key.id] = requirement_node
            if file_node.parent:
                if file_node.parent not in requirement_nodes:
                    raise ValueError(
                        "Parent relation not in order!\n"
                        f"  key: {file_node.key.model_dump()}"
                        f"  parent: {file_node.parent}"
                    )
                parent = requirement_nodes[file_node.parent]
                if parent.children is None:
                    parent.children = [requirement_node]
                else:
                    parent.children.append(requirement_node)
            else:
                requirement_tree[file_node.key.id] = requirement_node

    baseline_node = BaselineObjectNode(
        name=baseline,
        date=datetime.now(timezone.utc).isoformat(),
        type="CURRENT",
        repositoryID=f"{project}/{baseline}",
        children=list(requirement_tree.values()),
    )
    return response.json(baseline_node.model_dump())


@app.route("/user-defined-attributes", methods=["GET"])
@protected
async def get_user_defined_attributes(req: Request):
    filepath = base_dir / "UserDefinedAttributes.json"
    if not filepath.exists():
        return response.json([], status=200)
    with filepath.open("r") as f:
        data = json.load(f)
    return response.json(data)


@app.route("/projects/<project>/baselines/<baseline>/user-defined-attributes", methods=["POST"])
@protected
async def post_user_defined_attributes(req: Request, project: str, baseline: str):
    baseline_path = get_baseline_path(project, baseline)

    keys: dict[str, dict[str, None]] = {}
    for key in req.json.get("keys"):
        if key["id"] in keys:
            keys[key["id"]][key["version"]] = None
        else:
            keys[key["id"]] = {key["version"]: None}

    attribute_names: list[str] = req.json.get("attributeNames")

    file_nodes: list[dict] = []
    with baseline_path.open("r") as f:
        for line in f:
            file_node = FileRequirementObjectNode(**json.loads(line))
            if file_node.key.id in keys and file_node.key.version.name in keys[file_node.key.id]:
                file_nodes.append(
                    UserDefinedAttributes(
                        key=RequirementKey(id=file_node.key.id, version=file_node.key.version.name),
                        userDefinedAttributes=list(
                            filter(
                                lambda udf: udf.name in attribute_names,
                                file_node.userDefinedAttributes,
                            )
                        ),
                    ).model_dump()
                )

    return response.json(file_nodes)


@app.route("/projects/<project>/baselines/<baseline>/extended-requirement", methods=["POST"])
@protected
async def post_extended_requirement(req: Request, project: str, baseline: str):
    baseline_path = get_baseline_path(project, baseline)
    # Extract the key from the request body
    key = RequirementKey(**req.json.get("key"))
    with baseline_path.open("r") as f:
        for line in f:
            file_node = FileRequirementObjectNode(**json.loads(line))
            if file_node.key.id == key.id and file_node.key.version.name == key.version:
                return response.json(
                    get_extendedrequirementobject_from_file_object(file_node, baseline).model_dump()
                )
    raise NotFound("Requirement not found")


def get_project_path(project):
    project_path = base_dir / project
    if not project_path.exists():
        raise NotFound("Project not found")
    return project_path


def get_baseline_path(project, baseline):
    baseline_path = base_dir / project / f"{baseline}.jsonl"
    if not baseline_path.exists():
        raise NotFound("Baseline not found")
    return baseline_path


@app.route("/projects/<project>/baselines/<baseline>/requirement-versions", methods=["POST"])
@protected
async def post_requirement_versions(req: Request, project: str, baseline: str):
    baseline_path = get_baseline_path(project, baseline)
    key = RequirementKey(**req.json.get("key"))
    # Extract versions from the file
    versions = []
    with baseline_path.open("r") as f:
        for line in f:
            file_node = FileRequirementObjectNode(**json.loads(line))
            if file_node.key.id == key.id:
                versions.append(file_node.key.version.model_dump())
    return response.json(versions)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
