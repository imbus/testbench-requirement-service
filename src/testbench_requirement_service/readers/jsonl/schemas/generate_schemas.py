#!/usr/bin/env python3
"""
Generate JSON schemas from Pydantic models.

Run this script whenever you update the Pydantic models to regenerate the JSON schemas.
Usage: python generate_schemas.py
"""

import json
from pathlib import Path

from pydantic import BaseModel

from testbench_requirement_service.models.requirement import UserDefinedAttribute
from testbench_requirement_service.readers.jsonl.models import FileRequirementObjectNode


def generate_json_schema(model_class: type[BaseModel]) -> dict:
    """Generate JSON schema from a Pydantic model class."""
    return model_class.model_json_schema()


def write_json_schema_to_file(schema: dict, output_path: Path):
    """Write a JSON schema dictionary to a file."""
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(schema, f, indent=4, ensure_ascii=False)
    print(f"[OK] Generated: {output_path.name}")


def generate_requirement_object_schema():
    """Generate JSON schema for requirement objects in JSONL files."""
    schema = generate_json_schema(FileRequirementObjectNode)
    output_path = Path(__file__).parent / "requirement_object_schema.json"
    write_json_schema_to_file(schema, output_path)


def generate_user_defined_attributes_schema():
    """Generate JSON schema for UserDefinedAttributes.json definition file."""
    schema = generate_json_schema(UserDefinedAttribute)
    output_path = Path(__file__).parent / "user_defined_attributes_schema.json"
    write_json_schema_to_file(schema, output_path)


def main():
    """Generate all JSON schemas."""
    print("Generating JSON schemas from Pydantic models...")
    print()

    generate_requirement_object_schema()
    generate_user_defined_attributes_schema()

    print()
    print("[OK] All schemas generated successfully!")
    print()
    print("Note: Review the generated schemas and commit them to version control.")


if __name__ == "__main__":
    main()
