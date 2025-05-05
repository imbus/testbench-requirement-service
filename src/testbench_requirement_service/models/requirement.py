from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_serializer


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


class RequirementVersionObject(BaseModel):
    name: str
    date: datetime
    author: str
    comment: str

    @field_serializer("date")
    def serialize_date(self, date: datetime):
        return date.isoformat()


class BaselineObject(BaseModel):
    name: str
    date: datetime
    type: Literal["CURRENT", "UNLOCKED", "LOCKED", "DISABLED", "INVALID"]
    repositoryID: str

    @field_serializer("date")
    def serialize_date(self, date: datetime):
        return date.isoformat()


class BaselineObjectNode(BaselineObject):
    children: list[RequirementObjectNode] | None = []


class UserDefinedAttributes(BaseModel):
    key: RequirementKey
    userDefinedAttributes: list[UserDefinedAttribute]


class UserDefinedAttributesQuery(BaseModel):
    keys: list[RequirementKey]
    attributeNames: list[str]


RequirementObjectNode.model_rebuild()
