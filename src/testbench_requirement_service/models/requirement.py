from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ValidationInfo, field_serializer, field_validator

MAX_STR_LENGTH = 255
MAX_VERSION_LENGTH = 63


def truncate(v: str, max_length: int) -> str:
    """Truncate a string to the specified maximum length, adding "..." if it was truncated."""
    if not v:
        return v
    return v if len(v) <= max_length else v[: max_length - 3] + "..."


class RequirementKey(BaseModel):
    id: str
    version: str

    @field_validator("id", "version")
    @classmethod
    def must_not_be_empty(cls, v: str, info: ValidationInfo) -> str:
        if not v or not v.strip():
            raise ValueError(f"'{info.field_name}' must not be empty in a requirement row.")
        return v

    @field_serializer("id")
    def serialize_id(self, v: str):
        return truncate(v, MAX_STR_LENGTH)

    @field_serializer("version")
    def serialize_version(self, v: str):
        return truncate(v, MAX_VERSION_LENGTH)


class RequirementObject(BaseModel):
    name: str
    extendedID: str
    key: RequirementKey
    owner: str
    status: str
    priority: str
    requirement: bool

    @field_validator("name")
    @classmethod
    def must_not_be_empty(cls, v: str, info: ValidationInfo) -> str:
        if not v or not v.strip():
            raise ValueError(f"'{info.field_name}' must not be empty in a requirement row.")
        return v

    @field_serializer("name", "extendedID", "owner", "status", "priority")
    def serialize_str(self, v: str):
        return truncate(v, MAX_STR_LENGTH)


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

    @field_serializer("name")
    def serialize_name(self, name: str):
        return truncate(name, MAX_VERSION_LENGTH)

    @field_serializer("date")
    def serialize_date(self, date: datetime):
        return date.isoformat(timespec="seconds")

    @field_serializer("author", "comment")
    def serialize_str(self, v: str | None):
        if v is None:
            return v
        return truncate(v, MAX_STR_LENGTH)


class BaselineObject(BaseModel):
    name: str
    date: datetime
    type: Literal["CURRENT", "UNLOCKED", "LOCKED", "DISABLED", "INVALID"]

    @field_serializer("name")
    def serialize_name(self, name: str):
        return truncate(name, MAX_STR_LENGTH)

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

    @field_serializer("name")
    def serialize_str(self, v: str | None):
        if v is None:
            return v
        return truncate(v, MAX_STR_LENGTH)


class UserDefinedAttributeRequest(BaseModel):
    keys: list[RequirementKey]
    attributeNames: list[str]


class UserDefinedAttributeResponse(BaseModel):
    key: RequirementKey
    userDefinedAttributes: list[UserDefinedAttribute] | None = []


RequirementObjectNode.model_rebuild()
