from abc import ABC, abstractmethod

from testbench_requirement_service.models.requirement import (
    BaselineObjectNode,
    ExtendedRequirementObject,
    RequirementKey,
    RequirementVersionObject,
    UserDefinedAttribute,
    UserDefinedAttributes,
)


class FileReader(ABC):
    @abstractmethod
    def __init__(self, config_path: str):
        pass

    @abstractmethod
    def project_exists(self, project: str) -> bool:
        pass

    @abstractmethod
    def baseline_exists(self, project: str, baseline: str) -> bool:
        pass

    @abstractmethod
    def get_projects(self) -> list[str]:
        pass

    @abstractmethod
    def get_baselines(self, project: str) -> list[str]:
        pass

    @abstractmethod
    def get_requirements_root_node(self, project: str, baseline: str) -> BaselineObjectNode:
        pass

    @abstractmethod
    def get_user_defined_attributes(self) -> list[UserDefinedAttribute]:
        pass

    @abstractmethod
    def get_all_user_defined_attributes(
        self,
        project: str,
        baseline: str,
        requirement_keys: list[RequirementKey],
        attribute_names: list[str],
    ) -> list[UserDefinedAttributes]:
        pass

    @abstractmethod
    def get_extended_requirement(
        self, project: str, baseline: str, key: RequirementKey
    ) -> ExtendedRequirementObject:
        pass

    @abstractmethod
    def get_requirement_versions(
        self, project: str, baseline: str, key: RequirementKey
    ) -> list[RequirementVersionObject]:
        pass
