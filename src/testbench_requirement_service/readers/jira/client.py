from typing import Any

try:
    from jira import JIRA, JIRAError
    from jira.resources import Board, Field, Issue, Project, Sprint, dict2resource
except ImportError:
    pass

from testbench_requirement_service.log import logger
from testbench_requirement_service.readers.jira.config import JiraRequirementReaderConfig

DEFAULT_MAX_RESULTS = 100
DEFAULT_CHUNK_SIZE = 100


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

    def fetch_issues(  # noqa: PLR0913
        self,
        issue_keys: list[str],
        base_jql: str | None = None,
        fields: str | None = "*all",
        expand: str | None = None,
        properties: str | None = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> list[Issue]:
        """Fetch issues for a list of keys, optionally combined with base JQL.

        Example base_jql: "project = ABC AND status = Done".
        """

        if not issue_keys:
            return []

        def chunks(lst: list[str], n: int):
            for i in range(0, len(lst), n):
                yield lst[i : i + n]

        all_issues: list[Issue] = []

        try:
            for batch in chunks(issue_keys, chunk_size):
                keys_str = ",".join(batch)
                if base_jql:
                    jql = f"({base_jql}) AND issuekey IN ({keys_str})"
                else:
                    jql = f"issuekey IN ({keys_str})"

                batch_issues = self.fetch_issues_by_jql(
                    jql_query=jql,
                    fields=fields,
                    expand=expand,
                    properties=properties,
                    max_results=max_results,
                )
                all_issues.extend(batch_issues)

            return all_issues
        except JIRAError as e:
            logger.debug(f"Error fetching issues by keys: {e}")
            return []

    def fetch_issues_by_jql(
        self,
        jql_query: str,
        fields: str | None = "*all",
        expand: str | None = None,
        properties: str | None = None,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> list[Issue]:
        try:
            issues: list[Issue] = []

            if self.use_manual_pagination:
                start_at = 0
                while True:
                    issues_chunk = self.jira.search_issues(
                        jql_query,
                        startAt=start_at,
                        maxResults=max_results,
                        fields=fields,
                        expand=expand,
                        properties=properties,
                    )
                    issues.extend(list(issues_chunk))
                    if len(issues_chunk) < max_results:
                        # No more pages
                        break
                    start_at += max_results
            else:
                next_page_token = None
                while True:
                    issues_chunk = self.jira.enhanced_search_issues(
                        jql_str=jql_query,
                        nextPageToken=next_page_token,
                        maxResults=max_results,
                        fields=fields,
                        expand=expand,
                        properties=properties,
                    )
                    issues.extend(list(issues_chunk))
                    if not issues_chunk.nextPageToken:
                        break
                    next_page_token = issues_chunk.nextPageToken
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

    def fetch_issue_changelog_histories(self, issue_id: str) -> list[Any]:
        """
        Fetch the full changelog histories list for a single issue using pagination.

        Args:
            issue_id: Issue ID string.

        Returns:
            A list of resource objects with dotted-access support for all nested attributes,
            containing the complete changelog histories merged from all pages.
        """
        url = self.jira._get_url(f"issue/{issue_id}/changelog")
        start_at = 0
        max_results = 100
        all_histories: list[Any] = []

        try:
            while True:
                params = {"startAt": start_at, "maxResults": max_results}
                response = self.jira._session.get(url, params=params)
                response.raise_for_status()
                page_data = response.json()

                # Convert raw dicts to resource objects with dotted access (recursive)
                histories = page_data.get("histories", [])
                all_histories.extend(dict2resource(h) for h in histories)

                start_at += max_results
                if start_at >= page_data.get("total", 0):
                    break

            return all_histories

        except Exception as e:
            logger.debug(f"Error fetching changelog histories for issue {issue_id}: {e}")
            return []

    def bulk_fetch_issue_changelog_histories(  # noqa: C901
        self, issue_ids: list[str], batch_size: int = 100
    ) -> dict[str, list[Any]]:
        """
        Fetch changelog histories for given issues in batches using /rest/api/3/changelog/bulkfetch,
        handling pagination with nextPageToken for each batch.

        Args:
            issue_ids: List of issue IDs to fetch changelog histories for.
            batch_size: Number of issues per bulkfetch request (max depends on Jira instance).

        Returns:
            Dictionary mapping issue ID to list of resource objects with dotted-access support
            for all nested attributes.
        """

        def chunks(lst, n):
            """Yield successive n-sized chunks from list."""
            for i in range(0, len(lst), n):
                yield lst[i : i + n]

        url = self.jira._get_url("changelog/bulkfetch")
        issue_changelogs: dict[str, list[Any]] = {}

        try:
            for batch in chunks(issue_ids, batch_size):
                next_page_token: str | None = None

                while True:
                    payload = {"issueIdsOrKeys": batch}
                    if next_page_token:
                        payload["nextPageToken"] = next_page_token

                    response = self.jira._session.post(url, json=payload)
                    response.raise_for_status()
                    page_data = response.json()

                    # Process each issue's changelog histories directly
                    for issue_changelog in page_data.get("issueChangeLogs", []):
                        issue_id = issue_changelog.get("issueId")
                        if not issue_id:
                            continue

                        changelog_histories = issue_changelog.get("changeHistories", [])
                        converted_histories = [dict2resource(h) for h in changelog_histories]

                        if issue_id in issue_changelogs:
                            issue_changelogs[issue_id].extend(converted_histories)
                        else:
                            issue_changelogs[issue_id] = converted_histories

                    next_page_token = page_data.get("nextPageToken")
                    if not next_page_token:
                        break

            return issue_changelogs

        except Exception as e:
            logger.debug(f"Error bulk fetching issue changelog histories: {e}")
            return {}

    def fetch_changelog_histories(
        self, issue_ids: list[str], batch_size: int = 100
    ) -> dict[str, list[Any]]:
        """
        Fetch changelog histories for multiple issues efficiently.

        Attempts bulk fetch in batches first. If bulk fetch fails, falls back
        to per-issue paginated fetches.

        Args:
            issue_ids: List of issue IDs.
            batch_size: Batch size for bulk fetch calls.

        Returns:
            Dictionary mapping issue ID to list of resource objects with dotted-access support
            for all nested attributes.
        """
        issue_changelogs = {}

        try:
            # Attempt bulk fetch first
            issue_changelogs = self.bulk_fetch_issue_changelog_histories(
                issue_ids, batch_size=batch_size
            )
            if issue_changelogs:
                return issue_changelogs  # Return if bulk fetch succeeded
            logger.debug("Bulk fetch returned empty, falling back to per-issue fetch.")
        except Exception as e:
            logger.debug(f"Bulk fetch failed: {e}. Falling back to per-issue fetch.")

        # Fallback: fetch one issue at a time if bulk fails or empty
        for issue_id in issue_ids:
            try:
                histories = self.fetch_issue_changelog_histories(issue_id)
                issue_changelogs[issue_id] = histories
            except Exception as e:
                logger.debug(f"Failed to fetch changelog for issue {issue_id}: {e}")
                issue_changelogs[issue_id] = []

        return issue_changelogs
