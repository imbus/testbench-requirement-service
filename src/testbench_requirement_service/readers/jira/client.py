from typing import Any

try:
    from jira import JIRA, JIRAError
    from jira.resources import Board, Field, Issue, Project, Sprint
except ImportError:
    pass
from sanic.log import logger

from testbench_requirement_service.readers.jira.config import JiraRequirementReaderConfig


class JiraClient:
    def __init__(self, config: JiraRequirementReaderConfig):
        self.config = config
        self.jira = self._connect()
        # The following flags determine which Jira API endpoints to use
        self.use_issuetypes_endpoint = (not self.jira._is_cloud) and (
            self.jira._version >= (8, 4, 0)
        )
        self.use_manual_pagination = not self.jira._is_cloud and self.jira._version < (8, 4, 0)

    def _connect(self) -> JIRA:
        if self.config.auth_type == "basic":
            return JIRA(
                server=self.config.server_url,
                basic_auth=(self.config.username or "", self.config.api_token or ""),
            )
        if self.config.auth_type == "token":
            return JIRA(server=self.config.server_url, token_auth=self.config.token)
        if self.config.auth_type == "oauth":
            return JIRA(
                oauth={
                    "access_token": self.config.access_token,
                    "access_token_secret": self.config.access_token_secret,
                    "consumer_key": self.config.consumer_key,
                    "key_cert": self.config.key_cert,
                }
            )
        raise NotImplementedError(f"Unsupported auth_type {self.config.auth_type}")

    def fetch_issue(
        self,
        issue_id: str,
        fields: str | None = None,
        expand: str | None = None,
        properties: str | None = None,
    ) -> Issue | None:
        try:
            return self.jira.issue(issue_id, fields=fields, expand=expand, properties=properties)
        except JIRAError as e:
            logger.debug(f"Error fetching issue {issue_id}: {e}")
            return None

    def fetch_issues(
        self,
        jql_query: str,
        fields: str | None = "*all",
        expand: str | None = None,
        properties: str | None = None,
    ) -> list[Issue]:
        try:
            if not self.use_manual_pagination:
                return list(
                    self.jira.search_issues(
                        jql_query,
                        maxResults=1000,
                        fields=fields,
                        expand=expand,
                        properties=properties,
                    )
                )
            # Manual pagination for older Jira Server versions
            start_at = 0
            max_results = 1000
            issues: list[Issue] = []
            while True:
                chunk = self.jira.search_issues(
                    jql_query,
                    startAt=start_at,
                    maxResults=max_results,
                    fields=fields,
                    expand=expand,
                    properties=properties,
                )
                issues.extend(chunk)
                if len(chunk) < max_results:
                    # No more pages
                    break
                start_at += max_results
            return issues
        except JIRAError as e:
            logger.debug(f"Error fetching issues: {e}")
            return []

    def fetch_projects(self) -> list[Project]:
        try:
            return self.jira.projects()
        except JIRAError as e:
            logger.debug(f"Error fetching projects: {e}")
            return []

    def fetch_project_issue_fields(self, project_key: str) -> list[Field]:
        fields_dict: dict[str, Field] = {}

        try:
            if self.use_issuetypes_endpoint:
                logger.debug("_fetch_project_issue_fields: Use issuetypes endpoint")
                issue_types = self.jira.project_issue_types(project_key, maxResults=100)
                for issue_type in issue_types:
                    try:
                        fields_list = self.jira.project_issue_fields(
                            project_key, issue_type=issue_type.id, maxResults=100
                        )
                        for field in fields_list:
                            fields_dict[field.id] = field
                    except Exception as e:
                        logger.warning(
                            f"Error fetching issue fields for issue type {issue_type.id}: {e}"
                        )
            else:
                logger.debug("_fetch_project_issue_fields: Use createmeta endpoint")
                createmeta = self.jira.createmeta(project_key, expand="projects.issuetypes.fields")
                issue_types = createmeta["projects"][0]["issuetypes"]
                for issue_type in issue_types:
                    for field_id, field_data in issue_type["fields"].items():
                        fields_dict[field_id] = Field(
                            options=self.jira._options, session=self.jira._session, raw=field_data
                        )
        except Exception as e:
            logger.debug(f"Error fetching issue fields for project {project_key}: {e}")
            raise

        return list(fields_dict.values())

    def fetch_project_versions(self, project_key: str) -> list[str]:
        try:
            versions = self.jira.project_versions(project_key)
            if not versions:
                return []
            return [version.name for version in versions if version.name]
        except JIRAError as e:
            logger.debug(f"Error fetching project versions for {project_key}: {e}")
            return []

    def fetch_project_boards(self, project_key: str) -> list[Board]:
        try:
            return self.jira.boards(projectKeyOrID=project_key)  # type: ignore[no-any-return]
        except JIRAError as e:
            logger.debug(f"Error fetching boards for project {project_key}: {e}")
            return []

    def fetch_sprints(self, board_id: int) -> list[Sprint]:
        try:
            return self.jira.sprints(board_id)  # type: ignore[no-any-return]
        except JIRAError as e:
            logger.debug(f"Error fetching sprints for board {board_id}: {e}")
            return []

    def fetch_sprint_by_name(self, project_key: str, sprint_name: str) -> Sprint | None:
        boards = self.fetch_project_boards(project_key)
        scrum_boards = [board for board in boards if board.type == "scrum"]
        for board in scrum_boards:
            sprints = self.fetch_sprints(board.id)
            for sprint in sprints:
                if sprint.name == sprint_name:
                    return sprint
        logger.warning(f"Sprint '{sprint_name}' not found in project '{project_key}'")
        return None

    def fetch_all_custom_fields(self) -> list[dict[str, Any]]:
        try:
            return [
                field
                for field in self.jira.fields()
                if field.get("id", "").startswith("customfield_")
            ]
        except JIRAError as e:
            logger.debug(f"Error fetching custom fields: {e}")
            return []
