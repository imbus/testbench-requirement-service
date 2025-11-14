from testbench_requirement_service.models.requirement import (
    ExtendedRequirementObject,
    RequirementKey,
    RequirementObjectNode,
)
from testbench_requirement_service.readers.jsonl.models import FileRequirementObjectNode


def build_requirementobject_from_file_object(
    file_node: FileRequirementObjectNode,
) -> RequirementObjectNode:
    """Transform a FileRequirementObjectNode into a RequirementObjectNode."""
    return RequirementObjectNode(
        name=file_node.name,
        extendedID=file_node.extendedID,
        key=RequirementKey(id=file_node.key.id, version=file_node.key.version.name),
        owner=file_node.owner,
        status=file_node.status,
        priority=file_node.priority,
        requirement=file_node.requirement,
        children=None,  # Children will be attached in the tree-building step
    )


def build_extendedrequirementobject_from_file_object(
    file_node: FileRequirementObjectNode, baseline: str
) -> ExtendedRequirementObject:
    """Transform a FileRequirementObjectNode into a ExtendedRequirementObject."""
    return ExtendedRequirementObject(
        name=file_node.name,
        extendedID=file_node.extendedID,
        key=RequirementKey(id=file_node.key.id, version=file_node.key.version.name),
        owner=file_node.owner,
        status=file_node.status,
        priority=file_node.priority,
        requirement=file_node.requirement,
        description=file_node.description,
        documents=file_node.documents,
        baseline=baseline,
    )
