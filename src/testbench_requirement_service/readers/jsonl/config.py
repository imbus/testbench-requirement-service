from pathlib import Path

from pydantic import BaseModel, field_validator


class JsonlRequirementReaderConfig(BaseModel):
    requirements_path: Path

    @field_validator("requirements_path", mode="after")
    @classmethod
    def validate_requirements_path(cls, requirements_path: Path) -> Path:
        if not requirements_path.exists():
            raise FileNotFoundError(
                f"requirements_path not found: '{requirements_path.resolve()}'."
            )
        return requirements_path
