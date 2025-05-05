import json
from base64 import b64encode
from typing import Any

import requests  # type: ignore
from assertionengine import AssertionOperator, verify_assertion
from robot.api import logger


class APIKeywords:
    ROBOT_LIBRARY_SCOPE = "TEST"

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:8000",
        username: str = "admin",
        password: str = "123456",
    ):
        self.base_url = base_url
        self.username = username
        self.password = password

    @property
    def headers(self):
        if not self.username and not self.password:
            return {}
        credentials = f"{self.username}:{self.password}"
        encoded_credentials = b64encode(credentials.encode()).decode("utf-8")
        return {"Authorization": f"Basic {encoded_credentials}"}

    def set_credentials(self, username: str | None = None, password: str | None = None):
        if username is not None:
            self.username = username
        if password is not None:
            self.password = password

    def get_server_name_and_version(
        self,
        assertion_operator: AssertionOperator | None = AssertionOperator.validate,
        assertion_expected: Any | None = "value.status_code == 200",
    ):
        response = requests.get(f"{self.base_url}/server-name-and-version", headers=self.headers)
        self._log_response(response)
        return verify_assertion(response, assertion_operator, assertion_expected, "Response")

    def get_projects(
        self,
        assertion_operator: AssertionOperator | None = AssertionOperator.validate,
        assertion_expected: Any | None = "value.status_code == 200",
    ):
        response = requests.get(f"{self.base_url}/projects", headers=self.headers)
        self._log_response(response)
        return verify_assertion(response, assertion_operator, assertion_expected, "Response")

    def get_baselines(
        self,
        project: str,
        assertion_operator: AssertionOperator | None = AssertionOperator.validate,
        assertion_expected: Any | None = "value.status_code == 200",
    ):
        response = requests.get(
            f"{self.base_url}/projects/{project}/baselines", headers=self.headers
        )
        self._log_response(response)
        return verify_assertion(response, assertion_operator, assertion_expected, "Response")

    def get_requirements_root(
        self,
        project: str,
        baseline: str,
        assertion_operator: AssertionOperator | None = AssertionOperator.validate,
        assertion_expected: Any | None = "value.status_code == 200",
    ):
        response = requests.get(
            f"{self.base_url}/projects/{project}/baselines/{baseline}/requirements-root",
            headers=self.headers,
        )
        self._log_response(response)
        return verify_assertion(response, assertion_operator, assertion_expected, "Response")

    def get_user_defined_attributes(
        self,
        assertion_operator: AssertionOperator | None = AssertionOperator.validate,
        assertion_expected: Any | None = "value.status_code == 200",
    ):
        response = requests.get(f"{self.base_url}/user-defined-attributes", headers=self.headers)
        self._log_response(response)
        return verify_assertion(response, assertion_operator, assertion_expected, "Response")

    def post_all_user_defined_attributes(
        self,
        project: str,
        baseline: str,
        body=None,
        assertion_operator: AssertionOperator | None = AssertionOperator.validate,
        assertion_expected: Any | None = "value.status_code == 200",
    ):
        response = requests.post(
            f"{self.base_url}/projects/{project}/baselines/{baseline}/user-defined-attributes",
            data=body,
            headers=self.headers,
        )
        self._log_response(response)
        return verify_assertion(response, assertion_operator, assertion_expected, "Response")

    def post_extended_requirement(
        self,
        project: str,
        baseline: str,
        body=None,
        assertion_operator: AssertionOperator | None = AssertionOperator.validate,
        assertion_expected: Any | None = "value.status_code == 200",
    ):
        response = requests.post(
            f"{self.base_url}/projects/{project}/baselines/{baseline}/extended-requirement",
            data=body,
            headers=self.headers,
        )
        self._log_response(response)
        return verify_assertion(response, assertion_operator, assertion_expected, "Response")

    def post_requirement_versions(
        self,
        project: str,
        baseline: str,
        body=None,
        assertion_operator: AssertionOperator | None = AssertionOperator.validate,
        assertion_expected: Any | None = "value.status_code == 200",
    ):
        response = requests.post(
            f"{self.base_url}/projects/{project}/baselines/{baseline}/requirement-versions",
            data=body,
            headers=self.headers,
        )
        self._log_response(response)
        return verify_assertion(response, assertion_operator, assertion_expected, "Response")

    def _log_response(self, response):
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
