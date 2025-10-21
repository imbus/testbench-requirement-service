from abc import ABC, abstractmethod

from testbench_requirement_service.models.requirement import (
    BaselineObject,
    BaselineObjectNode,
    ExtendedRequirementObject,
    RequirementKey,
    RequirementVersionObject,
    UserDefinedAttribute,
    UserDefinedAttributeResponse,
)


class AbstractRequirementReader(ABC):
    @abstractmethod
    def __init__(self, config_path: str):
        """
        Initialize the requirement reader with the given configuration file path.

        The config_path is set either via CLI option (--reader-config)
        or in the app configuration file.

        Args:
            config_path (str): Path to the reader configuration file.
        """

    @abstractmethod
    def project_exists(self, project: str) -> bool:
        """
        Check if the specified project exists in the data source.

        Args:
            project (str): Name of the project to check.

        Returns:
            bool: True if the project exists, False otherwise.
        """

    @abstractmethod
    def baseline_exists(self, project: str, baseline: str) -> bool:
        """
        Check if the specified baseline exists for the given project.

        Args:
            project (str): Name of the project.
            baseline (str): Name of the baseline to check.

        Returns:
            bool: True if the baseline exists, False otherwise.
        """

    @abstractmethod
    def get_projects(self) -> list[str]:
        """
        Retrieve a list of all available projects in the data source.

        Returns:
            list[str]: List of project names.
        """

    @abstractmethod
    def get_baselines(self, project: str) -> list[BaselineObject]:
        """
        Retrieve a list of baseline objects for the specified project.

        Args:
            project (str): The name or identifier of the project for which to retrieve baselines.

        Returns:
            list[BaselineObject]: A list of BaselineObject instances associated
            with the given project.
        """

    @abstractmethod
    def get_requirements_root_node(self, project: str, baseline: str) -> BaselineObjectNode:
        """
        Retrieves the root node of requirements for a given project and baseline.

        Args:
            project (str): The name or identifier of the project.
            baseline (str): The baseline identifier for which to retrieve the
            requirements root node.

        Returns:
            BaselineObjectNode: The root node of the requirements tree for the
            specified project and baseline.
        """

    @abstractmethod
    def get_user_defined_attributes(self) -> list[UserDefinedAttribute]:
        """
        Retrieves a list of user-defined attributes.

        Returns:
            list[UserDefinedAttribute]: A list containing instances of UserDefinedAttribute
            representing the user-defined attributes.
        """

    @abstractmethod
    def get_all_user_defined_attributes(
        self,
        project: str,
        baseline: str,
        requirement_keys: list[RequirementKey],
        attribute_names: list[str],
    ) -> list[UserDefinedAttributeResponse]:
        """
        Retrieves all user-defined attributes for the specified requirements
        within a project and baseline.

        Args:
            project (str): The name or identifier of the project.
            baseline (str): The baseline within the project to query.
            requirement_keys (list[RequirementKey]): A list of requirement keys
            to fetch attributes for.
            attribute_names (list[str]): A list of attribute names to retrieve for each requirement.

        Returns:
            list[UserDefinedAttributeResponse]: A list of responses containing the
            requested user-defined attributes for each requirement.
        """

    @abstractmethod
    def get_extended_requirement(
        self, project: str, baseline: str, key: RequirementKey
    ) -> ExtendedRequirementObject:
        """
        Retrieves an extended requirement object for the specified project, baseline,
        and requirement key.

        Args:
            project (str): The name of the project.
            baseline (str): The baseline identifier.
            key (RequirementKey): The key identifying the requirement.

        Returns:
            ExtendedRequirementObject: The extended requirement object corresponding
            to the given parameters.
        """

    @abstractmethod
    def get_requirement_versions(
        self, project: str, baseline: str, key: RequirementKey
    ) -> list[RequirementVersionObject]:
        """
        Retrieves all versions of a specific requirement for a given project and baseline.

        Args:
            project (str): The name or identifier of the project.
            baseline (str): The baseline identifier within the project.
            key (RequirementKey): The key identifying the specific requirement.

        Returns:
            list[RequirementVersionObject]: A list of requirement version objects associated with
            the specified requirement key.
        """
