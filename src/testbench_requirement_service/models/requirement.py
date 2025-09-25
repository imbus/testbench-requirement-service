from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_serializer


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
    comment: str | None = None

    @field_serializer("date")
    def serialize_date(self, date: datetime):
        return date.isoformat(timespec="seconds")


class BaselineObject(BaseModel):
    name: str
    date: datetime
    type: Literal["CURRENT", "UNLOCKED", "LOCKED", "DISABLED", "INVALID"]

    @field_serializer("date")
    def serialize_date(self, date: datetime):
        return date.isoformat(timespec="seconds")


class BaselineObjectNode(BaselineObject):
    children: list[RequirementObjectNode] | None = []


class UserDefinedAttribute(BaseModel):
    name: str
    valueType: Literal["STRING", "ARRAY", "BOOLEAN"]
    stringValue: str | None = None
    stringValues: list[str] | None = None
    booleanValue: bool | None = None


class UserDefinedAttributeRequest(BaseModel):
    keys: list[RequirementKey]
    attributeNames: list[str]


class UserDefinedAttributeResponse(BaseModel):
    key: RequirementKey
    userDefinedAttributes: list[UserDefinedAttribute] | None = []


RequirementObjectNode.model_rebuild()
