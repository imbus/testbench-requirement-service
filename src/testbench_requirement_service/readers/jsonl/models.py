from pydantic import BaseModel

from testbench_requirement_service.models.requirement import (
    RequirementVersionObject,
    UserDefinedAttribute,
)


class FileRequirementKey(BaseModel):
    id: str
    version: RequirementVersionObject


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
