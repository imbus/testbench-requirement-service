from __future__ import annotations

from datetime import datetime, timezone

from jira.resources import Field, Issue, Project, PropertyHolder
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
from testbench_requirement_service.readers.jira.utils import (
    build_extendedrequirementobject_from_issue,
    build_requirementobjectnode_from_issue,
    build_userdefinedattribute_objects_for_issue,
    escape_jql_value,
    extract_baselines_from_issue,
    extract_valuetype_from_issue_field,
    generate_requirement_versions,
    get_config_value,
    get_field_id,
    get_issue_version,
    is_version_type_field,
)


class JiraRequirementReader(AbstractRequirementReader):
    CONFIG_CLASS = JiraRequirementReaderConfig

    def __init__(self, config: JiraRequirementReaderConfig):
        self.config = config
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
        issues = self.jira_client.fetch_issues_by_jql(jql_query)
        if not issues:
            logger.debug(f"No issues found for project '{project}' and baseline '{baseline}'")

        issue_changelogs = self.jira_client.fetch_changelog_histories(issues)
        for issue in issues:
            self._attach_changelog(issue, issue_changelogs.get(issue.key, []))

        issues.sort(key=self.sort_by_issue_key)
        requirement_nodes = self._build_requirement_nodes(issues, project)
        requirement_tree = self._build_requirement_tree(project, issues, requirement_nodes)

        return BaselineObjectNode(
            name=baseline,
            date=datetime.now(timezone.utc),
            type="CURRENT",
            children=sorted(
                requirement_tree.values(),
                key=lambda x: (
                    (0, int(x.extendedID.split("-")[-1]))
                    if x.extendedID
                    and "-" in x.extendedID
                    and x.extendedID.split("-")[-1].isdigit()
                    else (1, x.extendedID or "")
                ),
            ),
        )

    def get_user_defined_attributes(self) -> list[UserDefinedAttribute]:
        seen: set[str] = set()
        result: list[UserDefinedAttribute] = []
        for field in self.jira_client.fetch_issue_fields():
            if field["name"] not in seen:
                seen.add(field["name"])
                result.append(
                    UserDefinedAttribute(
                        name=field["name"],
                        valueType=extract_valuetype_from_issue_field(field),
                    )
                )
        return result

    def get_all_user_defined_attributes(
        self,
        project: str,
        baseline: str,
        requirement_keys: list[RequirementKey],
        attribute_names: list[str],
    ) -> list[UserDefinedAttributeResponse]:
        if not requirement_keys:
            return []

        uda_fields = self._resolve_fields_by_name(attribute_names, project)
        issue_map = self._fetch_issue_map(requirement_keys, project, baseline, uda_fields)

        result: list[UserDefinedAttributeResponse] = []
        for req_key in requirement_keys:
            issue = issue_map.get((req_key.id, req_key.version))
            if issue is None:
                continue
            udas = build_userdefinedattribute_objects_for_issue(
                issue=issue, uda_fields=uda_fields, project=project, config=self.config
            )
            result.append(UserDefinedAttributeResponse(key=req_key, userDefinedAttributes=udas))
        return result

    def get_extended_requirement(
        self, project: str, baseline: str, key: RequirementKey
    ) -> ExtendedRequirementObject:
        fields = self._prepare_fields(
            project=project,
            baseline=baseline,
        )
        expand = "renderedFields"
        issue = self.jira_client.fetch_issue(key.id, fields=fields, expand=expand)
        if issue is None:
            raise NotFound("Requirement not found")

        self._fetch_and_attach_changelog(issue)
        all_fields = self.jira_client.fetch_issue_fields()
        issue = get_issue_version(project, issue, key, self.config, all_fields)
        requirement_object = build_requirementobjectnode_from_issue(
            issue=issue,
            project=project,
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
        issue = self.jira_client.fetch_issue(key.id, fields=fields)
        if issue is None:
            raise NotFound("Requirement not found")

        self._fetch_and_attach_changelog(issue)
        return generate_requirement_versions(project, issue, self.config)

    def _resolve_fields_by_name(self, names: list[str], project: str) -> list[Field]:
        """Return project-scoped fields matching `names`, deduplicated by name."""
        names_set = set(names)
        project_key = self.projects[project].key
        seen: set[str] = set()
        result: list[Field] = []
        for field in self.jira_client.fetch_project_issue_fields(project_key):
            if field.name in names_set and field.name not in seen:
                seen.add(field.name)
                result.append(field)
        return result

    def _fetch_issue_map(
        self,
        requirement_keys: list[RequirementKey],
        project: str,
        baseline: str,
        fields: list[Field],
    ) -> dict[tuple[str, str], Issue]:
        """Fetch issues and reconstruct each to its requested version.

        Returns:
            A mapping of ``(issue_key, version)`` to the reconstructed Issue,
            ready for field extraction.
        """
        field_ids = [get_field_id(field) for field in fields]
        issue_keys = [req_key.id for req_key in requirement_keys]
        base_jql = self._build_issues_jql(project, baseline)
        issues = self.jira_client.fetch_issues(
            issue_keys,
            base_jql,
            fields=",".join(["key", "attachment", *field_ids]),
            expand="renderedFields",
        )

        issue_changelogs = self.jira_client.fetch_changelog_histories(issues)
        for issue in issues:
            self._attach_changelog(issue, issue_changelogs.get(issue.key, []))

        all_fields = self.jira_client.fetch_issue_fields()
        issue_map: dict[str, Issue] = {issue.key: issue for issue in issues}
        versioned_map: dict[tuple[str, str], Issue] = {}
        for req_key in requirement_keys:
            key = (req_key.id, req_key.version)
            if key in versioned_map or req_key.id not in issue_map:
                continue
            versioned_map[key] = get_issue_version(
                project, issue_map[req_key.id], req_key, self.config, all_fields
            )
        return versioned_map

    def _build_project_dict(self, projects: list[Project]) -> dict[str, Project]:
        return {f"{project.name} ({project.key})": project for project in projects}

    @staticmethod
    def sort_by_issue_key(issue: Issue):
        try:
            return int(issue.key.split("-")[-1])
        except (AttributeError, ValueError, IndexError):
            return float("inf")  # Push invalid/malformed keys to the end

    def _fetch_baseline_field(self, project_key: str, field_name: str) -> Field | None:
        issue_fields = self.jira_client.fetch_project_issue_fields(project_key)
        for field in issue_fields:
            field_id = get_field_id(field)
            if field_name in (field_id, field.name):
                return field
        logger.warning(
            f"Configured baseline_field '{field_name}' not found in project {project_key}"
        )
        return None

    def _fetch_baselines_for_project(self, project: str) -> list[str]:
        project_key = self.projects[project].key
        baseline_field = get_config_value(self.config, "baseline_field", project)

        if baseline_field.lower() == "fixversions":
            baselines = self.jira_client.fetch_project_versions(project_key)
        elif baseline_field.lower() == "sprint":
            baselines = self._fetch_sprint_baselines(project_key)
        else:
            baseline_field_obj = self._fetch_baseline_field(project_key, baseline_field)
            if baseline_field_obj:
                if is_version_type_field(baseline_field_obj):
                    baselines = self.jira_client.fetch_project_versions(project_key)
                else:
                    allowed_values = getattr(baseline_field_obj, "allowedValues", []) or []
                    baselines = [
                        av.get("name") or av.get("value") or str(av) for av in allowed_values
                    ]
            else:
                logger.warning(f"Baseline field '{baseline_field}' not found for project {project}")
                baselines = []
        self._baselines[project] = baselines
        return baselines

    def _fetch_sprint_baselines(self, project_key: str) -> list[str]:
        seen: set[str] = set()
        baselines: list[str] = []
        boards = self.jira_client.fetch_project_boards(project_key)
        scrum_boards = [board for board in boards if board.type == "scrum"]
        for board in scrum_boards:
            sprints = self.jira_client.fetch_sprints(board.id)
            for sprint in sprints:
                if sprint.name not in seen:
                    seen.add(sprint.name)
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
                baseline_field = get_config_value(self.config, "baseline_field", project)
                fields_set.add(baseline_field)
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
            baseline_field = get_config_value(self.config, "baseline_field", project)
            issue_baselines = extract_baselines_from_issue(issue, baseline_field)
            if baseline != "Current Baseline" and baseline not in issue_baselines:
                raise NotFound("Requirement not found")

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
            jql_template = get_config_value(self.config, "current_baseline_jql", project)
        else:
            jql_template = get_config_value(self.config, "baseline_jql", project)
        project_key = self.projects[project].key
        return str(jql_template).format(
            project=escape_jql_value(project_key),
            baseline=escape_jql_value(baseline),
        )

    def _build_requirement_nodes(
        self, issues: list[Issue], project: str
    ) -> dict[str, RequirementObjectNode]:
        """Convert issues into requirement nodes."""
        requirement_nodes = {}
        for issue in issues:
            req_node = build_requirementobjectnode_from_issue(
                issue=issue,
                project=project,
                config=self.config,
                is_requirement=not self._is_requirement_group_issue(issue, project),
            )
            requirement_nodes[issue.key] = req_node
        return requirement_nodes

    def _build_requirement_tree(
        self, project: str, issues: list[Issue], requirement_nodes: dict[str, RequirementObjectNode]
    ) -> dict[str, RequirementObjectNode]:
        """Link requirement nodes into a tree structure."""
        requirement_tree = {}
        for issue in issues:
            parent_key = self.jira_client.get_parent_key(issue)
            if not parent_key:
                requirement_tree[issue.key] = requirement_nodes[issue.key]
                continue

            if parent_key not in requirement_nodes:
                parent_node = self._fetch_parent_requirement_node(parent_key, issue.key, project)
                if parent_node is None:
                    requirement_tree[issue.key] = requirement_nodes[issue.key]
                    continue
                requirement_nodes[parent_key] = parent_node
                requirement_tree[parent_key] = parent_node

            parent = requirement_nodes[parent_key]
            parent.children = parent.children or []
            parent.children.append(requirement_nodes[issue.key])

        return requirement_tree

    def _fetch_parent_requirement_node(
        self, parent_key: str, issue_key: str, project: str
    ) -> RequirementObjectNode | None:
        """Fetch a parent issue and build its requirement node.

        Returns the node, or `None` if the parent issue could not be fetched.
        """
        fields = self._prepare_fields("summary,created,creator")
        parent_issue = self.jira_client.fetch_issue(parent_key, fields=fields)
        if not parent_issue:
            logger.warning(f"Parent issue {parent_key} of issue {issue_key} could not be fetched")
            return None
        self._fetch_and_attach_changelog(parent_issue)
        return build_requirementobjectnode_from_issue(
            issue=parent_issue,
            project=project,
            config=self.config,
            is_requirement=not self._is_requirement_group_issue(parent_issue, project),
        )

    def _attach_changelog(self, issue: Issue, histories: list) -> None:
        """Attach pre-fetched changelog histories to an issue object."""
        changelog = getattr(issue, "changelog", None)
        if changelog is None:
            changelog = PropertyHolder()
            issue.changelog = changelog  # type: ignore[attr-defined]
        changelog.histories = histories  # type: ignore[union-attr]

    def _fetch_and_attach_changelog(self, issue: Issue) -> None:
        """Fetch full paginated changelog for an issue and attach it.

        Uses the dedicated paginated changelog endpoint to ensure all history
        entries are retrieved, avoiding the ~100 entry limit of the embedded
        ``expand=changelog`` response on Jira Cloud.
        """
        histories = self.jira_client.fetch_issue_changelog_histories(issue.key)
        self._attach_changelog(issue, histories)

    def _is_requirement_group_issue(self, issue: Issue, project: str | None = None) -> bool:
        """
        Check if an issue is a requirement group (e.g., Epic, Folder).
        Uses case-insensitive comparison to handle different Jira instance types.
        """
        issuetype = getattr(issue.fields, "issuetype", None)
        if not issuetype or not getattr(issuetype, "name", None):
            logger.debug(f"Issue {issue.key} has no issuetype field")
            return False

        issue_type_name: str = issuetype.name
        requirement_group_types: list[str] = (
            get_config_value(self.config, "requirement_group_types", project) or []
        )
        return any(issue_type_name.lower() == t.lower() for t in requirement_group_types)
