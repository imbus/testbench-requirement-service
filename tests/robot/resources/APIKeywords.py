import json
from contextlib import contextmanager
from typing import Any

import requests  # type: ignore
from assertionengine import AssertionOperator, verify_assertion
from robot.api import logger


class APIKeywords:
    """API testing library for Robot Framework"""

    ROBOT_LIBRARY_SCOPE = "TEST"

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:8020",
        username: str = "admin",
        password: str = "123456",
        timeout: int = 3,
        reuse_session: bool = False,
    ):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.timeout = timeout
        self.reuse_session = reuse_session
        self._session = None
        if self.reuse_session:
            self._session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create and configure a new session."""
        session = requests.Session()
        session.headers.update({"accept": "application/json"})
        if self.username or self.password:
            session.auth = (self.username, self.password)
        return session

    @contextmanager
    def _get_session(self):
        """Get a session - either reuse existing session or create a new one."""
        if self.reuse_session and self._session:
            yield self._session
        else:
            session = self._create_session()
            try:
                yield session
            finally:
                session.close()

    def set_credentials(self, username: str | None = None, password: str | None = None):
        """Update credentials. If using persistent session, recreates it with new auth."""
        if username is not None:
            self.username = username
        if password is not None:
            self.password = password
        if self.reuse_session:
            if self._session:
                self._session.close()
            self._session = self._create_session()

    def get(
        self,
        endpoint: str,
        assertion_operator: AssertionOperator | None = AssertionOperator.validate,
        assertion_expected: Any | None = "value.status_code == 200",
    ):
        """GET request to the specified endpoint."""
        with self._get_session() as session:
            response = session.get(f"{self.base_url}{endpoint}", timeout=self.timeout)
            self._log_response(response)
            return verify_assertion(response, assertion_operator, assertion_expected, "Response")

    def post(
        self,
        endpoint: str,
        body: Any | None = None,
        assertion_operator: AssertionOperator | None = AssertionOperator.validate,
        assertion_expected: Any | None = "value.status_code == 200",
    ):
        """POST request to the specified endpoint."""
        body = json.loads(body) if isinstance(body, str) else body
        with self._get_session() as session:
            response = session.post(
                f"{self.base_url}{endpoint}",
                json=body,
                timeout=self.timeout,
            )
            self._log_response(response)
            return verify_assertion(response, assertion_operator, assertion_expected, "Response")

    def get_server_name_and_version(
        self,
        assertion_operator: AssertionOperator | None = AssertionOperator.validate,
        assertion_expected: Any | None = "value.status_code == 200",
    ):
        return self.get("/server-name-and-version", assertion_operator, assertion_expected)

    def get_projects(
        self,
        assertion_operator: AssertionOperator | None = AssertionOperator.validate,
        assertion_expected: Any | None = "value.status_code == 200",
    ):
        return self.get("/projects", assertion_operator, assertion_expected)

    def get_baselines(
        self,
        project: str,
        assertion_operator: AssertionOperator | None = AssertionOperator.validate,
        assertion_expected: Any | None = "value.status_code == 200",
    ):
        return self.get(f"/projects/{project}/baselines", assertion_operator, assertion_expected)

    def get_requirements_root(
        self,
        project: str,
        baseline: str,
        assertion_operator: AssertionOperator | None = AssertionOperator.validate,
        assertion_expected: Any | None = "value.status_code == 200",
    ):
        return self.get(
            f"/projects/{project}/baselines/{baseline}/requirements-root",
            assertion_operator,
            assertion_expected,
        )

    def get_user_defined_attributes(
        self,
        assertion_operator: AssertionOperator | None = AssertionOperator.validate,
        assertion_expected: Any | None = "value.status_code == 200",
    ):
        return self.get("/user-defined-attributes", assertion_operator, assertion_expected)

    def post_all_user_defined_attributes(
        self,
        project: str,
        baseline: str,
        body: Any | None = None,
        assertion_operator: AssertionOperator | None = AssertionOperator.validate,
        assertion_expected: Any | None = "value.status_code == 200",
    ):
        return self.post(
            f"/projects/{project}/baselines/{baseline}/user-defined-attributes",
            body,
            assertion_operator,
            assertion_expected,
        )

    def post_extended_requirement(
        self,
        project: str,
        baseline: str,
        body: Any | None = None,
        assertion_operator: AssertionOperator | None = AssertionOperator.validate,
        assertion_expected: Any | None = "value.status_code == 200",
    ):
        return self.post(
            f"/projects/{project}/baselines/{baseline}/extended-requirement",
            body,
            assertion_operator,
            assertion_expected,
        )

    def post_requirement_versions(
        self,
        project: str,
        baseline: str,
        body: Any | None = None,
        assertion_operator: AssertionOperator | None = AssertionOperator.validate,
        assertion_expected: Any | None = "value.status_code == 200",
    ):
        return self.post(
            f"/projects/{project}/baselines/{baseline}/requirement-versions",
            body,
            assertion_operator,
            assertion_expected,
        )

    def _log_response(self, response: requests.Response):
        response_dict = {
            "url": response.url,
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "encoding": response.encoding,
            "elapsed_time": response.elapsed.total_seconds(),
            "text": response.text,
            "json": response.json()
            if "application/json" in response.headers.get("Content-Type", "")
            else None,
        }
        logger.trace(json.dumps(response_dict, indent=2))
