from http import HTTPStatus
from typing import Any

from jira import JIRA, JIRAError
from jira.resources import (
    Board,
    Field,
    Issue,
    Project,
    Sprint,
    dict2resource,
)

from testbench_requirement_service.log import logger
from testbench_requirement_service.readers.jira.config import JiraRequirementReaderConfig
from testbench_requirement_service.utils.cache import TTLCache

DEFAULT_MAX_RESULTS = 100
DEFAULT_CHUNK_SIZE = 100

_JIRA_CLOUD_API3_BASE = "{server}/rest/api/3/{path}"

_EPIC_LINK_SCHEMA_KEY = "com.pyxis.greenhopper.jira:gh-epic-link"
_PARENT_LINK_SCHEMA_KEY = "com.atlassian.jpo:jpo-custom-field-parent"


def _chunks(lst: list, n: int):
    """Yield successive n-sized chunks from a list."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


class JiraClient:
    def __init__(self, config: JiraRequirementReaderConfig):
        self.config = config
        self.jira = self._connect()
        self._fields_cache: TTLCache[list[dict[str, Any]]] = TTLCache(ttl=config.cache_ttl)
        # The following flags determine which Jira API endpoints to use
        self.use_issuetypes_endpoint = not self.jira._is_cloud and self.jira._version >= (8, 4, 0)
        self.use_manual_pagination = not self.jira._is_cloud
        # Parent link fields for Server/DC compatibility (lazy-loaded)
        self._epic_link_field_id: str | None = None
        self._parent_link_field_id: str | None = None
        if not self.jira._is_cloud:
            self._init_parent_link_fields()

    def _connect(self) -> JIRA:
        try:
            options: dict[str, Any] = {"verify": self.config.ssl_verify}
            if self.config.client_cert is not None:
                options["client_cert"] = self.config.client_cert

            if self.config.auth_type == "basic":
                return JIRA(
                    server=self.config.server_url,
                    options=options,
                    basic_auth=(self.config.username or "", self.config.password or ""),
                    max_retries=self.config.max_retries,
                    timeout=self.config.timeout,
                )
            if self.config.auth_type == "token":
                return JIRA(
                    server=self.config.server_url,
                    options=options,
                    token_auth=self.config.token,
                    max_retries=self.config.max_retries,
                    timeout=self.config.timeout,
                )
            if self.config.auth_type == "oauth1":
                return JIRA(
                    server=self.config.server_url,
                    options=options,
                    oauth={
                        "access_token": self.config.oauth1_access_token,
                        "access_token_secret": self.config.oauth1_access_token_secret,
                        "consumer_key": self.config.oauth1_consumer_key,
                        "key_cert": self.config.oauth1_key_cert,
                    },
                    max_retries=self.config.max_retries,
                    timeout=self.config.timeout,
                )
            raise NotImplementedError(f"Unsupported auth_type {self.config.auth_type}")
        except Exception as e:
            status_code = getattr(e, "status_code", None)
            detail = f"HTTP {status_code}: {e}" if status_code else f"{type(e).__name__}: {e}"
            raise ConnectionError(
                f"Could not connect to Jira at '{self.config.server_url}' "
                f"(auth_type='{self.config.auth_type}'): {detail}"
            ) from e

    def _init_parent_link_fields(self):
        """
        Initialize field IDs for Epic Link and Parent Link custom fields.
        Handles Jira Server/DC instances where parent relationships may use custom fields.

        Lookup priority:
        1. schema.custom key (translation-safe, rename-safe, plugin-defined)
        2. field name match (fallback for old/non-standard instances)
        """
        try:
            for field in self.fetch_issue_fields():
                schema_custom = field.get("schema", {}).get("custom", "")
                field_name = field.get("name", "").lower()
                field_id = field.get("id", "")

                # --- Epic Link ---
                if schema_custom == _EPIC_LINK_SCHEMA_KEY:
                    self._epic_link_field_id = field_id
                    logger.debug(f"Found Epic Link field by schema key: {field_id}")
                elif not self._epic_link_field_id and "epic link" in field_name:
                    self._epic_link_field_id = field_id
                    logger.debug(f"Found Epic Link field by name fallback: {field_id}")

                # --- Parent Link ---
                if schema_custom == _PARENT_LINK_SCHEMA_KEY:
                    self._parent_link_field_id = field_id
                    logger.debug(f"Found Parent Link field by schema key: {field_id}")
                elif not self._parent_link_field_id and "parent link" in field_name:
                    self._parent_link_field_id = field_id
                    logger.debug(f"Found Parent Link field by name fallback: {field_id}")
        except Exception as e:
            logger.warning(
                f"Could not initialize parent link fields: {e}. "
                "Epic/Parent Link fields will be unavailable."
            )

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
            if e.status_code == HTTPStatus.NOT_FOUND:
                logger.debug(f"Issue {issue_id} not found ({HTTPStatus.NOT_FOUND})")
            else:
                logger.warning(f"Error fetching issue {issue_id}: HTTP {e.status_code}")
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

        all_issues: list[Issue] = []

        for batch in _chunks(issue_keys, chunk_size):
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
                    chunk = list(issues_chunk)
                    issues.extend(chunk)
                    if len(chunk) < max_results:
                        # No more pages
                        break
                    start_at += len(chunk)
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
            logger.warning(f"Error fetching issues by JQL '{jql_query}': {e}")
            return []

    def fetch_projects(self) -> list[Project]:
        try:
            return self.jira.projects()
        except JIRAError as e:
            logger.warning(f"Error fetching projects: {e}")
            return []

    def _fetch_fields_for_issue_type(self, project_key: str, issue_type_id: str) -> list[Field]:
        """Fetch all fields for a single issue type using pagination."""
        fields: list[Field] = []
        start_at = 0
        while True:
            fields_chunk = self.jira.project_issue_fields(
                project_key,
                issue_type=issue_type_id,
                startAt=start_at,
                maxResults=DEFAULT_MAX_RESULTS,
            )
            fields.extend(fields_chunk)
            returned = len(fields_chunk)
            if returned < DEFAULT_MAX_RESULTS:
                break
            start_at += returned
        return fields

    def _fetch_fields_via_issuetypes_endpoint(self, project_key: str) -> dict[str, Field]:
        """Fetch all project fields using the issuetypes endpoint with pagination.

        Uses a dict keyed by field ID to deduplicate fields that appear across multiple issue types.
        """
        fields_dict: dict[str, Field] = {}
        start_at = 0
        while True:
            issue_types_chunk = self.jira.project_issue_types(
                project_key, startAt=start_at, maxResults=DEFAULT_MAX_RESULTS
            )
            for issue_type in issue_types_chunk:
                try:
                    for field in self._fetch_fields_for_issue_type(project_key, issue_type.id):
                        fields_dict[field.fieldId] = field
                except Exception as e:
                    logger.warning(
                        f"Error fetching issue fields for issue type {issue_type.id}: {e}"
                    )
            returned = len(issue_types_chunk)
            if returned < DEFAULT_MAX_RESULTS:
                break
            start_at += returned
        return fields_dict

    def _fetch_fields_via_createmeta_endpoint(self, project_key: str) -> dict[str, Field]:
        """Fetch all project fields using the legacy createmeta endpoint."""
        fields_dict: dict[str, Field] = {}
        createmeta = self.jira.createmeta(project_key, expand="projects.issuetypes.fields")
        projects = createmeta.get("projects", [])
        if not projects:
            logger.debug(f"No projects found in createmeta response for {project_key}")
            return {}
        for issue_type in projects[0]["issuetypes"]:
            try:
                for field_id, field_data in issue_type["fields"].items():
                    fields_dict[field_id] = Field(
                        options=self.jira._options,
                        session=self.jira._session,
                        raw=field_data,
                    )
            except Exception as e:
                issue_type_id = issue_type.get("id", "unknown")
                logger.warning(f"Error fetching issue fields for issue type {issue_type_id}: {e}")
        return fields_dict

    def fetch_project_issue_fields(self, project_key: str) -> list[Field]:
        if self.use_issuetypes_endpoint:
            logger.debug("_fetch_project_issue_fields: Use issuetypes endpoint")
            fields_dict = self._fetch_fields_via_issuetypes_endpoint(project_key)
        else:
            logger.debug("_fetch_project_issue_fields: Use createmeta endpoint")
            fields_dict = self._fetch_fields_via_createmeta_endpoint(project_key)
        return list(fields_dict.values())

    def fetch_project_versions(self, project_key: str) -> list[str]:
        try:
            versions = self.jira.project_versions(project_key)
            if not versions:
                return []
            return [version.name for version in versions if version.name]
        except JIRAError as e:
            logger.warning(f"Error fetching project versions for {project_key}: {e}")
            return []

    def fetch_project_boards(self, project_key: str) -> list[Board]:
        try:
            return self.jira.boards(projectKeyOrID=project_key)  # type: ignore[no-any-return]
        except JIRAError as e:
            logger.warning(f"Error fetching boards for project {project_key}: {e}")
            return []

    def fetch_sprints(self, board_id: int) -> list[Sprint]:
        try:
            return self.jira.sprints(board_id)  # type: ignore[no-any-return]
        except JIRAError as e:
            logger.warning(f"Error fetching sprints for board {board_id}: {e}")
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

    def fetch_issue_fields(self) -> list[dict[str, Any]]:
        """Return all issue fields, refreshing automatically when the cache expires."""
        cached = self._fields_cache.get()
        if cached is not None:
            return cached
        try:
            fields = self.jira.fields()
            self._fields_cache.set(fields)
            return fields
        except JIRAError as e:
            logger.warning(f"Error fetching issue fields: {e}")
            return self._fields_cache.stale_value or []

    def fetch_custom_issue_fields(self) -> list[dict[str, Any]]:
        """Return all custom fields, derived from the cached issue fields."""
        return [
            field
            for field in self.fetch_issue_fields()
            if field.get("id", "").startswith("customfield_")
        ]

    def _fetch_changelog_via_endpoint(self, issue_id_or_key: str) -> list[Any]:
        """
        Fetch changelog histories via the dedicated paginated endpoint.

        ``GET /rest/api/2/issue/{key}/changelog`` — Jira Cloud only.
        Raises on any error; callers are responsible for exception handling.
        """
        max_results = 100
        histories: list[Any] = []
        start_at = 0

        while True:
            page = self.jira._get_json(
                f"issue/{issue_id_or_key}/changelog",
                params={"startAt": start_at, "maxResults": max_results},
            )
            if "values" not in page and "histories" not in page:
                raise ValueError(f"Unexpected /changelog response (keys: {list(page.keys())})")
            page_histories = page.get("values") or page.get("histories") or []
            if not page_histories:
                break
            histories.extend(dict2resource(h) for h in page_histories)
            start_at += len(page_histories)
            total = page.get("total")
            if page.get("isLast", False) or (total is not None and start_at >= total):
                break
            if len(page_histories) < max_results:
                break

        return histories

    def _fetch_changelog_via_expand(self, issue_id_or_key: str) -> list[Any]:
        """
        Fetch changelog histories via ``expand=changelog`` on the issue resource.

        ``GET /rest/api/2/issue/{key}?expand=changelog`` — works on all Jira
        instance types but is truncated to ~100 entries (no pagination).
        Raises on any error; callers are responsible for exception handling.
        """
        issue = self.fetch_issue(issue_id_or_key, expand="changelog")
        if issue is None:
            return []
        changelog = getattr(issue, "changelog", None)
        if changelog is None:
            return []
        raw_histories = getattr(changelog, "histories", [])
        total = getattr(changelog, "total", None)
        if total is not None and len(raw_histories) < total:
            logger.warning(
                "Changelog for %s is truncated (%d of %d entries). Some history may be incomplete.",
                issue_id_or_key,
                len(raw_histories),
                total,
            )
        return list(raw_histories)

    def fetch_issue_changelog_histories(self, issue_id_or_key: str) -> list[Any]:
        """
        Fetch changelog histories for a single issue.

        Routes by instance type:
        - **Jira Cloud**: paginated ``GET /rest/api/2/issue/{key}/changelog``.
        - **Jira Server/DC**: ``GET /rest/api/2/issue/{key}?expand=changelog``
          (truncated to ~100 entries; no pagination available).

        Returns an empty list on failure.
        """
        try:
            if self.jira._is_cloud:
                return self._fetch_changelog_via_endpoint(issue_id_or_key)
            return self._fetch_changelog_via_expand(issue_id_or_key)
        except Exception as e:
            logger.debug("Failed to fetch changelog for %s: %s", issue_id_or_key, e)
            return []

    def bulk_fetch_issue_changelog_histories(
        self, issue_ids: list[str], batch_size: int = 100
    ) -> dict[str, list[Any]]:
        """
        Fetch changelog histories for given issues in batches using the Jira Cloud
        bulk changelog endpoint (``POST /rest/api/3/changelog/bulkfetch``), handling
        pagination with ``nextPageToken`` for each batch.  This endpoint is
        **Jira Cloud-only** and is not available on Jira Server/DC.

        Args:
            issue_ids: List of numeric issue IDs (not keys) to fetch changelog for.
            batch_size: Number of issues per request (max depends on Jira instance).

        Returns:
            Dictionary mapping numeric issue ID to list of resource objects.
        """
        issue_changelogs: dict[str, list[Any]] = {}

        try:
            for batch in _chunks(issue_ids, batch_size):
                next_page_token: str | None = None

                while True:
                    payload: dict[str, Any] = {"issueIdsOrKeys": batch}
                    if next_page_token:
                        payload["nextPageToken"] = next_page_token

                    # Bulk changelog is Cloud-only and only available under api/3.
                    page_data = self.jira._get_json(
                        "changelog/bulkfetch",
                        params=payload,
                        use_post=True,
                        base=_JIRA_CLOUD_API3_BASE,
                    )

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

        except Exception as e:
            logger.warning(
                f"Error bulk fetching issue changelog histories: {e}. "
                f"Returning {len(issue_changelogs)} partial result(s)."
            )

        return issue_changelogs

    def fetch_changelog_histories(
        self, issues: list[Issue], batch_size: int = 100
    ) -> dict[str, list[Any]]:
        """
        Fetch changelog histories for multiple issues, keyed by issue key.

        On Jira Cloud, attempts a bulk fetch first using numeric IDs (as required by the
        bulk API), then remaps the response back to issue keys internally.
        On Jira Server/DC, fetches per-issue using issue keys directly.
        Falls back to per-issue fetch if bulk fetch fails or returns empty.

        Args:
            issues: List of Jira Issue objects.
            batch_size: Batch size for Cloud bulk fetch calls.

        Returns:
            Dictionary mapping issue key to list of resource objects.
        """
        if not issues:
            return {}

        issue_changelogs: dict[str, list[Any]] = {}

        # On Cloud, use the efficient bulk endpoint (requires numeric IDs; remapped to keys here).
        # Fall through to per-issue for any issues missing from the bulk result.
        if self.jira._is_cloud:
            try:
                id_to_key = {issue.id: issue.key for issue in issues}
                changelog_histories = self.bulk_fetch_issue_changelog_histories(
                    list(id_to_key.keys()), batch_size=batch_size
                )
                if changelog_histories:
                    issue_changelogs = {
                        id_to_key[issue_id]: histories
                        for issue_id, histories in changelog_histories.items()
                        if issue_id in id_to_key
                    }
                    # Check for any issues whose changelogs were not returned by the bulk endpoint
                    missing = [i for i in issues if i.key not in issue_changelogs]
                    if not missing:
                        return issue_changelogs
                    logger.debug(
                        "Bulk fetch missing %d issue(s), fetching per-issue.", len(missing)
                    )
                    issues = missing
                else:
                    logger.debug("Bulk fetch returned empty, falling back to per-issue fetch.")
            except Exception as e:
                logger.debug("Bulk fetch failed: %s. Falling back to per-issue fetch.", e)

        # Per-issue fetch using issue key (works on all Jira instance types)
        for issue in issues:
            issue_changelogs[issue.key] = self.fetch_issue_changelog_histories(issue.key)

        return issue_changelogs

    def get_parent_key(self, issue: Issue) -> str | None:
        """
        Get the parent key of an issue, handling both Cloud and Server/DC instances.

        For Jira Cloud and newer Server versions, uses the standard 'parent' field.
        For older Jira Server/DC versions, falls back to 'Epic Link' or 'Parent Link' custom fields.

        Args:
            issue: The Jira issue to get the parent key from.

        Returns:
            The parent issue key if found, None otherwise.
        """
        # Try standard parent field first (works for Cloud and newer Server versions)
        parent_obj = getattr(issue.fields, "parent", None)
        if parent_obj:
            return getattr(parent_obj, "key", None)

        # For older Server/DC versions, check Epic Link and Parent Link custom fields
        if self._epic_link_field_id:
            epic_link = getattr(issue.fields, self._epic_link_field_id, None)
            if epic_link:
                if isinstance(epic_link, str):
                    return epic_link
                return getattr(epic_link, "key", None)

        if self._parent_link_field_id:
            parent_link = getattr(issue.fields, self._parent_link_field_id, None)
            if parent_link:
                if isinstance(parent_link, str):
                    return parent_link
                return getattr(parent_link, "key", None)

        return None
