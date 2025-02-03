# Models for HTTP API
from typing import Literal

from pydantic import BaseModel


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
    # TODO:  Check if this could be used with datetime type for date field.
    # therefore using the standard object?
    # Bitte testen, ob `model_dump()` von pydantic datetime objekte zu ISO format umwandelt.
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
