"""Configuration models for TestBench Requirement Service."""

from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from testbench_requirement_service.models.logging import LoggingConfig


class Settings(BaseModel):
    """Validated settings loaded from TOML or legacy Python config."""

    reader_class: str = "testbench_requirement_service.readers.JsonlRequirementReader"
    reader_config_path: str | None = None
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    password_hash: str | None = None
    salt: str | None = None
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @field_validator("reader_config_path")
    @classmethod
    def validate_reader_config_exists(cls, v: str | None) -> str | None:
        """Validate that reader_config_path exists if provided."""
        if v is not None and not Path(v).exists():
            raise ValueError(f"Reader config file not found: '{v}'")
        return v
