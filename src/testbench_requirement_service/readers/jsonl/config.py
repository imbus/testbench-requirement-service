from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class JsonlRequirementReaderConfig(BaseModel):
    requirements_path: Path = Field(..., description="Path to your JSONL requirements directory")

    @field_validator("requirements_path", mode="after")
    @classmethod
    def validate_requirements_path(cls, requirements_path: Path) -> Path:
        try:
            if not requirements_path.exists():
                raise ValueError(
                    f"requirements_path not found: '{requirements_path}'.\n"
                    "  Hint: Use forward slashes (C:/path/to/folder)"
                    " or double-backslashes (C:\\\\path\\\\to\\\\folder)"
                )
        except OSError as e:
            raise ValueError(
                f"cannot access requirements_path: '{requirements_path}'\n  OSError: {e}"
            ) from e
        return requirements_path
