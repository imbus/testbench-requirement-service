"""Configuration model for SQL requirement reader."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class SqlUserDefinedAttributeConfig(BaseModel):
    """User-defined attribute mapping for SQL sources."""

    name: str = Field(..., description="Name exposed by the API")
    type: Literal["STRING", "ARRAY", "BOOLEAN"] = Field(..., description="Attribute value type")
    array_separator: str = Field(
        ",",
        description="Separator used when ARRAY values are stored as delimited text",
        json_schema_extra={"depends_on": {"type": "ARRAY"}},
    )
    true_value: str = Field(
        "true",
        description="Value interpreted as true for BOOLEAN attributes stored as text",
        json_schema_extra={"depends_on": {"type": "BOOLEAN"}},
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("User-defined attribute name must not be empty")
        return value

    @field_validator("array_separator")
    @classmethod
    def validate_array_separator(cls, v: str) -> str:
        if not v:
            raise ValueError("array_separator must not be empty")
        return v

    @field_validator("true_value")
    @classmethod
    def validate_true_value(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("true_value must not be empty")
        return v


class SqlRequirementReaderConfig(BaseModel):
    """SQL reader configuration loaded from TOML."""

    database_url: str = Field(..., description="Database URL passed to SQLAlchemy create_engine")
    echo: bool = Field(False, description="Enable SQL statement logging")
    pool_pre_ping: bool = Field(True, description="Test pooled connections before use")
    connect_timeout_seconds: int | None = Field(
        None,
        ge=1,
        le=300,
        description="Connection timeout in seconds (driver dependent)",
    )
    pool_size: int = Field(5, ge=1, le=200, description="Preferred SQLAlchemy pool size")
    max_overflow: int = Field(
        10,
        ge=0,
        le=200,
        description="Maximum temporary connections above pool_size",
    )
    pool_recycle_seconds: int = Field(
        1800,
        ge=-1,
        le=86400,
        description="Recycle pooled connections after this number of seconds (-1 disables)",
    )
    user_defined_attributes: list[SqlUserDefinedAttributeConfig] = Field(
        default_factory=list,
        description="User-defined attribute mappings",
        json_schema_extra={
            "prompt_as_list": True,
            "item_label": "User Defined Attribute",
            "add_prompt": "Would you like to add a user-defined SQL attribute?",
            "add_another_prompt": "Add another user-defined SQL attribute?",
        },
    )

    @field_validator(
        "database_url",
    )
    @classmethod
    def validate_non_empty_string(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("Value must not be empty")
        return value

    @model_validator(mode="after")
    def validate_uda_names_unique(self) -> "SqlRequirementReaderConfig":
        seen: set[str] = set()
        for udf in self.user_defined_attributes:
            key = udf.name.casefold()
            if key in seen:
                raise ValueError(f"Duplicate user_defined_attributes name: '{udf.name}'")
            seen.add(key)
        return self
