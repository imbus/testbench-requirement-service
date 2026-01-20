from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

try:  # noqa: SIM105
    from jira.resources import Field, Issue, Project
except ImportError:
    pass
from sanic import NotFound

from testbench_requirement_service.log import logger
from testbench_requirement_service.models.requirement import (
    BaselineObject,
    BaselineObjectNode,
    ExtendedRequirementObject,
    RequirementKey,
    RequirementObjectNode,
    RequirementVersionObject,
    UserDefinedAttribute,
    UserDefinedAttributeResponse,
)
from testbench_requirement_service.readers.abstract_reader import AbstractRequirementReader
from testbench_requirement_service.readers.jira.client import JiraClient
from testbench_requirement_service.readers.jira.config import JiraRequirementReaderConfig
from testbench_requirement_service.readers.jira.render_utils import build_rendered_field_html
from testbench_requirement_service.readers.jira.utils import (
    build_extendedrequirementobject_from_issue,
    build_requirementobjectnode_from_issue,
    build_userdefinedattribute_object,
    extract_baselines_from_issue,
    extract_valuetype_from_issue_field,
    generate_requirement_versions,
    get_field_id,
    get_issue_version,
    is_version_type_field,
)
from testbench_requirement_service.readers.utils import load_reader_config_from_path


class JiraRequirementReader(AbstractRequirementReader):
    def __init__(self, config_path: str):
        self.config = load_reader_config_from_path(
            config_path=Path(config_path),
            config_class=JiraRequirementReaderConfig,
            config_prefix="jira",
        )
        self.jira_client = JiraClient(self.config)

        # key: project name (format: "{project.name} ({project.key})"), value: Project Resource
        self._projects: dict[str, Project] = {}
        # key: project name (format: "{project.name} ({project.key})"), value: list of baselines
        self._baselines: dict[str, list[str]] = {}

    @property
    def projects(self) -> dict[str, Project]:
        """Return a dict mapping project name (fmt: "{project.name} ({project.key})") to Project."""
        if not self._projects:
            projects = self.jira_client.fetch_projects()
            self._projects = self._build_project_dict(projects)
        return self._projects

    def project_exists(self, project: str) -> bool:
        if project in self.projects:
            return True
        # Cache miss: fetch projects and check again
        projects = self.jira_client.fetch_projects()
        self._projects = self._build_project_dict(projects)
        return project in self.projects

    def baseline_exists(self, project: str, baseline: str) -> bool:
        return baseline == "Current Baseline" or baseline in self._get_baselines_for_project(
            project
        )

    def get_projects(self) -> list[str]:
        return list(self.projects.keys())

    def get_baselines(self, project: str) -> list[BaselineObject]:
        baselines = sorted(self._get_baselines_for_project(project))
        now = datetime.now(timezone.utc)
        return [
            BaselineObject(
                name="Current Baseline",
                date=now,
                type="CURRENT",
            ),
            *[
                BaselineObject(
                    name=baseline,
                    date=now,
                    type="UNLOCKED",
                )
                for baseline in baselines
            ],
        ]

    def get_requirements_root_node(self, project: str, baseline: str) -> BaselineObjectNode:
        jql_query = self._build_issues_jql(project, baseline)
        issues = self.jira_client.fetch_issues_by_jql(jql_query, expand="changelog")
        if not issues:
            logger.debug(f"No issues found for project '{project}' and baseline '{baseline}'")

        issue_ids = [issue.id for issue in issues]
        issue_changelogs = self.jira_client.fetch_changelog_histories(issue_ids)
        for issue in issues:
            histories = issue_changelogs.get(issue.id, [])
            issue.changelog.histories = histories

        issues.sort(key=self.sort_by_issue_key)
        requirement_nodes = self._build_requirement_nodes(issues, project)
        requirement_tree = self._build_requirement_tree(project, issues, requirement_nodes)

        return BaselineObjectNode(
            name=baseline,
            date=datetime.now(timezone.utc),
            type="CURRENT",
            children=sorted(
                requirement_tree.values(), key=lambda x: int(x.extendedID.split("-")[-1])
            ),
        )

    def get_user_defined_attributes(self) -> list[UserDefinedAttribute]:
        return [
            UserDefinedAttribute(
                name=field["name"],
                valueType=extract_valuetype_from_issue_field(field),
            )
            for field in self.jira_client.fetch_all_custom_fields()
        ]

    def get_all_user_defined_attributes(
        self,
        project: str,
        baseline: str,
        requirement_keys: list[RequirementKey],
        attribute_names: list[str],
    ) -> list[UserDefinedAttributeResponse]:
        if not requirement_keys:
            return []

        custom_fields = self.jira_client.fetch_all_custom_fields()
        fields = [field for field in custom_fields if field["name"] in attribute_names]
        field_ids = [field["id"] for field in fields]

        issue_keys = [req_key.id for req_key in requirement_keys]
        base_jql = self._build_issues_jql(project, baseline)
        issues = self.jira_client.fetch_issues(
            issue_keys,
            base_jql,
            fields=",".join(["key", "attachment", *field_ids]),
            expand="renderedFields",
        )
        issue_map = {issue.key: issue for issue in issues}

        user_defined_attributes: list[UserDefinedAttributeResponse] = []
        for req_key in requirement_keys:
            issue = issue_map.get(req_key.id)
            if not issue:
                continue

            udas = []
            for field in fields:
                if not hasattr(issue.fields, field["id"]):
                    continue
                if hasattr(issue.renderedFields, field["id"]) and field[
                    "name"
                ] in self._get_config_value("rendered_fields", project):
                    field_value = build_rendered_field_html(
                        issue,
                        field_id=field["id"],
                        jira_server_url=self.config.server_url,
                        include_head=True,
                    )
                else:
                    field_value = getattr(issue.fields, field["id"])
                udas.append(build_userdefinedattribute_object(field, field_value))

            user_defined_attributes.append(
                UserDefinedAttributeResponse(key=req_key, userDefinedAttributes=udas)
            )

        return user_defined_attributes

    def get_extended_requirement(
        self, project: str, baseline: str, key: RequirementKey
    ) -> ExtendedRequirementObject:
        fields = self._prepare_fields(
            project=project,
            baseline=baseline,
        )
        expand = "renderedFields,changelog"
        issue = self.jira_client.fetch_issue(key.id, fields=fields, expand=expand)
        if issue is None:
            raise NotFound("Requirement not found")
        self._validate_issue(
            issue
        )  # TODO: discuss whether project and baseline checks are needed here

        custom_fields = self.jira_client.fetch_all_custom_fields()
        issue = get_issue_version(project, issue, key, self.config, custom_fields)
        requirement_object = build_requirementobjectnode_from_issue(
            project=project,
            issue=issue,
            owner_field_name=self._get_config_value("owner", project),
            config=self.config,
            key=key,
            is_requirement=True,
        )
        return build_extendedrequirementobject_from_issue(
            issue=issue,
            baseline=baseline,
            requirement_object=requirement_object,
            jira_server_url=self.config.server_url,
        )

    def get_requirement_versions(
        self, project: str, baseline: str, key: RequirementKey
    ) -> list[RequirementVersionObject]:
        fields = self._prepare_fields("summary,created,creator", project, baseline)
        issue = self.jira_client.fetch_issue(key.id, fields=fields, expand="changelog")
        if issue is None:
            raise NotFound("Requirement not found")
        self._validate_issue(
            issue
        )  # TODO: discuss whether project and baseline checks are needed here
        return generate_requirement_versions(project, issue, self.config)

    def _build_project_dict(self, projects: list[Project]) -> dict[str, Project]:
        return {f"{project.name} ({project.key})": project for project in projects}

    @staticmethod
    def sort_by_issue_key(issue: Issue):
        try:
            return int(issue.key.split("-")[-1])
        except (AttributeError, ValueError, IndexError):
            return float("inf")  # Push invalid/malformed keys to the end

    def _fetch_baseline_field(self, project_key: str) -> Field | None:
        issue_fields = self.jira_client.fetch_project_issue_fields(project_key)
        for field in issue_fields:
            field_id = get_field_id(field)
            if self.config.baseline_field in (field_id, field.name):
                return field
        logger.warning(
            f"Configured baseline_field '{self.config.baseline_field}' not found in project {project_key}"  # noqa: E501
        )
        return None

    def _fetch_baselines_for_project(self, project: str) -> list[str]:
        project_key = self.projects[project].key
        baseline_field = self._get_config_value("baseline_field", project)

        if baseline_field.lower() == "fixversions":
            baselines = self.jira_client.fetch_project_versions(project_key)
        elif baseline_field.lower() == "sprint":
            baselines = self._fetch_sprint_baselines(project_key)
        else:
            baseline_field_obj = self._fetch_baseline_field(project_key)
            if baseline_field_obj:
                if is_version_type_field(baseline_field_obj):
                    baselines = self.jira_client.fetch_project_versions(project_key)
                else:
                    allowed_values = getattr(baseline_field_obj, "allowedValues", []) or []
                    baselines = [
                        av.get("name") or av.get("value") or str(av) for av in allowed_values
                    ]
            else:
                logger.warning(f"Baseline field not found for project {project}")
                baselines = []
        self._baselines[project] = baselines
        return baselines

    def _fetch_sprint_baselines(self, project_key: str) -> list[str]:
        baselines = []
        boards = self.jira_client.fetch_project_boards(project_key)
        scrum_boards = [board for board in boards if board.type == "scrum"]
        for board in scrum_boards:
            sprints = self.jira_client.fetch_sprints(board.id)
            for sprint in sprints:
                baselines.append(sprint.name)
        return baselines

    def _get_baselines_for_project(self, project: str) -> list[str]:
        if not self._baselines or project not in self._baselines:
            # Cache miss: fetch baselines
            self._fetch_baselines_for_project(project)
        return self._baselines.get(project, [])

    def _prepare_fields(
        self, fields: str | None = None, project: str | None = None, baseline: str | None = None
    ) -> str | None:
        if fields and fields != "*all":
            fields_set = {field.strip() for field in fields.split(",")}
            if project:
                fields_set.add("project")
            if baseline:
                fields_set.add(self.config.baseline_field)
            fields_set.add("issuetype")
            return ",".join(fields_set)
        return fields

    def _validate_issue(
        self, issue: Issue, project: str | None = None, baseline: str | None = None
    ):
        """
        Validate that a Jira issue meets expected constraints.
        Checks that the issue:
        - belongs to the specified project (if provided),
        - is associated with the specified baseline (if provided and not "Current Baseline"),
        Args:
            issue: The Jira issue to validate.
            project: Optional project identifier; if provided the issue must belong to this project.
            baseline: Optional baseline name; if provided (and not "Current Baseline") the issue must be in this baseline.
        Raises:
            NotFound: If any of the above validations fail.
        """  # noqa: E501
        # If project is specified, check if the issue belongs to the specified project
        if project:
            project_key = self.projects[project].key
            if issue.fields.project.key != project_key:
                raise NotFound("Requirement not found")

        # If baseline is specified, check if the issue belongs to the specified baseline
        if baseline:
            issue_baselines = extract_baselines_from_issue(issue, self.config.baseline_field)
            if baseline != "Current Baseline" and baseline not in issue_baselines:
                raise NotFound("Requirement not found")

    def _normalize_field_for_jql(self, field_name: str) -> str:
        """
        Normalize Jira field names to their canonical JQL equivalents.

        Currently handles known special cases like converting 'fixVersions' to 'fixVersion'.

        Args:
            field_name (str): The field name to normalize.

        Returns:
            str: The normalized field name for JQL queries.
        """
        if field_name.lower() == "fixversions":
            return "fixVersion"
        return field_name

    def _build_issues_jql(self, project: str, baseline: str, extra_jql: str | None = None) -> str:
        jql_query = self._build_baseline_jql(project, baseline)
        if extra_jql:
            jql_query += f" AND {extra_jql}"
        return jql_query

    def _build_baseline_jql(self, project: str, baseline: str) -> str:
        """
        Build the JQL query string for filtering issues by baseline.

        If the baseline is "Current Baseline", uses the current_baseline_jql template for the project.
        Otherwise, uses the baseline_jql template for the project.

        The returned string should be a valid JQL clause, e.g. 'fixVersion = "{baseline}"'.
        The template is formatted with the project name and baseline name.

        Args:
            project (str): The project name.
            baseline (str): The baseline name.

        Returns:
            str: The formatted JQL clause.
        """  # noqa: E501
        if baseline == "Current Baseline":
            jql_template = self._get_config_value("current_baseline_jql", project)
        else:
            jql_template = self._get_config_value("baseline_jql", project)
        project_key = self.projects[project].key
        return str(jql_template).format(project=project_key, baseline=baseline)

    def _build_requirement_nodes(
        self, issues: list[Issue], project: str
    ) -> dict[str, RequirementObjectNode]:
        """Convert issues into requirement nodes."""
        requirement_nodes = {}
        for issue in issues:
            is_requirement = True  # TODO: fix ?
            req_node = build_requirementobjectnode_from_issue(
                project=project,
                issue=issue,
                owner_field_name=self._get_config_value("owner", project),
                config=self.config,
                is_requirement=is_requirement,
            )
            requirement_nodes[issue.key] = req_node
        return requirement_nodes

    def _build_requirement_tree(
        self, project: str, issues: list[Issue], requirement_nodes: dict[str, RequirementObjectNode]
    ) -> dict[str, RequirementObjectNode]:
        """Link requirement nodes into a tree structure."""
        requirement_tree = {}
        try:
            for issue in issues:
                parent_obj = getattr(issue.fields, "parent", None)
                if not parent_obj:
                    requirement_tree[issue.key] = requirement_nodes[issue.key]
                    continue

                parent_key = parent_obj.key
                if parent_key not in requirement_nodes:
                    try:
                        fields = self._prepare_fields("summary,created,creator")
                        parent_issue = self.jira_client.fetch_issue(
                            parent_key, fields=fields, expand="changelog"
                        )
                        if not parent_issue:
                            raise ValueError(f"Parent issue {parent_key} not found")
                        requirement_nodes[parent_key] = build_requirementobjectnode_from_issue(
                            project=project,
                            issue=parent_issue,
                            owner_field_name=self._get_config_value("owner", project),
                            config=self.config,
                            is_requirement=not self._is_requirement_group_issue(
                                parent_issue, project
                            ),
                        )
                        parent = requirement_nodes[parent_key]
                        requirement_tree[parent_key] = parent
                    except Exception as e:
                        logger.warning(
                            f"Parent issue {parent_key} of issue {issue.key} could not be fetched: {e}"  # noqa: E501
                        )
                        continue
                else:
                    parent = requirement_nodes[parent_key]
                parent.children = parent.children or []
                parent.children.append(requirement_nodes[issue.key])

        except Exception as e:
            logger.error(f"Error building requirement tree: {e}")
            return {}

        return requirement_tree

    def _get_config_value(self, attr: str, project: str | None = None) -> str:
        """
        Retrieve a configuration value, optionally project-specific, falling back to global config.
        Args:
            attr (str): The attribute name to retrieve.
            project (str | None): The project name, if any.
        Returns:
            The value of the attribute, or None if not found.
        """
        if project and project in self.config.projects:
            project_config = self.config.projects[project]
            value = getattr(project_config, attr, None)
            if value is not None:
                return value  # type: ignore
        return getattr(self.config, attr, None)  # type: ignore

    def _is_requirement_group_issue(self, issue: Issue, project: str | None = None) -> bool:
        return issue.fields.issuetype.name in self._get_config_value(
            "requirement_group_types", project
        )
