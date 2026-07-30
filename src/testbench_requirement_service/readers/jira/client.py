import math
from http import HTTPStatus
from typing import Any

import requests
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
from testbench_requirement_service.readers.jira.config import (
    AUTH_OAUTH2_2LO,
    JiraRequirementReaderConfig,
    is_oauth2,
)
from testbench_requirement_service.readers.jira.jira_oauth import (
    GRANT_CLIENT_CREDENTIALS,
    GRANT_REFRESH_TOKEN,
    JiraAuthExpiredError,
    configure_oauth2_runtime,
    get_valid_jira_token_sync,
)
from testbench_requirement_service.utils.cache import TTLCache

DEFAULT_MAX_RESULTS = 100
DEFAULT_CHUNK_SIZE = 100

_JIRA_CLOUD_API3_BASE = "{server}/rest/api/3/{path}"
_JIRA_GATEWAY_BASE = "https://api.atlassian.com/ex/jira/{cloud_id}"
_TENANT_INFO_PATH = "/_edge/tenant_info"

_EPIC_LINK_SCHEMA_KEY = "com.pyxis.greenhopper.jira:gh-epic-link"
_PARENT_LINK_SCHEMA_KEY = "com.atlassian.jpo:jpo-custom-field-parent"


def _chunks(lst: list, n: int):
    """Yield successive n-sized chunks from a list."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


class JiraClient:
    def __init__(self, config: JiraRequirementReaderConfig):
        self.config = config
        self._fields_cache: TTLCache[list[dict[str, Any]]] = TTLCache(ttl=config.cache_ttl)
        self._uses_gateway: bool = False
        self._gateway_url: str | None = None
        self._proxies: dict[str, str] | None = None
        if self.config.proxy_url:
            self._proxies = {
                "http": self.config.proxy_url,
                "https": self.config.proxy_url,
            }
        self.jira = self._connect()
        # The following flags determine which Jira API endpoints to use
        self.use_issuetypes_endpoint = not self.jira._is_cloud and self.jira._version >= (8, 4, 0)
        self.use_manual_pagination = not self.jira._is_cloud
        # Parent link fields for Server/DC compatibility (lazy-loaded)
        self._epic_link_field_id: str | None = None
        self._parent_link_field_id: str | None = None
        if not self.jira._is_cloud:
            self._init_parent_link_fields()
        logger.info(
            "Connected to Jira %s (version=%s, cloud=%s, use_issuetypes=%s)",
            self.config.server_url,
            self.jira._version,
            self.jira._is_cloud,
            self.use_issuetypes_endpoint,
        )

    @property
    def site_url(self) -> str:
        """Return the human-facing Jira site URL (always the configured server_url).

        This is the URL to use for building browser links, display URLs, and any
        URL embedded in responses shown to the user.  It is distinct from the
        internal gateway URL used when connecting via the Atlassian API gateway
        for scoped API tokens.
        """
        return self.config.server_url.rstrip("/")

    @property
    def gateway_url(self) -> str | None:
        """Return the Atlassian API gateway URL, or ``None`` when not in gateway mode.

        When set, all authenticated HTTP fetches (attachments, inline images) must
        use this URL as the base instead of ``site_url`` because scoped API tokens
        are only accepted by the gateway, not by the direct Jira Cloud site.
        """
        return self._gateway_url

    def _build_jira_options(self) -> dict[str, Any]:
        options: dict[str, Any] = {"verify": self.config.ssl_verify}
        if self.config.client_cert is not None:
            options["client_cert"] = self.config.client_cert
        if self._proxies is not None:
            options["proxies"] = self._proxies
        return options

    def _create_jira_instance(self, server: str, token_override: str | None = None) -> JIRA:
        """Create a JIRA instance against *server* using the configured auth."""
        logger.debug(
            "Creating JIRA instance for '%s' (auth_type='%s')", server, self.config.auth_type
        )
        options = self._build_jira_options()
        if self.config.auth_type == "basic":
            return JIRA(
                server=server,
                options=options,
                basic_auth=(self.config.username or "", self.config.password or ""),
                max_retries=self.config.max_retries,
                timeout=self.config.timeout,
            )
        if self.config.auth_type == "token":
            return JIRA(
                server=server,
                options=options,
                token_auth=self.config.token,
                max_retries=self.config.max_retries,
                timeout=self.config.timeout,
            )
        if self.config.auth_type == "oauth1":
            return JIRA(
                server=server,
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
        if is_oauth2(self.config.auth_type):
            token = token_override or self.config.oauth2_access_token or self.config.token
            return JIRA(
                server=server,
                options=options,
                token_auth=token,
                max_retries=self.config.max_retries,
                timeout=self.config.timeout,
            )
        raise NotImplementedError(f"Unsupported auth_type {self.config.auth_type}")

    def _verify_connection(self, jira: JIRA) -> bool:
        """Verify that *jira* can authenticate successfully by calling ``/myself``.

        The ``/myself`` endpoint is available on both Jira Cloud and Server/DC
        and requires valid authentication on both.  It is used here because the
        JIRA constructor alone is insufficient — the ``serverInfo`` endpoint used
        during construction is public and returns HTTP 200 regardless of whether
        the credentials are valid.

        Returns ``True`` on success, ``False`` on HTTP 401.  Any other error is
        re-raised so the caller can surface it as a hard connection failure.
        """
        try:
            jira.myself()
            return True
        except JIRAError as e:
            if e.status_code == HTTPStatus.UNAUTHORIZED:
                logger.debug("Connection verification returned 401 for '%s'.", jira.server_url)
                return False
            raise

    def _fetch_cloud_id(self) -> str | None:
        """Fetch the Atlassian Cloud ID for this Jira instance.

        Uses the public ``/_edge/tenant_info`` endpoint which requires no
        authentication and is available on all Jira Cloud sites (including
        those using custom domains).

        Returns the cloud ID string, or ``None`` when the request fails or
        the response does not contain the expected field.
        """
        server_url = self.config.server_url.rstrip("/")
        tenant_info_url = f"{server_url}{_TENANT_INFO_PATH}"
        try:
            response = requests.get(
                tenant_info_url,
                timeout=self.config.timeout,
                verify=self.config.ssl_verify,
                cert=self.config.client_cert,
                proxies=self._proxies,
            )
            response.raise_for_status()
            data = response.json()
            cloud_id: str | None = data.get("cloudId")
            if not cloud_id:
                logger.warning(
                    f"Tenant info response from '{tenant_info_url}' did not contain 'cloudId'. "
                    f"Response keys: {list(data.keys())}"
                )
                return None
            logger.debug(f"Fetched Atlassian Cloud ID: {cloud_id}")
            return cloud_id
        except requests.RequestException as e:
            logger.warning(f"Could not fetch Atlassian Cloud ID from '{tenant_info_url}': {e}")
            return None
        except (ValueError, KeyError) as e:
            logger.warning(
                f"Unexpected response from '{tenant_info_url}' while fetching Cloud ID: {e}"
            )
            return None

    def _connect_via_gateway(self) -> JIRA:
        """Connect to Jira Cloud through the Atlassian API gateway.

        Fetches the Cloud ID, then creates a JIRA instance against the gateway URL.

        Raises ``ConnectionError`` when the Cloud ID cannot be fetched or the
        gateway connection fails.
        """
        cloud_id = self._fetch_cloud_id()
        if not cloud_id:
            raise ConnectionError(
                f"Could not obtain Atlassian Cloud ID for '{self.config.server_url}'. "
                "Unable to attempt gateway connection for scoped API token."
            )

        gateway_url = _JIRA_GATEWAY_BASE.format(cloud_id=cloud_id)
        logger.info(
            f"Connecting to Jira via Atlassian gateway (scoped API token mode): {gateway_url}"
        )

        if is_oauth2(self.config.auth_type):
            is_2lo = self.config.auth_type == AUTH_OAUTH2_2LO
            configure_oauth2_runtime(
                grant_type=GRANT_CLIENT_CREDENTIALS if is_2lo else GRANT_REFRESH_TOKEN,
                refresh_token=None if is_2lo else self.config.oauth2_refresh_token,
                client_id=self.config.oauth2_client_id,
                client_secret=self.config.oauth2_client_secret,
                expires_at=None if is_2lo else self.config.oauth2_expires_at,
            )
            try:
                initial_oauth2_token = get_valid_jira_token_sync(is_first_call=True)
            except JiraAuthExpiredError as exc:
                raise ConnectionError(
                    "Jira OAuth2 authorization expired while establishing the initial connection. "
                    "Please re-run the setup wizard to authorize Jira OAuth2."
                ) from exc
        else:
            initial_oauth2_token = None

        jira = self._create_jira_instance(gateway_url, token_override=initial_oauth2_token)
        if is_oauth2(self.config.auth_type):
            self._patch_session_for_oauth2_token(jira._session)

        if not self._verify_connection(jira):
            raise ConnectionError(
                f"Authentication failed against the Atlassian gateway '{gateway_url}'. "
                f"Please verify your credentials for '{self.config.server_url}'."
            )

        self._uses_gateway = True
        self._gateway_url = gateway_url
        self._patch_session_for_gateway(jira._session, gateway_url)

        return jira

    def _patch_session_for_oauth2_token(self, session: Any) -> None:
        """Inject a valid OAuth2 bearer token into every Jira HTTP request."""
        original_send = session.send

        def _oauth2_send(request: Any, **kwargs: Any) -> Any:
            try:
                token = get_valid_jira_token_sync()
            except JiraAuthExpiredError as exc:
                raise ConnectionError(
                    "Jira OAuth2 authorization expired. "
                    "Please re-run the setup wizard to authorize Jira OAuth2."
                ) from exc

            if token:
                request.headers["Authorization"] = f"Bearer {token}"
            return original_send(request, **kwargs)

        session.send = _oauth2_send

    def _patch_session_for_gateway(self, session: Any, gateway_url: str) -> None:
        """Rewrite site-URL requests to the Atlassian gateway at transport level.

        Scoped API tokens are only accepted by the gateway, not by the direct
        Jira Cloud site URL.  Attaching `content` and inline-image URLs are
        always absolute site URLs embedded in API responses.  Patching ``send``
        here means every request that goes through this session — regardless of
        who constructed the URL — is transparently routed to the gateway without
        any caller needing to know about the gateway.
        """
        site_base = self.site_url.rstrip("/")
        gateway_base = gateway_url.rstrip("/")
        original_send = session.send

        def _rewriting_send(request: Any, **kwargs: Any) -> Any:
            if request.url and request.url.startswith(site_base + "/"):
                request.url = gateway_base + request.url[len(site_base) :]
            return original_send(request, **kwargs)

        session.send = _rewriting_send

    def _connect(self) -> JIRA:
        """Connect to Jira using the configured authentication.

        Connection strategy:
        1. Create a JIRA instance against ``config.server_url``.
        2. Verify authentication via ``/myself`` (for all auth types — the
           JIRA constructor alone is insufficient because ``serverInfo`` is public).
        3. If verification fails with HTTP 401 **and** the instance is Jira Cloud
           **and** ``auth_type`` is ``"basic"``, attempt a gateway connection via
           the Atlassian API gateway (``api.atlassian.com``).  This transparently
           supports scoped API tokens which only work through the gateway.
        4. If all attempts fail, raise ``ConnectionError`` with a clear message.

        Gateway fallback is deliberately restricted to Cloud + basic auth because:
        - ``token`` and ``oauth1`` are only used on Jira Data Center / Server,
          which has no gateway.
        - A 401 on DC basic auth means wrong credentials, not a scoped token.
        """
        try:
            if is_oauth2(self.config.auth_type):
                return self._connect_via_gateway()
            jira = self._create_jira_instance(self.config.server_url)
        except NotImplementedError:
            raise
        except Exception as e:
            status_code = getattr(e, "status_code", None)
            detail = f"HTTP {status_code}: {e}" if status_code else f"{type(e).__name__}: {e}"
            raise ConnectionError(
                f"Could not connect to Jira at '{self.config.server_url}' "
                f"(auth_type='{self.config.auth_type}'): {detail}"
            ) from e

        try:
            auth_ok = self._verify_connection(jira)
        except Exception as e:
            status_code = getattr(e, "status_code", None)
            detail = f"HTTP {status_code}: {e}" if status_code else f"{type(e).__name__}: {e}"
            raise ConnectionError(
                f"Could not connect to Jira at '{self.config.server_url}' "
                f"(auth_type='{self.config.auth_type}'): {detail}"
            ) from e

        if auth_ok:
            logger.debug(
                "Connected to Jira at '%s' (auth_type='%s').",
                self.config.server_url,
                self.config.auth_type,
            )
            return jira

        if self.config.auth_type == "basic" and jira._is_cloud:
            logger.info(
                "Direct authentication to '%s' failed (likely a scoped API token). "
                "Attempting connection via Atlassian API gateway.",
                self.config.server_url,
            )
            try:
                return self._connect_via_gateway()
            except ConnectionError as gateway_error:
                raise ConnectionError(
                    f"Could not connect to Jira at '{self.config.server_url}' "
                    f"(auth_type='{self.config.auth_type}'): "
                    "Direct authentication failed and gateway fallback also failed: "
                    f"{gateway_error}"
                ) from gateway_error

        raise ConnectionError(
            f"Could not connect to Jira at '{self.config.server_url}' "
            f"(auth_type='{self.config.auth_type}'): "
            "Authentication failed (HTTP 401). Please check your credentials."
        )

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
        logger.debug("Fetching issue '%s'", issue_id)
        try:
            issue = self.jira.issue(issue_id, fields=fields, expand=expand, properties=properties)
            logger.debug("Successfully fetched issue '%s'", issue_id)
            return issue
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

        num_batches = math.ceil(len(issue_keys) / chunk_size)
        logger.debug(
            "Fetching %d issue(s) by key in %d batch(es) (chunk_size=%d)",
            len(issue_keys),
            num_batches,
            chunk_size,
        )
        all_issues: list[Issue] = []

        for batch_index, batch in enumerate(_chunks(issue_keys, chunk_size), start=1):
            keys_str = ",".join(batch)
            if base_jql:
                jql = f"({base_jql}) AND issuekey IN ({keys_str})"
            else:
                jql = f"issuekey IN ({keys_str})"

            logger.debug("Fetching batch %d/%d (%d key(s))", batch_index, num_batches, len(batch))
            batch_issues = self.fetch_issues_by_jql(
                jql_query=jql,
                fields=fields,
                expand=expand,
                properties=properties,
                max_results=max_results,
            )
            all_issues.extend(batch_issues)

        logger.debug(
            "Fetched %d issue(s) total for %d requested key(s)", len(all_issues), len(issue_keys)
        )
        return all_issues

    def fetch_issues_by_jql(
        self,
        jql_query: str,
        fields: str | None = "*all",
        expand: str | None = None,
        properties: str | None = None,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> list[Issue]:
        logger.debug("Fetching issues by JQL (max_results=%d): %s", max_results, jql_query)
        try:
            issues: list[Issue] = []

            if self.use_manual_pagination:
                start_at = 0
                page_num = 0
                while True:
                    page_num += 1
                    logger.debug("Fetching JQL page %d (start_at=%d)", page_num, start_at)
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
                    logger.debug(
                        "JQL page %d: received %d issue(s) (total so far: %d)",
                        page_num,
                        len(chunk),
                        len(issues),
                    )
                    if len(chunk) < max_results:
                        # No more pages
                        break
                    start_at += len(chunk)
            else:
                next_page_token = None
                page_num = 0
                while True:
                    page_num += 1
                    logger.debug(
                        "Fetching JQL page %d (has_next_page_token=%s)",
                        page_num,
                        bool(next_page_token),
                    )
                    issues_chunk = self.jira.enhanced_search_issues(
                        jql_str=jql_query,
                        nextPageToken=next_page_token,
                        maxResults=max_results,
                        fields=fields,
                        expand=expand,
                        properties=properties,
                    )
                    chunk = list(issues_chunk)
                    issues.extend(chunk)
                    logger.debug(
                        "JQL page %d: received %d issue(s) (total so far: %d)",
                        page_num,
                        len(chunk),
                        len(issues),
                    )
                    if not issues_chunk.nextPageToken:
                        break
                    next_page_token = issues_chunk.nextPageToken
            logger.debug("Fetched %d issue(s) total using JQL query", len(issues))
            return issues
        except JIRAError as e:
            logger.warning(f"Error fetching issues by JQL '{jql_query}': {e}")
            return []

    def fetch_projects(self) -> list[Project]:
        logger.debug("Fetching projects from Jira")
        try:
            projects = self.jira.projects()
            logger.debug("Fetched %d project(s) from Jira", len(projects))
            return projects
        except JIRAError as e:
            logger.warning(f"Error fetching projects: {e}")
            return []

    def _fetch_fields_for_issue_type(self, project_key: str, issue_type_id: str) -> list[Field]:
        """Fetch all fields for a single issue type using pagination."""
        logger.debug(
            "Fetching fields for issue type '%s' in project '%s'", issue_type_id, project_key
        )
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
        logger.debug("Fetched %d field(s) for issue type '%s'", len(fields), issue_type_id)
        return fields

    def _fetch_fields_via_issuetypes_endpoint(self, project_key: str) -> dict[str, Field]:
        """Fetch all project fields using the issuetypes endpoint with pagination.

        Uses a dict keyed by field ID to deduplicate fields that appear across multiple issue types.
        """
        logger.debug(
            "Fetching project fields via issuetypes endpoint for project '%s'", project_key
        )
        fields_dict: dict[str, Field] = {}
        start_at = 0
        while True:
            issue_types_chunk = self.jira.project_issue_types(
                project_key, startAt=start_at, maxResults=DEFAULT_MAX_RESULTS
            )
            for issue_type in issue_types_chunk:
                logger.debug(
                    "Processing fields for issue type '%s' in project '%s'",
                    issue_type.id,
                    project_key,
                )
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
        logger.debug(
            "Fetched %d unique field(s) for project '%s' via issuetypes endpoint",
            len(fields_dict),
            project_key,
        )
        return fields_dict

    def _fetch_fields_via_createmeta_endpoint(self, project_key: str) -> dict[str, Field]:
        """Fetch all project fields using the legacy createmeta endpoint."""
        logger.debug(
            "Fetching project fields via createmeta endpoint for project '%s'", project_key
        )
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
        logger.debug(
            "Fetched %d unique field(s) for project '%s' via createmeta endpoint",
            len(fields_dict),
            project_key,
        )
        return fields_dict

    def fetch_project_issue_fields(self, project_key: str) -> list[Field]:
        if self.use_issuetypes_endpoint:
            logger.debug("_fetch_project_issue_fields: Use issuetypes endpoint")
            fields_dict = self._fetch_fields_via_issuetypes_endpoint(project_key)
        else:
            logger.debug("_fetch_project_issue_fields: Use createmeta endpoint")
            fields_dict = self._fetch_fields_via_createmeta_endpoint(project_key)
        result = list(fields_dict.values())
        logger.debug("Fetched %d unique field(s) for project '%s'", len(result), project_key)
        return result

    def fetch_project_versions(self, project_key: str) -> list[str]:
        logger.debug("Fetching versions for project '%s'", project_key)
        try:
            versions = self.jira.project_versions(project_key)
            if not versions:
                logger.debug("No versions found for project '%s'", project_key)
                return []
            names = [version.name for version in versions if version.name]
            logger.debug("Fetched %d version(s) for project '%s'", len(names), project_key)
            return names
        except JIRAError as e:
            logger.warning(f"Error fetching project versions for {project_key}: {e}")
            return []

    def fetch_project_boards(self, project_key: str) -> list[Board]:
        logger.debug("Fetching boards for project '%s'", project_key)
        try:
            boards = self.jira.boards(projectKeyOrID=project_key)
            logger.debug("Fetched %d board(s) for project '%s'", len(boards), project_key)
            return boards  # type: ignore[no-any-return]
        except JIRAError as e:
            logger.warning(f"Error fetching boards for project {project_key}: {e}")
            return []

    def fetch_sprints(self, board_id: int) -> list[Sprint]:
        logger.debug("Fetching sprints for board %d", board_id)
        try:
            sprints = self.jira.sprints(board_id)
            logger.debug("Fetched %d sprint(s) for board %d", len(sprints), board_id)
            return sprints  # type: ignore[no-any-return]
        except JIRAError as e:
            logger.warning(f"Error fetching sprints for board {board_id}: {e}")
            return []

    def fetch_sprint_by_name(self, project_key: str, sprint_name: str) -> Sprint | None:
        logger.debug("Searching for sprint '%s' in project '%s'", sprint_name, project_key)
        boards = self.fetch_project_boards(project_key)
        scrum_boards = [board for board in boards if board.type == "scrum"]
        logger.debug("Found %d scrum board(s) in project '%s'", len(scrum_boards), project_key)
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
            logger.debug("Returning %d cached issue field(s)", len(cached))
            return cached
        logger.debug("Fetching all issue fields from Jira")
        try:
            fields = self.jira.fields()
            logger.debug("Fetched %d issue field(s) from Jira", len(fields))
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
        logger.debug("Fetching changelog for '%s' via paginated endpoint", issue_id_or_key)
        max_results = 100
        histories: list[Any] = []
        start_at = 0
        page_num = 0

        while True:
            page_num += 1
            logger.debug(
                "Fetching changelog page %d for '%s' (start_at=%d)",
                page_num,
                issue_id_or_key,
                start_at,
            )
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
            logger.debug(
                "Changelog page %d for '%s': received %d entries (total so far: %d)",
                page_num,
                issue_id_or_key,
                len(page_histories),
                len(histories),
            )
            total = page.get("total")
            if page.get("isLast", False) or (total is not None and start_at >= total):
                break
            if len(page_histories) < max_results:
                break

        logger.debug("Fetched %d changelog entries for '%s'", len(histories), issue_id_or_key)
        return histories

    def _fetch_changelog_via_expand(self, issue_id_or_key: str) -> list[Any]:
        """
        Fetch changelog histories via ``expand=changelog`` on the issue resource.

        ``GET /rest/api/2/issue/{key}?expand=changelog`` — works on all Jira
        instance types but is truncated to ~100 entries (no pagination).
        Raises on any error; callers are responsible for exception handling.
        """
        logger.debug("Fetching changelog for '%s' via expand", issue_id_or_key)
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
        logger.debug("Fetched %d changelog entries for '%s'", len(raw_histories), issue_id_or_key)
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
        logger.debug("Fetching changelog histories for issue '%s'", issue_id_or_key)
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

        logger.debug(
            "Bulk fetching changelog histories for %d issue(s) in batches of %d",
            len(issue_ids),
            batch_size,
        )
        try:
            for batch_index, batch in enumerate(_chunks(issue_ids, batch_size), start=1):
                logger.debug(
                    "Bulk changelog batch %d: fetching %d issue(s)", batch_index, len(batch)
                )
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
                    issue_change_logs = page_data.get("issueChangeLogs", [])
                    for issue_changelog in issue_change_logs:
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
                    logger.debug(
                        "Bulk changelog batch %d page: processed %d issue changelog(s) "
                        "(has_next_page=%s)",
                        batch_index,
                        len(issue_change_logs),
                        bool(next_page_token),
                    )
                    if not next_page_token:
                        break

        except Exception as e:
            logger.warning(
                f"Error bulk fetching issue changelog histories: {e}. "
                f"Returning {len(issue_changelogs)} partial result(s)."
            )

        logger.debug(
            "Bulk changelog fetch completed: got changelogs for %d issue(s)",
            len(issue_changelogs),
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

        logger.debug("Fetching changelog histories for %d issue(s)", len(issues))
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

        logger.debug("Fetched changelog histories for %d issue(s)", len(issue_changelogs))
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
