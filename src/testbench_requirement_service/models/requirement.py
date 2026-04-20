from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    FieldSerializationInfo,
    ValidationInfo,
    field_serializer,
    field_validator,
)

from testbench_requirement_service.log import logger

MAX_STR_LENGTH = 255
MAX_VERSION_LENGTH = 63


def truncate(
    v: str,
    max_length: int,
    field_name: str,
    model_instance: BaseModel,
    warn: bool = False,
) -> str:
    """
    Truncate a string to the specified maximum length, adding '...' if truncated.
    Logs a warning if truncation occurs and 'warn' is True, otherwise logs at debug level.

     Args:
        v: The string to truncate. Returns as-is if None or within max_length.
        max_length: Maximum allowed length of the string (including '...').
        field_name: Name of the field being truncated, used in log output.
        model_instance: The model instance being truncated, used in log output.
        warn: If True, logs at WARNING level instead of DEBUG.
    """
    if not v or len(v) <= max_length:
        return v

    log = logger.warning if warn else logger.debug
    log(
        "Truncating '%s' ('%.40s\u2026') on %s: %d chars exceeds max %d",
        field_name,
        v,
        model_instance.__class__.__name__,
        len(v),
        max_length,
    )

    return v[: max_length - 3] + "..."


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
    def serialize_id(self, v: str) -> str:
        return truncate(v, MAX_STR_LENGTH, "id", self, warn=True)

    @field_serializer("version")
    def serialize_version(self, v: str) -> str:
        return truncate(v, MAX_VERSION_LENGTH, "version", self, warn=True)


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
    def serialize_str(self, v: str, info: FieldSerializationInfo) -> str:
        return truncate(v, MAX_STR_LENGTH, info.field_name, self)


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
    def serialize_name(self, name: str) -> str:
        return truncate(name, MAX_VERSION_LENGTH, "name", self, warn=True)

    @field_serializer("date")
    def serialize_date(self, date: datetime) -> str:
        return date.isoformat(timespec="seconds")

    @field_serializer("author", "comment")
    def serialize_str(self, v: str | None, info: FieldSerializationInfo) -> str | None:
        if v is None:
            return v
        return truncate(v, MAX_STR_LENGTH, info.field_name, self)


class BaselineObject(BaseModel):
    name: str
    date: datetime
    type: Literal["CURRENT", "UNLOCKED", "LOCKED", "DISABLED", "INVALID"]

    @field_serializer("name")
    def serialize_name(self, name: str) -> str:
        return truncate(name, MAX_STR_LENGTH, "name", self, warn=True)

    @field_serializer("date")
    def serialize_date(self, date: datetime) -> str:
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
    def serialize_name(self, v: str) -> str:
        return truncate(v, MAX_STR_LENGTH, "name", self, warn=True)


class UserDefinedAttributeRequest(BaseModel):
    keys: list[RequirementKey]
    attributeNames: list[str]


class UserDefinedAttributeResponse(BaseModel):
    key: RequirementKey
    userDefinedAttributes: list[UserDefinedAttribute] | None = []


RequirementObjectNode.model_rebuild()
